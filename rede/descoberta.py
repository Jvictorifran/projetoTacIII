"""Descoberta de salas na LAN por broadcast UDP.

O anfitriao grita "tem sala aqui" a cada segundo; quem esta na tela de
multiplayer escuta e lista as salas que ouviu nos ultimos segundos.
"""

import json
import socket
import threading
import time

from rede.protocolo import ASSINATURA, PORTA_ANUNCIO, VERSAO

INTERVALO = 1.0
VALIDADE = 3.5              # sala que sumiu por isso sai da lista


class Anunciante(threading.Thread):
    def __init__(self, info_da_sala):
        super().__init__(daemon=True)
        self.info_da_sala = info_da_sala    # funcao -> dict com sala, porta, modo...
        self.parar = threading.Event()

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            while not self.parar.is_set():
                msg = dict(self.info_da_sala(), tipo="anuncio",
                           assinatura=ASSINATURA, versao=VERSAO)
                dados = json.dumps(msg).encode("utf-8")
                # o broadcast cobre a rede; o 127.0.0.1 cobre quem joga na
                # mesma maquina do servidor
                for destino in ("<broadcast>", "127.0.0.1"):
                    try:
                        s.sendto(dados, (destino, PORTA_ANUNCIO))
                    except OSError:
                        pass
                self.parar.wait(INTERVALO)
        finally:
            s.close()


class Buscador:
    """Escuta os anuncios sem travar o jogo: chame `salas()` a cada quadro."""

    def __init__(self):
        self.encontradas = {}       # (ip, porta) -> (info, visto_em)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.erro = None
        try:
            self.sock.bind(("", PORTA_ANUNCIO))
        except OSError as e:
            self.erro = f"nao deu pra escutar a porta {PORTA_ANUNCIO}: {e.strerror}"
        self.sock.setblocking(False)

    def salas(self):
        agora = time.monotonic()
        while True:
            try:
                dados, (ip, _) = self.sock.recvfrom(4096)
            except (BlockingIOError, OSError):
                break
            try:
                info = json.loads(dados.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            if not isinstance(info, dict) or info.get("assinatura") != ASSINATURA:
                continue
            porta = info.get("porta")
            if not isinstance(porta, int):
                continue
            # o anuncio pelo 127.0.0.1 e o da rede sao a mesma sala
            if ip == "127.0.0.1":
                ip = info.get("ip", ip)
            self.encontradas[(ip, porta)] = (info, agora)
        self.encontradas = {k: v for k, v in self.encontradas.items()
                            if agora - v[1] < VALIDADE}
        return sorted(((ip, porta, info) for (ip, porta), (info, _) in self.encontradas.items()),
                      key=lambda s: str(s[2].get("sala", "")))

    def fechar(self):
        self.sock.close()
