"""Fases feitas no editor: o formato do arquivo, a validacao e o gerador.

Uma fase e uma grade de colunas de `COLUNA` px. Cada coluna tem um nivel de
chao (0, 1 ou 2, as mesmas tres alturas do modo infinito) ou e buraco (-1).
Em cima das colunas ficam os objetos: carro, humano, moeda e caixa.

O arquivo e um JSON em `fases/<nome>.json`:

    {"versao": 1, "nome": "...", "autor": "...", "cenario": "cidade",
     "velocidade": 450, "colunas": [0, 0, -1, 1, ...],
     "objetos": [{"tipo": "carro", "col": 40, "vida": 2},
                 {"tipo": "moeda", "col": 52, "y": 300}, ...]}

O fim da ultima coluna e a linha de chegada.
"""

import json
import os
import re

from jogo import config as cfg
from jogo import poderes
from jogo.entidades import Box, Humano, Moeda, Obstaculo
from jogo.mundo import TEMPO_NO_AR, Segmento

VERSAO = 1
PASTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fases")

COLUNA = 40                 # largura de uma coluna da grade, em px
BURACO = -1
LARGADA = 10                # colunas iniciais travadas em chao reto (400 px)
MIN_COLUNAS = 60
MAX_COLUNAS = 900           # 36000 px = 720 m
PADRAO_COLUNAS = 400        # 320 m
VELOCIDADES = (330, 400, 450, 500, 560, 620, 700)
TIPOS = ("carro", "humano", "moeda", "caixa")
MOEDA_Y = (cfg.TETO + 20, cfg.CHAO_Y - 20)

# buraco maximo, em fracao do alcance do pulo, conforme a proxima plataforma
# fica no mesmo nivel, mais baixa ou um nivel acima. Um pouco acima do que o
# modo infinito sorteia, mas ainda com folga pra horda inteira passar.
FOLGA_MESMO = 0.55
FOLGA_DESCE = 0.60
FOLGA_SOBE = 0.25


def topo_do_nivel(nivel):
    return cfg.CHAO_Y - nivel * cfg.ALTURA_NIVEL


