"""Gera os efeitos sonoros do jogo em WAV, so com a biblioteca padrao.

Cada som e uma funcao `t -> amostra` (-1..1) somada de ondas simples e
ruido, com um envelope por cima - o mesmo jeito dos chips de videogame
antigo. Sai tudo em mono, 16 bits, 22050 Hz, em `assets/sons/`.

    ./venv/bin/python ferramentas/gerar_sons.py

Pra mexer num som, mude a funcao dele em `SONS` e rode de novo: os WAV sao
regravados.
"""

import math
import os
import random
import struct
import wave

TAXA = 22050
SAIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "assets", "sons")


# ------------------------------------------------------------------- ondas
def seno(fase):
    return math.sin(math.tau * fase)


def quadrada(fase, largura=0.5):
    return 1.0 if fase % 1.0 < largura else -1.0


def triangulo(fase):
    return 4 * abs(fase % 1.0 - 0.5) - 1


def envelope(t, dur, ataque=0.005, queda=2.0):
    """Sobe em `ataque` segundos e cai ate zero no fim (`queda` = curvatura)."""
    if t < ataque:
        return t / ataque
    return max(0.0, 1 - (t - ataque) / (dur - ataque)) ** queda


def renderizar(dur, voz, volume=0.8, semente=7):
    """Roda `voz(t, fase_de, ruido)` amostra a amostra.

    `fase_de(freq)` acumula a fase de um oscilador cuja frequencia muda no
    tempo (varredura sem estalo); cada chamada na mesma ordem e um oscilador.
    `ruido()` e ruido branco com semente fixa, pro arquivo sair sempre igual.
    """
    rng = random.Random(semente)
    fases = []
    amostras = []
    for i in range(int(dur * TAXA)):
        t = i / TAXA
        usados = [0]

        def fase_de(freq):
            k = usados[0]
            usados[0] += 1
            if k == len(fases):
                fases.append(0.0)
            fases[k] += freq / TAXA
            return fases[k]

        amostras.append(voz(t, fase_de, lambda: rng.uniform(-1, 1)))
    pico = max(1e-9, max(abs(a) for a in amostras))
    return [a / pico * volume for a in amostras]


def passa_baixa(amostras, fator):
    """Filtro de um polo: quanto menor o fator, mais abafado."""
    saida, y = [], 0.0
    for a in amostras:
        y += (a - y) * fator
        saida.append(y)
    pico = max(1e-9, max(abs(a) for a in saida))
    alvo = max(abs(a) for a in amostras)
    return [a / pico * alvo for a in saida]


# -------------------------------------------------------------------- sons
def pulo():
    dur = 0.16

    def voz(t, fase, ruido):
        f = 300 + 520 * (t / dur) ** 0.7
        return quadrada(fase(f), 0.35) * envelope(t, dur, queda=1.4)
    return renderizar(dur, voz, 0.45)


def moeda():
    dur = 0.22

    def voz(t, fase, ruido):
        f = 988 if t < 0.06 else 1319         # si -> mi, o "plim" classico
        return (quadrada(fase(f), 0.5) * 0.6 + seno(fase(f * 2)) * 0.4) \
            * envelope(t, dur, queda=1.8)
    return renderizar(dur, voz, 0.4)


def mordida():
    """Humano virando zumbi: grunhido grave que desce, com um 'nhac' no comeco."""
    dur = 0.3

    def voz(t, fase, ruido):
        f = 190 - 90 * (t / dur) + 14 * seno(fase(28))
        grunhido = (quadrada(fase(f), 0.3) * 0.6 + triangulo(fase(f / 2)) * 0.5)
        nhac = ruido() * max(0.0, 1 - t / 0.04)
        return grunhido * envelope(t, dur, 0.02, 1.2) + nhac * 0.7
    return passa_baixa(renderizar(dur, voz, 0.6), 0.35)


def batida():
    """Zumbi no carro: pancada de lata."""
    dur = 0.28

    def voz(t, fase, ruido):
        lata = ruido() * envelope(t, dur, 0.001, 3.0)
        corpo = seno(fase(150 - 80 * t / dur)) * envelope(t, dur, 0.001, 2.0)
        tinido = seno(fase(1240)) * envelope(t, dur, 0.001, 5.0) * 0.25
        return lata * 0.7 + corpo * 0.8 + tinido
    return passa_baixa(renderizar(dur, voz, 0.7), 0.5)


def parede():
    """Zumbi dando de cara na parede do buraco: baque surdo."""
    dur = 0.22

    def voz(t, fase, ruido):
        baque = seno(fase(120 - 70 * t / dur)) * envelope(t, dur, 0.001, 2.2)
        terra = ruido() * envelope(t, dur, 0.001, 5.0) * 0.5
        return baque + terra
    return passa_baixa(renderizar(dur, voz, 0.75), 0.22)


def explosao():
    """Carro destruido pela horda com poder."""
    dur = 0.55

    def voz(t, fase, ruido):
        estouro = ruido() * envelope(t, dur, 0.002, 2.4)
        grave = seno(fase(95 - 60 * t / dur)) * envelope(t, dur, 0.002, 1.6)
        return estouro * 0.8 + grave
    return passa_baixa(renderizar(dur, voz, 0.75), 0.3)


def poder():
    """Pegou a caixa: arpejo subindo."""
    notas = (523, 659, 784, 1047, 1319)
    passo = 0.07
    dur = passo * len(notas) + 0.25

    def voz(t, fase, ruido):
        i = min(len(notas) - 1, int(t / passo))
        local = t - i * passo
        f = notas[i]
        return (quadrada(fase(f), 0.5) * 0.5 + triangulo(fase(f * 2)) * 0.5) \
            * envelope(local, dur - i * passo, 0.004, 1.5)
    return renderizar(dur, voz, 0.45)


def fim():
    """Fim de jogo: quatro notas descendo."""
    notas = (392, 330, 262, 196)
    passo = 0.17
    dur = passo * len(notas) + 0.35

    def voz(t, fase, ruido):
        i = min(len(notas) - 1, int(t / passo))
        local = t - i * passo
        f = notas[i] * (1 - 0.03 * local)
        return (triangulo(fase(f)) * 0.7 + quadrada(fase(f / 2), 0.4) * 0.3) \
            * envelope(local, dur - i * passo, 0.006, 1.3)
    return renderizar(dur, voz, 0.5)


def clique():
    dur = 0.07

    def voz(t, fase, ruido):
        return quadrada(fase(660 + 500 * t / dur), 0.5) * envelope(t, dur, 0.002, 1.5)
    return renderizar(dur, voz, 0.35)


SONS = {
    "pulo": pulo,
    "moeda": moeda,
    "mordida": mordida,
    "batida": batida,
    "parede": parede,
    "explosao": explosao,
    "poder": poder,
    "fim": fim,
    "clique": clique,
}


def gravar(nome, amostras):
    caminho = os.path.join(SAIDA, nome + ".wav")
    # 5 ms de saida suave: sem isso o corte seco no fim da um estalo
    n = min(len(amostras), int(0.005 * TAXA))
    for i in range(n):
        amostras[-1 - i] *= i / n
    with wave.open(caminho, "wb") as arq:
        arq.setnchannels(1)
        arq.setsampwidth(2)
        arq.setframerate(TAXA)
        arq.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, a)) * 32767)) for a in amostras))
    return caminho


if __name__ == "__main__":
    os.makedirs(SAIDA, exist_ok=True)
    for nome, funcao in SONS.items():
        amostras = funcao()
        print(f"{gravar(nome, amostras)}  ({len(amostras) / TAXA:.2f} s)")
