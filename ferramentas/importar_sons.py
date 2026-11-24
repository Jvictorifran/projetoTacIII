"""Monta os efeitos sonoros e a musica do jogo a partir de sons CC0 baixados da web.

Uso:
    ./venv/bin/python ferramentas/importar_sons.py /pasta/com/os/downloads

A pasta deve ter os arquivos e os zips extraidos com os nomes originais (veja
a coluna `arquivo` da tabela `SONS` e o `CREDITOS.md`, que diz de onde vem
cada um). Cada efeito pode ser uma ou mais camadas: um trecho de um arquivo,
com atraso e ganho proprios, misturadas e normalizadas num WAV mono de 16 bits
em `assets/sons/`. Nomes com `_1`, `_2`... sao variacoes que o jogo sorteia.

O pygame decodifica qualquer formato (ogg, mp3, wav); o corte, a mistura e o
fade sao feitos a mao com `array`, sem dependencia nova.
"""

import array
import os
import shutil
import sys
import wave

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

TAXA = 44100
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "assets", "sons")
MUSICA = os.path.join(RAIZ, "assets", "musica")

# camada = (arquivo, inicio_s, duracao_s, atraso_s, ganho)
# efeito = (camadas, pico_final, fade_s)
SONS = {
    "pulo": ([("RPGsounds_Kenney/OGG/cloth1.ogg", 0.0, 0.30, 0.0, 1.0)], 0.55, 0.06),
    "moeda": ([("RPGsounds_Kenney/OGG/handleCoins.ogg", 0.04, 0.32, 0.0, 1.0)], 0.6, 0.08),
    "mordida": ([("crunch_-_tito/crunch.4.ogg", 0.11, 0.45, 0.0, 1.0),
                 ("crunchybite.ogg", 0.0, 0.29, 0.02, 0.8)], 0.9, 0.08),
    "zumbi_1": ([("01_zombey.mp3", 0.03, 1.0, 0.0, 1.0)], 0.8, 0.15),
    "zumbi_2": ([("03_zombey.mp3", 0.03, 1.0, 0.0, 1.0)], 0.8, 0.15),
    "zumbi_3": ([("04_zombey_0.mp3", 0.03, 1.1, 0.0, 1.0)], 0.8, 0.15),
    "zumbi_4": ([("06_zombey.mp3", 0.04, 1.2, 0.0, 1.0)], 0.8, 0.15),
    "grito_1": ([("female_scream_1.ogg", 0.58, 1.20, 0.0, 1.0)], 0.75, 0.25),
    "grito_2": ([("high_pitch_scream.mp3", 0.02, 1.30, 0.0, 1.0)], 0.6, 0.35),
    "batida": ([("qubodup-crash.ogg", 0.0, 0.58, 0.0, 1.0),
                ("sfx_breaking_and_falling/bfh1_metal_hit_01.ogg", 0.0, 0.24, 0.0, 0.7)], 0.85, 0.08),
    "quebra": ([("glass_breaking.wav", 0.0, 1.10, 0.05, 1.0),
                ("sfx_breaking_and_falling/bfh1_metal_falling_01.ogg", 0.10, 0.90, 0.0, 0.8)], 0.9, 0.3),
    "parede": ([("sfx_breaking_and_falling/bfh1_hit_03.ogg", 0.0, 0.45, 0.0, 1.0)], 0.85, 0.1),
    "explosao": ([("mechanical_explosion.wav", 0.0, 1.36, 0.0, 1.0)], 0.9, 0.3),
    "poder": ([("Digital_SFX_Set/powerUp1.mp3", 0.04, 1.0, 0.0, 1.0)], 0.6, 0.15),
    "fim": ([("Digital_SFX_Set/lowThreeTone.mp3", 0.03, 0.93, 0.0, 1.0),
             ("07_zombey.mp3", 0.01, 1.45, 0.35, 0.9)], 0.8, 0.3),
    "clique": ([("kenney_interfaceSounds/Audio/select_001.ogg", 0.0, 0.05, 0.0, 1.0)], 0.5, 0.01),
}
# passos de corrida: os 10 passos do pacote RPG do Kenney em sequencia viram
# um loop de 1,6 s que toca enquanto a horda corre no chao
PASSOS = [f"RPGsounds_Kenney/OGG/footstep0{i}.ogg" for i in range(10)]
PASSO_INTERVALO = 0.16
TEMA = "hallow_quest_2.mp3"     # Spooky Action Loop ("Hallow Quest"), Zane Little


def amostras(origem, arquivo, inicio, duracao):
    som = pygame.mixer.Sound(os.path.join(origem, arquivo))
    a = array.array("h", som.get_raw())
    ini = int(inicio * TAXA)
    return a[ini:ini + int(duracao * TAXA)]


def misturar(camadas, total):
    mix = [0.0] * total
    for a, atraso, ganho in camadas:
        base = int(atraso * TAXA)
        for i, v in enumerate(a):
            if base + i < total:
                mix[base + i] += v * ganho
    return mix


def acabar(mix, pico_final, fade):
    pico = max((abs(v) for v in mix), default=0) or 1.0
    k = pico_final * 32767 / pico
    n = len(mix)
    fade_n = max(1, int(fade * TAXA))
    ataque = int(0.004 * TAXA)              # evita estalo no comeco
    saida = array.array("h")
    for i, v in enumerate(mix):
        env = 1.0
        if i < ataque:
            env = i / ataque
        if i > n - fade_n:
            env *= max(0.0, (n - i) / fade_n)
        saida.append(max(-32767, min(32767, int(v * k * env))))
    return saida


def gravar(nome, dados):
    caminho = os.path.join(SAIDA, nome + ".wav")
    with wave.open(caminho, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(dados.tobytes())
    print(f"{nome:10s} {len(dados) / TAXA:5.2f} s")


def main(origem):
    pygame.mixer.init(TAXA, -16, 1)
    os.makedirs(SAIDA, exist_ok=True)
    for nome, (camadas, pico, fade) in SONS.items():
        trechos = [(amostras(origem, arq, ini, dur), atraso, ganho)
                   for arq, ini, dur, atraso, ganho in camadas]
        total = max(int(atraso * TAXA) + len(a) for a, atraso, _ in trechos)
        gravar(nome, acabar(misturar(trechos, total), pico, fade))

    passos = []
    for i, arq in enumerate(PASSOS):
        passos.append((amostras(origem, arq, 0.0, 0.3), i * PASSO_INTERVALO, 1.0 if i % 2 else 0.8))
    total = int(len(PASSOS) * PASSO_INTERVALO * TAXA)
    gravar("corrida", acabar(misturar(passos, total), 0.7, 0.0))

    os.makedirs(MUSICA, exist_ok=True)
    shutil.copyfile(os.path.join(origem, TEMA), os.path.join(MUSICA, "tema.mp3"))
    print("musica   -> assets/musica/tema.mp3")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
