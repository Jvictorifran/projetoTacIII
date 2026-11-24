"""Efeitos sonoros e musica: carrega os arquivos de assets/ e toca pelo nome.

Sem placa de som, ou sem os arquivos, tudo aqui vira um "nao faz nada": o
jogo roda igual, so que mudo. Os WAV saem de `ferramentas/importar_sons.py`, a
partir de sons CC0 baixados da web (a origem de cada um esta no CREDITOS.md).

Um efeito pode ter variacoes (`grito_1.wav`, `grito_2.wav`...): `tocar("grito")`
sorteia uma. Os passos da horda sao um loop num canal proprio, com o volume
acompanhando o tamanho da horda; a musica tema usa o `pygame.mixer.music`.
"""

import glob
import os
import random

import pygame

RAIZ = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sons"
)
TEMA = os.path.join(os.path.dirname(RAIZ), "musica", "tema.mp3")

# volume de cada efeito (os que tocam muito ficam mais baixos)
VOLUMES = {
    "pulo": 0.35,
    "moeda": 0.40,
    "mordida": 0.70,
    "zumbi": 0.55,
    "grito": 0.45,
    "batida": 0.70,
    "quebra": 0.75,
    "parede": 0.80,
    "explosao": 0.80,
    "poder": 0.65,
    "fim": 0.80,
    "clique": 0.50,
    "corrida": 0.35,
}
VOLUME_MUSICA = 0.45
# o mesmo efeito nao recomeca antes disso: 20 moedas pegas no mesmo quadro
# viram um "plim" so, e nao um chiado
INTERVALO_MS = 60
# gritos e gemidos tem intervalo maior: uma horda de 40 nao vira um coral
INTERVALOS = {"grito": 1600, "zumbi": 450}

ligado = True
musica_ligada = True
volume = 0.8                # volume geral (0 a 1), multiplica todos
_sons = {}                  # nome -> lista de variacoes
_ultimo = {}
_canal_passos = None
_passos = 0.0               # intensidade atual dos passos (0 a 1)


def preparar():
    """Chamar antes do pygame.init(): buffer pequeno = som sem atraso."""
    pygame.mixer.pre_init(44100, -16, 2, 512)


def carregar():
    global _canal_passos
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init()
        except pygame.error:
            return                  # sem saida de audio: segue mudo
    pygame.mixer.set_num_channels(24)
    for nome in VOLUMES:
        arquivos = sorted(glob.glob(os.path.join(RAIZ, nome + ".wav")) +
                          glob.glob(os.path.join(RAIZ, nome + "_*.wav")))
        for caminho in arquivos:
            try:
                _sons.setdefault(nome, []).append(pygame.mixer.Sound(caminho))
            except pygame.error:
                continue
    pygame.mixer.set_reserved(1)    # o canal 0 fica so pros passos
    _canal_passos = pygame.mixer.Channel(0)
    definir_volume(volume)


def definir_volume(valor):
    global volume
    volume = max(0.0, min(1.0, valor))
    for nome, variacoes in _sons.items():
        for som in variacoes:
            som.set_volume(VOLUMES[nome] * volume)
    if pygame.mixer.get_init():
        pygame.mixer.music.set_volume(VOLUME_MUSICA * volume)


def disponivel():
    return bool(_sons)


def tocar(nome):
    if not ligado:
        return
    variacoes = _sons.get(nome)
    if not variacoes:
        return
    agora = pygame.time.get_ticks()
    if agora - _ultimo.get(nome, -10 ** 6) < INTERVALOS.get(nome, INTERVALO_MS):
        return
    _ultimo[nome] = agora
    random.choice(variacoes).play()


def alternar():
    """Liga/desliga os efeitos. Devolve o estado novo."""
    global ligado
    ligado = not ligado
    if not ligado and pygame.mixer.get_init():
        for i in range(pygame.mixer.get_num_channels()):
            pygame.mixer.Channel(i).stop()
    return ligado


# ------------------------------------------------------------------ passos
def passos(intensidade):
    """Loop de passos da horda: 0 cala, 1 e a horda cheia correndo no chao."""
    global _passos
    if _canal_passos is None or "corrida" not in _sons:
        return
    alvo = intensidade if ligado else 0.0
    _passos += (alvo - _passos) * 0.15      # sobe e desce suave
    if _passos < 0.02:
        if _canal_passos.get_busy():
            _canal_passos.stop()
        return
    if not _canal_passos.get_busy():
        _canal_passos.play(_sons["corrida"][0], loops=-1)
    _canal_passos.set_volume(min(1.0, _passos))


# ------------------------------------------------------------------ musica
def tocar_musica():
    if not musica_ligada or not os.path.exists(TEMA) or not pygame.mixer.get_init():
        return
    if pygame.mixer.music.get_busy():
        return
    try:
        pygame.mixer.music.load(TEMA)
        pygame.mixer.music.set_volume(VOLUME_MUSICA * volume)
        pygame.mixer.music.play(loops=-1, fade_ms=1200)
    except pygame.error:
        pass


def alternar_musica():
    """Liga/desliga a musica tema. Devolve o estado novo."""
    global musica_ligada
    musica_ligada = not musica_ligada
    if musica_ligada:
        tocar_musica()
    elif pygame.mixer.get_init():
        pygame.mixer.music.fadeout(400)
    return musica_ligada


def musica_disponivel():
    return os.path.exists(TEMA)
