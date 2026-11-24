"""Protocolo do placar da LAN: JSON, uma mensagem por linha.

Mensagens (campo `tipo`):

    cliente -> servidor   ola {nome, versao} . comecei . progresso {pontos, metros}
                          resultado {pontos, metros, moedas, horda_max, seed,
                                     fase, duracao} . tchau
    servidor -> cliente   bem_vindo {id, sala, modo, seed, fase, restante}
                          ranking {sala, modo, restante, linhas}
                          aceito {lugar, total} . recusado {motivo} . erro {motivo}
    servidor -> LAN (UDP) anuncio {assinatura, sala, porta, modo, jogadores, versao}
"""

import json
import socket

PORTA = 50505               # TCP: conversa com o servidor do placar
PORTA_ANUNCIO = 50506       # UDP: o anfitriao avisa que tem sala
VERSAO = "2.0"
ASSINATURA = "ZT2D"
LINHA_MAX = 256 * 1024      # uma fase inteira cabe folgada numa linha


def codificar(msg):
    return (json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


class Leitor:
    """Junta os pedacos que chegam do socket e devolve as mensagens inteiras."""

    def __init__(self):
        self.buffer = b""

    def alimentar(self, dados):
        self.buffer += dados
        if len(self.buffer) > LINHA_MAX and b"\n" not in self.buffer:
            self.buffer = b""           # lixo sem fim de linha: descarta
            return []
        msgs = []
        while b"\n" in self.buffer:
            linha, self.buffer = self.buffer.split(b"\n", 1)
            try:
                msg = json.loads(linha.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            if isinstance(msg, dict) and isinstance(msg.get("tipo"), str):
                msgs.append(msg)
        return msgs


def ip_local():
    """IP desta maquina na rede local (o UDP `connect` nao manda nada)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
