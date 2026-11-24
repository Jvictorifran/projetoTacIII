"""Cliente do placar: a ponte entre a partida local e o servidor da sala.

A conversa com a rede fica numa thread; o jogo so chama `processar()` uma vez
por quadro pra pegar o que chegou. Funciona como um proxy: pro resto do jogo,
mandar o resultado e so chamar `resultado(...)`, como se o placar fosse local.
Se a conexao cair, a partida segue normal e o resultado vai quando voltar.
"""

import queue
import socket
import threading
import time

from rede.protocolo import PORTA, VERSAO, Leitor, codificar

ESPERA_RECONEXAO = 2.0


class ClientePlacar:
    def __init__(self, ip, nome, porta=PORTA):
        self.ip, self.porta, self.nome = ip, porta, nome
        self.fila = queue.Queue()
        self.sock = None
        self.trava = threading.Lock()
        self.parar = threading.Event()
        self.pendente = None        # resultado que nao conseguiu sair

        # estado visto pelo jogo (so a thread principal mexe, em processar)
        self.conectado = False
        self.recebido = False       # ja chegou o bem_vindo
        self.erro = None
        self.sala = ""
        self.modo = "livre"
        self.seed = None
        self.fase = None
        self.linhas = []
        self.aviso = None           # (texto, quando) do ultimo aceito/recusado
        self._restante = None
        self._restante_em = 0.0

        threading.Thread(target=self._rodar, daemon=True).start()

    # --------------------------------------------------- thread da rede
    def _rodar(self):
        while not self.parar.is_set():
            try:
                sock = socket.create_connection((self.ip, self.porta), timeout=3)
            except OSError as e:
                self.fila.put({"tipo": "_falha", "motivo": e.strerror or str(e)})
                self.parar.wait(ESPERA_RECONEXAO)
                continue
            sock.settimeout(None)
            with self.trava:
                self.sock = sock
            self._enviar({"tipo": "ola", "nome": self.nome, "versao": VERSAO})
            if self.pendente:
                self._enviar(self.pendente)
            leitor = Leitor()
            try:
                while not self.parar.is_set():
                    dados = sock.recv(65536)
                    if not dados:
                        break
                    for msg in leitor.alimentar(dados):
                        if msg["tipo"] == "aceito" or msg["tipo"] == "recusado":
                            self.pendente = None
                        self.fila.put(msg)
            except OSError:
                pass
            with self.trava:
                self.sock = None
            try:
                sock.close()
            except OSError:
                pass
            self.fila.put({"tipo": "_caiu"})
            self.parar.wait(ESPERA_RECONEXAO)

    def _enviar(self, msg):
        with self.trava:
            sock = self.sock
            if sock is None:
                return False
            try:
                sock.sendall(codificar(msg))
                return True
            except OSError:
                return False

    # ------------------------------------------------- lado do jogo
    def processar(self):
        """Aplica o que chegou da rede. Chame uma vez por quadro."""
        while True:
            try:
                msg = self.fila.get_nowait()
            except queue.Empty:
                break
            tipo = msg["tipo"]
            if tipo == "bem_vindo":
                self.conectado, self.recebido, self.erro = True, True, None
                self.nome = msg.get("nome", self.nome)
                self.sala, self.modo = msg.get("sala", ""), msg.get("modo", "livre")
                self.seed, self.fase = msg.get("seed"), msg.get("fase")
                self._marcar_restante(msg.get("restante"))
            elif tipo == "ranking":
                self.linhas = msg.get("linhas", [])
                self._marcar_restante(msg.get("restante"))
            elif tipo == "aceito":
                texto = f"Seu resultado entrou: {msg.get('lugar')}o de {msg.get('total')}"
                if msg.get("recorde"):
                    texto += " - novo recorde seu!"
                self.aviso = (texto, time.monotonic())
            elif tipo == "recusado":
                self.aviso = ("Resultado recusado: " + str(msg.get("motivo")), time.monotonic())
            elif tipo == "erro":
                self.erro = str(msg.get("motivo"))
                self.fechar(avisar=False)
            elif tipo == "_falha":
                self.conectado = False
                self.erro = "sem resposta do servidor: " + str(msg.get("motivo"))
            elif tipo == "_caiu":
                self.conectado = False
                if not self.parar.is_set():
                    self.erro = "conexao caiu, tentando de novo..."

    def _marcar_restante(self, restante):
        self._restante = restante
        self._restante_em = time.monotonic()

    def restante(self):
        if self._restante is None:
            return None
        return max(0.0, self._restante - (time.monotonic() - self._restante_em))

    def comecei(self):
        self._enviar({"tipo": "comecei"})

    def progresso(self, pontos, metros):
        self._enviar({"tipo": "progresso", "pontos": pontos, "metros": metros})

    def resultado(self, pontos, metros, moedas, horda_max, duracao, seed, fase):
        msg = {"tipo": "resultado", "pontos": pontos, "metros": metros, "moedas": moedas,
               "horda_max": horda_max, "duracao": round(duracao, 2), "seed": seed,
               "fase": fase}
        self.pendente = msg
        self._enviar(msg)

    def posicao(self, pontos_agora):
        """(lugar, total, quem esta logo a frente e por quantos pontos)."""
        outros = [(l["pontos"], l["nome"]) for l in self.linhas if l["nome"] != self.nome]
        meu = max(pontos_agora, next((l["pontos"] for l in self.linhas
                                      if l["nome"] == self.nome), 0))
        frente = sorted((p, n) for p, n in outros if p >= meu)
        lugar = len(frente) + 1
        alvo = (frente[0][1], frente[0][0] - meu + 1) if frente else None
        return lugar, len(outros) + 1, alvo

    def fechar(self, avisar=True):
        if avisar:
            self._enviar({"tipo": "tchau"})
        self.parar.set()
        with self.trava:
            sock, self.sock = self.sock, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        self.conectado = False