def colunas_do_tunel(total):
    """Colunas que caem no tunel de troca de cenario (chao reto obrigatorio)."""
    travadas = set()
    k = 1
    meio = cfg.TUNEL_LARGURA / 2 + cfg.TUNEL_MARGEM
    while k * cfg.TRECHO_CENARIO - meio < total * COLUNA:
        ini = int((k * cfg.TRECHO_CENARIO - meio) // COLUNA)
        fim = int((k * cfg.TRECHO_CENARIO + meio) // COLUNA)
        travadas.update(range(max(0, ini), min(total, fim + 1)))
        k += 1
    return travadas


def nome_de_arquivo(nome):
    base = re.sub(r"[^a-z0-9]+", "_", nome.lower()).strip("_")
    return (base or "fase") + ".json"


class Problema:
    def __init__(self, ini, fim, texto):
        self.ini, self.fim, self.texto = ini, fim, texto


class Fase:
    def __init__(self, nome="Nova fase", autor="Jogador", colunas=None,
                 objetos=None, velocidade=450, cenario="cidade"):
        self.nome = nome
        self.autor = autor
        self.velocidade = velocidade
        self.cenario = cenario
        self.colunas = list(colunas) if colunas else [0] * PADRAO_COLUNAS
        self.objetos = {}           # coluna -> objeto (um por coluna)
        for obj in objetos or ():
            self.objetos[obj["col"]] = dict(obj)
        self.caminho = None         # de onde veio, pra salvar por cima
        self.travar()

    # ------------------------------------------------------------ regras
    @property
    def total(self):
        return len(self.colunas)

    @property
    def chegada(self):
        return self.total * COLUNA

    @property
    def metros(self):
        return int(self.chegada / cfg.PX_POR_METRO)

    def travadas(self):
        return set(range(LARGADA)) | colunas_do_tunel(self.total)

    def travar(self):
        """Largada e tunel sao sempre chao reto, sem carro."""
        for c in self.travadas():
            self.colunas[c] = 0
            if self.objetos.get(c, {}).get("tipo") == "carro":
                del self.objetos[c]
        for c in [c for c in self.objetos if c >= self.total]:
            del self.objetos[c]

    def pode_por(self, tipo, col):
        if not 0 <= col < self.total:
            return False
        if tipo == "moeda":
            return True
        if self.colunas[col] == BURACO:
            return False
        return not (tipo == "carro" and col in self.travadas())

    def nivel_depois(self, col):
        return self.colunas[col] if col < self.total else 0

    def problemas(self):
        """Trechos impossiveis de passar, pro editor pintar de vermelho."""
        achados = []
        alcance = self.velocidade * TEMPO_NO_AR
        col = 0
        while col < self.total:
            nivel = self.colunas[col]
            if nivel == BURACO:
                ini = col
                while col < self.total and self.colunas[col] == BURACO:
                    col += 1
                antes = self.colunas[ini - 1] if ini > 0 else 0
                depois = self.nivel_depois(col)
                largura = (col - ini) * COLUNA
                if depois >= antes + 2:
                    achados.append(Problema(ini, col - 1, "subida de 2 niveis: o pulo nao alcanca"))
                    continue
                if depois > antes:
                    limite = FOLGA_SOBE * alcance
                elif depois < antes:
                    limite = FOLGA_DESCE * alcance
                else:
                    limite = FOLGA_MESMO * alcance
                if largura > limite:
                    achados.append(Problema(ini, col - 1,
                                            f"buraco de {largura} px: o maximo aqui e {int(limite)} px"))
                continue
            seguinte = self.nivel_depois(col + 1)
            if col + 1 < self.total and seguinte != BURACO and seguinte >= nivel + 2:
                achados.append(Problema(col, col + 1, "parede de 2 niveis: o pulo nao alcanca"))
            col += 1
        return achados

    # ---------------------------------------------------------- arquivo
    def para_dict(self):
        objetos = [self.objetos[c] for c in sorted(self.objetos)]
        return {"versao": VERSAO, "nome": self.nome, "autor": self.autor,
                "cenario": self.cenario, "velocidade": self.velocidade,
                "colunas": self.colunas, "objetos": objetos}

    @classmethod
    def de_dict(cls, dados):
        """Le o dicionario do arquivo (ou da rede). Dado estranho vira erro."""
        if not isinstance(dados, dict) or dados.get("versao") != VERSAO:
            raise ValueError("fase de outra versao")
        colunas = [int(c) for c in dados["colunas"]]
        if not MIN_COLUNAS <= len(colunas) <= MAX_COLUNAS:
            raise ValueError("tamanho de fase invalido")
        colunas = [max(BURACO, min(cfg.NIVEIS - 1, c)) for c in colunas]
        objetos = []
        for obj in dados.get("objetos", []):
            tipo, col = obj.get("tipo"), int(obj.get("col", -1))
            if tipo not in TIPOS or not 0 <= col < len(colunas):
                continue
            limpo = {"tipo": tipo, "col": col}
            if tipo == "carro":
                limpo["vida"] = max(1, min(4, int(obj.get("vida", 2))))
            elif tipo == "moeda":
                limpo["y"] = max(MOEDA_Y[0], min(MOEDA_Y[1], int(obj.get("y", 300))))
            elif tipo == "caixa":
                poder = obj.get("poder")
                limpo["poder"] = poder if poder in poderes.TODOS else poderes.TODOS[0]
            objetos.append(limpo)
        velocidade = int(dados.get("velocidade", 450))
        velocidade = min(VELOCIDADES, key=lambda v: abs(v - velocidade))
        return cls(str(dados.get("nome", "Sem nome"))[:32], str(dados.get("autor", ""))[:24],
                   colunas, objetos, velocidade, str(dados.get("cenario", "cidade")))

    def salvar(self):
        os.makedirs(PASTA, exist_ok=True)
        if self.caminho is None:
            self.caminho = os.path.join(PASTA, nome_de_arquivo(self.nome))
        with open(self.caminho, "w", encoding="utf-8") as arq:
            json.dump(self.para_dict(), arq, ensure_ascii=False, indent=1)
        return self.caminho


def carregar(caminho):
    with open(caminho, encoding="utf-8") as arq:
        fase = Fase.de_dict(json.load(arq))
    fase.caminho = caminho
    return fase


def listar():
    """Fases salvas, em ordem de nome. Arquivo estragado fica de fora."""
    if not os.path.isdir(PASTA):
        return []
    fases = []
    for nome in sorted(os.listdir(PASTA)):
        if not nome.endswith(".json"):
            continue
        try:
            fases.append(carregar(os.path.join(PASTA, nome)))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return fases


# ------------------------------------------------------------------ gerador
class GeradorDeFase:
    """Strategy das fases: monta o caminho todo da grade, uma vez so.

    Depois da chegada o chao segue reto, pra horda ter onde frear.
    """

    def __init__(self, fase):
        self.fase = fase

    def preparar(self, mundo):
        f = self.fase
        mundo.segmentos = [Segmento(-400, 400, cfg.CHAO_Y, 0)]
        col = 0
        while col < f.total:
            nivel = f.colunas[col]
            ini = col
            while col < f.total and f.colunas[col] == nivel:
                col += 1
            if nivel == BURACO:
                continue
            x = ini * COLUNA
            ultimo = mundo.segmentos[-1]
            if ultimo.nivel == nivel and abs(ultimo.fim - x) < 1:
                ultimo.largura += (col - ini) * COLUNA      # emenda com o da largada
            else:
                mundo.segmentos.append(Segmento(x, (col - ini) * COLUNA, topo_do_nivel(nivel), nivel))
        for c, obj in sorted(f.objetos.items()):
            x = c * COLUNA + COLUNA / 2
            nivel = f.colunas[c]
            topo = topo_do_nivel(max(0, nivel))
            if obj["tipo"] == "carro":
                mundo.obstaculos.append(Obstaculo(x, topo, obj["vida"]))
            elif obj["tipo"] == "humano":
                mundo.humanos.append(Humano(x, topo))
            elif obj["tipo"] == "moeda":
                mundo.moedas.append(Moeda(x, obj["y"]))
            elif obj["tipo"] == "caixa":
                mundo.caixas.append(Box(x, topo - 8, obj["poder"]))
        mundo.proxima_caixa = float("inf")

    def estender(self, mundo, limite):
        while mundo.segmentos[-1].fim < limite:
            ultimo = mundo.segmentos[-1]
            ini = max(ultimo.fim, self.fase.chegada)
            if ultimo.nivel == 0 and ultimo.fim >= self.fase.chegada:
                ultimo.largura += cfg.LARGURA
            else:
                mundo.segmentos.append(Segmento(ini, cfg.LARGURA, cfg.CHAO_Y, 0))
