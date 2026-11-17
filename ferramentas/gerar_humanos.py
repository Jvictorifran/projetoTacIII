"""Gera as folhas dos humanos a partir das folhas dos zumbis.

Roda fora do jogo, uma vez, e regrava assets/image/human*.png:

    ./venv/bin/python ferramentas/gerar_humanos.py

O humano e o mesmo desenho do zumbi "curado": a pele esverdeada vira pele de
gente, os olhos brancos ganham pupila e uma peca de roupa ou o cabelo troca de
cor, pra pessoa nao ser confundida com o zumbi que nasceu da mesma folha.
Assim humano e zumbi tem exatamente o mesmo traco e a mesma animacao.
"""

import colorsys
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

QUADRO = 256                # lado de cada quadro na folha
RAIZ = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "image"
)

# faixa de cor da pele de zumbi nas folhas (matiz 0..1, luz maxima)
PELE_MATIZ = (0.44, 0.56)
PELE_LUZ_MAX = 0.55         # acima disso e lente de oculos, nao pele
PELE_LUZ_BASE = 0.33        # luz tipica da pele do zumbi

PUPILA = (38, 28, 34)

# cada humano: folha de origem, tom de pele (matiz, saturacao, luz) e trocas de
# cor extras no formato (matiz_min, matiz_max, nova_matiz, escala_luz, escala_sat)
HUMANOS = (
    {"origem": "zombie1.png", "pele": (0.070, 0.62, 0.74),      # garoto
     "trocas": ((0.57, 0.72, 0.11, 1.75, 1.0),)},               # camisa azul -> amarela
    {"origem": "zombie2.png", "pele": (0.065, 0.50, 0.63),      # policial
     "trocas": ()},
    {"origem": "zombie4.png", "pele": (0.060, 0.48, 0.45),      # grandalhao
     "trocas": ((0.57, 0.72, 0.36, 1.15, 0.7),)},               # calca azul -> verde
    {"origem": "zombie5.png", "pele": (0.075, 0.66, 0.79),      # garota
     "trocas": ((0.035, 0.18, 0.055, 0.5, 0.75),)},             # cabelo loiro -> castanho
)


def _recolorir(dados, pele, trocas):
    """Troca a pele de zumbi por pele de gente, mantendo luz e sombra do desenho."""
    matiz_pele, sat_pele, luz_pele = pele
    for i in range(0, len(dados), 4):
        if dados[i + 3] == 0:
            continue
        h, l, s = colorsys.rgb_to_hls(dados[i] / 255, dados[i + 1] / 255, dados[i + 2] / 255)
        if s < 0.12:
            continue                    # cinza, preto e branco ficam como estao
        if PELE_MATIZ[0] <= h <= PELE_MATIZ[1] and l <= PELE_LUZ_MAX:
            # a luz relativa do pixel se mantem: contorno segue escuro, brilho claro
            l = min(0.9, luz_pele * (l / PELE_LUZ_BASE) ** 0.8)
            h, s = matiz_pele, sat_pele
        else:
            for h0, h1, nova, esc_luz, esc_sat in trocas:
                if h0 <= h <= h1:
                    h, l, s = nova, min(0.92, l * esc_luz), min(1.0, s * esc_sat)
                    break
            else:
                continue
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        dados[i], dados[i + 1], dados[i + 2] = round(r * 255), round(g * 255), round(b * 255)


def _olhos(folha, x0):
    """Caixas dos olhos de um quadro: manchas brancas redondas na altura da cabeca."""
    visto = set()
    achados = []

    def branco(x, y):
        c = folha.get_at((x0 + x, y))
        return c.a > 200 and min(c.r, c.g, c.b) > 215

    for y in range(QUADRO // 2):
        for x in range(QUADRO):
            if (x, y) in visto or not branco(x, y):
                continue
            pilha, pontos = [(x, y)], []
            visto.add((x, y))
            while pilha:
                px, py = pilha.pop()
                pontos.append((px, py))
                for viz in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
                    if (0 <= viz[0] < QUADRO and 0 <= viz[1] < QUADRO
                            and viz not in visto and branco(*viz)):
                        visto.add(viz)
                        pilha.append(viz)
            xs, ys = [p[0] for p in pontos], [p[1] for p in pontos]
            larg, alt = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            # ate 2.6 de proporcao: o grandalhao corre de olho meio fechado
            redondo = 0.6 <= larg / alt <= 2.6 and len(pontos) >= 0.6 * larg * alt
            if 60 <= len(pontos) <= 700 and redondo and (min(ys) + max(ys)) / 2 < 126:
                achados.append((min(xs), min(ys), larg, alt))
    return achados


def _pupilas(folha):
    """Zumbi tem o olho todo branco; gente tem pupila, olhando pra frente."""
    for q in range(folha.get_width() // QUADRO):
        for x, y, larg, alt in _olhos(folha, q * QUADRO):
            raio = max(2.6, min(larg, alt) * 0.3)
            cx = q * QUADRO + x + larg * 0.58
            cy = y + alt * 0.52
            pygame.draw.circle(folha, PUPILA, (cx, cy), raio)
            pygame.draw.circle(folha, (255, 255, 255),
                               (cx + raio * 0.35, cy - raio * 0.35), max(1.0, raio * 0.3))


def gerar():
    print("humanos:")
    for n, ficha in enumerate(HUMANOS, start=1):
        origem = pygame.image.load(os.path.join(RAIZ, ficha["origem"])).convert_alpha()
        dados = bytearray(pygame.image.tobytes(origem, "RGBA"))
        _recolorir(dados, ficha["pele"], ficha["trocas"])
        folha = pygame.image.frombytes(bytes(dados), origem.get_size(), "RGBA").convert_alpha()
        _pupilas(folha)
        destino = os.path.join(RAIZ, f"human{n}.png")
        pygame.image.save(folha, destino)
        print(f"  human{n}.png  <- {ficha['origem']}")


if __name__ == "__main__":
    pygame.init()
    pygame.display.set_mode((1, 1))
    gerar()
    pygame.quit()
