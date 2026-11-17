"""Efeitos sonoros: carrega os WAV de assets/sons e toca pelo nome.

Sem placa de som, ou sem os arquivos, tudo aqui vira um "nao faz nada": o
jogo roda igual, so que mudo. Os WAV saem de `ferramentas/gerar_sons.py`.
"""

import os

import pygame

RAIZ = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sons"
)

# volume de cada efeito (os que tocam muito ficam mais baixos)
VOLUMES = {
    "pulo": 0.45,
    "moeda": 0.40,
    "mordida": 0.60,
    "batida": 0.75,
    "parede": 0.80,
    "explosao": 0.80,
    "poder": 0.65,
    "fim": 0.75,
    "clique": 0.50,
}
# o mesmo efeito nao recomeca antes disso: 20 moedas pegas no mesmo quadro
# viram um "plim" so, e nao um chiado
INTERVALO_MS = 60

ligado = True
_sons = {}
_ultimo = {}


def preparar():
    """Chamar antes do pygame.init(): buffer pequeno = som sem atraso."""
    pygame.mixer.pre_init(44100, -16, 2, 512)


def carregar():
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init()
        except pygame.error:
            return                  # sem saida de audio: segue mudo
    for nome, volume in VOLUMES.items():
        caminho = os.path.join(RAIZ, nome + ".wav")
        if not os.path.exists(caminho):
            continue
        try:
            som = pygame.mixer.Sound(caminho)
        except pygame.error:
            continue
        som.set_volume(volume)
        _sons[nome] = som


def disponivel():
    return bool(_sons)


def tocar(nome):
    if not ligado:
        return
    som = _sons.get(nome)
    if som is None:
        return
    agora = pygame.time.get_ticks()
    if agora - _ultimo.get(nome, -INTERVALO_MS) < INTERVALO_MS:
        return
    _ultimo[nome] = agora
    som.play()


def alternar():
    """Liga/desliga os efeitos. Devolve o estado novo."""
    global ligado
    ligado = not ligado
    if not ligado and pygame.mixer.get_init():
        pygame.mixer.stop()
    return ligado
