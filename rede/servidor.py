"""Servidor do placar: roda numa thread no computador do anfitriao.

So ele mexe no ranking. Cada cliente manda o resultado das proprias partidas;
o servidor confere, guarda e avisa todo mundo (padrao Observer pela rede).
"""

import itertools
import json
import os
import socket
import threading
import time

from jogo import config as cfg
from rede.descoberta import Anunciante
from rede.protocolo import PORTA, VERSAO, Leitor, codificar, ip_local

CAMINHO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "placar_lan.json")
LIVRE, DESAFIO = "livre", "desafio"
TOP = 10
TOLERANCIA_FIM = 60.0       # partida comecada no fim do desafio ainda conta
BONUS_POR_ZUMBI = 10        # o mesmo do fim de fase (jogo.py)


class Placar:
    """Melhor partida de cada jogador da sala."""

    def __init__(self, entradas=None):
        self.entradas = dict(entradas or {})

    def registrar(self, nome, r):
        atual = self.entradas.get(nome)
        if atual is None or r["pontos"] > atual["pontos"]:
            self.entradas[nome] = {k: r[k] for k in ("pontos", "metros", "moedas", "horda_max")}
            return True
        return False

    def ordenado(self):
        return sorted(self.entradas.items(), key=lambda kv: (-kv[1]["pontos"], kv[0]))

    def lugar(self, nome):
        for i, (n, _) in enumerate(self.ordenado()):
            if n == nome:
                return i + 1
        return None


class Conexao:
    def __init__(self, sock, endereco, ident):
        self.sock = sock
        self.endereco = endereco
        self.id = ident
        self.nome = None
        self.jogando = False
        self.agora = 0              # pontos da partida em andamento
        self.trava = threading.Lock()

    def enviar(self, msg):
        try:
            with self.trava:
                self.sock.sendall(codificar(msg))
            return True
        except OSError:
            return False


class ServidorPlacar:
    def __init__(self, sala, modo=LIVRE, seed=None, minutos=10, fase=None,
                 porta=PORTA, caminho=None):
        self.sala = sala[:32]
        self.modo = modo
        self.seed = seed
        self.fase = fase            # dict da fase do editor (desafio numa fase)
        self.porta = porta
        self.caminho = caminho or CAMINHO
        self.fim = time.monotonic() + minutos * 60 if modo == DESAFIO else None
        self.chave = f"{self.sala}|{modo}|{seed}|{fase['nome'] if fase else ''}"
        self.placar = Placar(self._ler_guardado())
        self.conexoes = []
        self.ids = itertools.count(1)
        self.trava = threading.Lock()
        self.parar = threading.Event()
        self.sock = None
        self.anunciante = None
        self.ip = ip_local()

    # ---------------------------------------------------------- ciclo
    def iniciar(self):
        """Abre a porta. Levanta OSError se ela estiver ocupada."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.porta))
        self.sock.listen(8)
        self.sock.settimeout(0.5)
        threading.Thread(target=self._aceitar, daemon=True).start()
        self.anunciante = Anunciante(self.info)
        self.anunciante.start()

    def encerrar(self):
        self.parar.set()
        if self.anunciante:
            self.anunciante.parar.set()
        with self.trava:
            conexoes = list(self.conexoes)
        for c in conexoes:
            c.enviar({"tipo": "erro", "motivo": "o anfitriao fechou a sala"})
            try:
                c.sock.close()
            except OSError:
                pass
        if self.sock:
            self.sock.close()

    def info(self):
        with self.trava:
            jogadores = sum(1 for c in self.conexoes if c.nome)
        return {"sala": self.sala, "porta": self.porta, "modo": self.modo,
                "jogadores": jogadores, "ip": self.ip}

    def restante(self):
        return None if self.fim is None else max(0.0, self.fim - time.monotonic())

    # ------------------------------------------------------- conexoes
    def _aceitar(self):
        while not self.parar.is_set():
            try:
                sock, endereco = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            sock.settimeout(None)
            c = Conexao(sock, endereco, next(self.ids))
            with self.trava:
                self.conexoes.append(c)
            threading.Thread(target=self._atender, args=(c,), daemon=True).start()

    def _atender(self, c):
        leitor = Leitor()
        try:
            while not self.parar.is_set():
                dados = c.sock.recv(4096)
                if not dados:
                    break
                for msg in leitor.alimentar(dados):
                    if not self._tratar(c, msg):
                        return
        except OSError:
            pass
        finally:
            with self.trava:
                if c in self.conexoes:
                    self.conexoes.remove(c)
            try:
                c.sock.close()
            except OSError:
                pass
            self.transmitir()

    def _tratar(self, c, msg):
        """Uma mensagem do cliente. Devolve False pra derrubar a conexao."""
        tipo = msg["tipo"]
        if tipo == "ola":
            if msg.get("versao") != VERSAO:
                c.enviar({"tipo": "erro", "motivo": f"versao diferente (servidor {VERSAO})"})
                return False
            c.nome = self._nome_livre(str(msg.get("nome") or "Jogador")[:16], c)
            c.enviar({"tipo": "bem_vindo", "id": c.id, "nome": c.nome, "sala": self.sala,
                      "modo": self.modo, "seed": self.seed, "fase": self.fase,
                      "restante": self.restante()})
            self.transmitir()
        elif c.nome is None:
            return False                    # nada antes do ola
        elif tipo == "comecei":
            c.jogando, c.agora = True, 0
            self.transmitir()
        elif tipo == "progresso":
            c.agora = int(msg.get("pontos", 0) or 0)
            self.transmitir()
        elif tipo == "resultado":
            c.jogando = False
            motivo = self.validar(msg)
            if motivo:
                c.enviar({"tipo": "recusado", "motivo": motivo})
            else:
                r = {k: int(msg[k]) for k in ("pontos", "metros", "moedas", "horda_max")}
                with self.trava:
                    melhorou = self.placar.registrar(c.nome, r)
                    lugar = self.placar.lugar(c.nome)
                    total = len(self.placar.entradas)
                    if melhorou:
                        self._guardar()
                c.enviar({"tipo": "aceito", "lugar": lugar, "total": total,
                          "recorde": melhorou})
            self.transmitir()
        elif tipo == "tchau":
            return False
        return True

    def _nome_livre(self, nome, c):
        with self.trava:
            usados = {o.nome for o in self.conexoes if o is not c and o.nome}
        base, n = nome, 2
        while nome in usados:
            nome = f"{base[:13]} {n}"
            n += 1
        return nome

    # -------------------------------------------------------- regras
    def validar(self, r):
        """Motivo pra recusar o resultado, ou None se ele e plausivel."""
        try:
            pontos, metros = int(r["pontos"]), int(r["metros"])
            moedas, horda = int(r["moedas"]), int(r["horda_max"])
            duracao = float(r["duracao"])
        except (KeyError, TypeError, ValueError):
            return "resultado incompleto"
        if min(pontos, metros, moedas, horda) < 0 or duracao <= 0:
            return "numeros negativos"
        if metros > duracao * cfg.VEL_MAXIMA / cfg.PX_POR_METRO + 20:
            return "metros demais pro tempo de jogo"
        if horda > cfg.MAX_ZUMBIS:
            return "horda maior que o limite"
        bonus = pontos - metros - moedas * 5
        if bonus < 0 or bonus > BONUS_POR_ZUMBI * cfg.MAX_ZUMBIS:
            return "pontuacao nao bate com metros e moedas"
        if self.modo == DESAFIO:
            if self.fase is None and r.get("seed") != self.seed:
                return "partida de outro mapa"
            if self.fase is not None and r.get("fase") != self.fase.get("nome"):
                return "partida de outra fase"
            if time.monotonic() > self.fim + TOLERANCIA_FIM:
                return "o desafio ja acabou"
        return None

    def linhas(self):
        with self.trava:
            linhas = [{"nome": nome, "jogando": False, "agora": 0, **dados}
                      for nome, dados in self.placar.ordenado()]
            por_nome = {l["nome"]: l for l in linhas}
            for c in self.conexoes:
                if not c.nome:
                    continue
                if c.nome not in por_nome:
                    por_nome[c.nome] = {"nome": c.nome, "pontos": 0, "metros": 0, "moedas": 0,
                                        "horda_max": 0, "jogando": False, "agora": 0}
                    linhas.append(por_nome[c.nome])
                por_nome[c.nome]["jogando"] = c.jogando
                por_nome[c.nome]["agora"] = c.agora if c.jogando else 0
        return linhas[:max(TOP, len(self.conexoes))]

    def transmitir(self):
        msg = {"tipo": "ranking", "sala": self.sala, "modo": self.modo,
               "restante": self.restante(), "linhas": self.linhas()}
        with self.trava:
            conexoes = [c for c in self.conexoes if c.nome]
        for c in conexoes:
            c.enviar(msg)

    # ------------------------------------------------------ arquivo
    def _ler_guardado(self):
        try:
            with open(self.caminho, encoding="utf-8") as arq:
                tudo = json.load(arq)
            return tudo.get(self.chave, {})
        except (OSError, ValueError, AttributeError):
            return {}

    def _guardar(self):
        try:
            with open(self.caminho, encoding="utf-8") as arq:
                tudo = json.load(arq)
            if not isinstance(tudo, dict):
                tudo = {}
        except (OSError, ValueError):
            tudo = {}
        tudo[self.chave] = self.placar.entradas
        try:
            with open(self.caminho, "w", encoding="utf-8") as arq:
                json.dump(tudo, arq, ensure_ascii=False, indent=1)
        except OSError:
            pass
