"""Gera as folhas de sprite dos humanos e dos poderes.

Roda fora do jogo, uma vez, e grava os PNG em assets/image:

    ./venv/bin/python ferramentas/gerar_sprites.py

Tudo e desenhado numa superficie SUPER vezes maior e reduzido no fim. E isso
que da o contorno macio do estilo cartoon das folhas de zumbi que ja existiam.

Convencao: todas as funcoes daqui recebem coordenadas e tamanhos no espaco do
quadro final (256x256). A multiplicacao por SUPER acontece so dentro das
primitivas de desenho.
"""

import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

QUADRO = 256                # lado de cada quadro na folha final
QUADROS = 5                 # quadros do ciclo de corrida (igual aos zumbis)
ICONE = 128                 # lado dos sprites de poder
SUPER = 4                   # fator de supersampling
PRETO = (34, 26, 32)
CONTORNO = 4.5              # espessura do contorno, em pixels do quadro final

RAIZ = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "image"
)


# --------------------------------------------------------------- primitivas
def _e(v):
    return v * SUPER


def _ep(ponto_):
    return (ponto_[0] * SUPER, ponto_[1] * SUPER)


def _eps(pontos):
    return [_ep(q) for q in pontos]


def andar(origem, angulo, comprimento):
    """Anda `comprimento` a partir de `origem` no `angulo` (0 = direita)."""
    return (origem[0] + math.cos(angulo) * comprimento,
            origem[1] + math.sin(angulo) * comprimento)


def capsula(surf, a, b, raio, cor):
    pygame.draw.line(surf, cor, _ep(a), _ep(b), int(_e(raio) * 2))
    pygame.draw.circle(surf, cor, _ep(a), _e(raio))
    pygame.draw.circle(surf, cor, _ep(b), _e(raio))


def bola(surf, centro, raio, cor):
    pygame.draw.circle(surf, cor, _ep(centro), _e(raio))


def bola_contornada(surf, centro, raio, cor):
    bola(surf, centro, raio + CONTORNO, PRETO)
    bola(surf, centro, raio, cor)


def elipse(surf, centro, rx, ry, cor):
    r = pygame.Rect(0, 0, int(_e(rx) * 2), int(_e(ry) * 2))
    r.center = (int(_e(centro[0])), int(_e(centro[1])))
    pygame.draw.ellipse(surf, cor, r)


def elipse_contornada(surf, centro, rx, ry, cor):
    elipse(surf, centro, rx + CONTORNO, ry + CONTORNO, PRETO)
    elipse(surf, centro, rx, ry, cor)


def poligono(surf, pontos, cor):
    pygame.draw.polygon(surf, cor, _eps(pontos))


def poligono_contornado(surf, pontos, cor):
    pts = _eps(pontos)
    pygame.draw.polygon(surf, PRETO, pts)
    pygame.draw.lines(surf, PRETO, True, pts, int(_e(CONTORNO) * 2))
    pygame.draw.polygon(surf, cor, pts)


def membro(surf, base, ang1, ang2, c1, c2, raio, cor, cor_ponta=None, raio_ponta=None):
    """Braco ou perna: duas capsulas mais a ponta (mao ou sapato).

    O contorno inteiro sai antes do preenchimento: do contrario o contorno da
    canela cobriria a coxa ja pintada e o membro ficaria partido ao meio.
    """
    meio = andar(base, ang1, c1)
    fim = andar(meio, ang2, c2)
    ponta = andar(fim, ang2, raio * 0.35)
    rp = raio_ponta if raio_ponta is not None else raio * 1.05

    capsula(surf, base, meio, raio + CONTORNO, PRETO)
    capsula(surf, meio, fim, raio * 0.88 + CONTORNO, PRETO)
    if cor_ponta:
        bola(surf, ponta, rp + CONTORNO, PRETO)
    capsula(surf, base, meio, raio, cor)
    capsula(surf, meio, fim, raio * 0.88, cor)
    if cor_ponta:
        bola(surf, ponta, rp, cor_ponta)
    return fim


def escurecer(cor, f=0.72):
    return tuple(max(0, min(255, int(c * f))) for c in cor[:3])


def clarear(cor, f=0.3):
    return tuple(int(c + (255 - c) * f) for c in cor[:3])


def nova_tela(lado=QUADRO):
    return pygame.Surface((lado * SUPER, lado * SUPER), pygame.SRCALPHA)


def reduzir(grande, lado=QUADRO):
    return pygame.transform.smoothscale(grande, (lado, lado))


def salvar(surf, nome):
    pygame.image.save(surf, os.path.join(RAIZ, nome))
    print(f"  {nome:22s} {surf.get_width()}x{surf.get_height()}")


# ------------------------------------------------------------------ humanos
# Cada tipo e so uma paleta mais um corte de cabelo: a pose vem toda do ciclo.
HUMANOS = [
    dict(pele=(246, 205, 172), roupa=(72, 120, 208), calca=(58, 72, 116),
         sapato=(236, 240, 246), cabelo=(96, 62, 40), corte="curto"),
    dict(pele=(250, 214, 186), roupa=(226, 96, 128), calca=(122, 74, 156),
         sapato=(250, 250, 250), cabelo=(238, 196, 96), corte="longo"),
    dict(pele=(176, 122, 86), roupa=(220, 220, 226), calca=(52, 54, 66),
         sapato=(60, 52, 56), cabelo=(38, 32, 34), corte="social"),
    dict(pele=(240, 198, 164), roupa=(244, 200, 72), calca=(88, 160, 96),
         sapato=(228, 92, 72), cabelo=(214, 118, 60), corte="tigela"),
]


def arco(centro, raio, a0, a1, n=9):
    """Pontos sobre um arco de circulo, em graus (0 = direita, 270 = topo)."""
    return [andar(centro, math.radians(a0 + (a1 - a0) * i / (n - 1)), raio)
            for i in range(n)]


def _cabelo(surf, centro, r, estilo, cor):
    """Faixa de cabelo por cima da cabeca, montada sobre dois arcos.

    A borda de fora carrega o estilo (espetos, franja reta, liso) e a de
    dentro acompanha o cranio, entao o cabelo nunca invade o rosto.
    """
    if estilo == "longo":
        capsula(surf, andar(centro, math.radians(200), r * 0.8),
                andar(centro, math.radians(110), r * 1.75), r * 0.38 + CONTORNO, PRETO)
        capsula(surf, andar(centro, math.radians(200), r * 0.8),
                andar(centro, math.radians(110), r * 1.75), r * 0.38, cor)

    if estilo == "curto":      # espetos, como o cabelo dos zumbis
        fora = arco(centro, r * 1.06, 195, 345, 11)
        for i in range(1, len(fora), 2):
            fora[i] = andar(centro, math.radians(195 + 150 * i / 10), r * 1.34)
    elif estilo == "tigela":   # franja reta na testa
        fora = arco(centro, r * 1.12, 185, 355, 9)
    else:                      # liso, colado no cranio
        fora = arco(centro, r * 1.05, 200, 350, 9)

    dentro = arco(centro, r * 0.78, 350, 200, 9)
    if estilo == "tigela":
        dentro = arco(centro, r * 0.72, 345, 195, 9)
    poligono_contornado(surf, fora + dentro, cor)


def _rosto(surf, centro, r, pele):
    cx, cy = centro
    # olhos grandes e brancos, como nas folhas de zumbi
    for dx, raio in ((0.04, 0.24), (0.46, 0.28)):
        bola(surf, (cx + r * dx, cy), r * raio + CONTORNO * 0.7, PRETO)
        bola(surf, (cx + r * dx, cy), r * raio, (255, 255, 255))
        bola(surf, (cx + r * dx + r * 0.08, cy + r * 0.04), r * raio * 0.44, (30, 26, 34))
    # nariz na silhueta, pra leitura de perfil
    bola(surf, (cx + r * 0.88, cy + r * 0.28), r * 0.14 + CONTORNO * 0.6, PRETO)
    bola(surf, (cx + r * 0.88, cy + r * 0.28), r * 0.14, escurecer(pele, 0.95))
    # boca aberta: o humano esta gritando
    elipse_contornada(surf, (cx + r * 0.46, cy + r * 0.62), r * 0.22, r * 0.19, (126, 54, 60))


def quadro_humano(tipo, i):
    """Um quadro do ciclo de corrida, virado pra direita."""
    surf = nova_tela()
    fase = i / QUADROS * math.tau
    passo = math.sin(fase)
    pele, roupa = tipo["pele"], tipo["roupa"]
    calca, sapato = tipo["calca"], tipo["sapato"]

    balanco = abs(math.sin(fase)) * 6          # o corpo sobe e desce no passo
    quadril_y = 160 - balanco
    ombro_y = 116 - balanco
    quadril = (124, quadril_y)
    ombro = (128, ombro_y)

    def perna(ang, cor_calca, cor_sapato, raio):
        ang2 = ang + (0.5 if passo < 0 else -0.3)
        pe = membro(surf, quadril, ang, ang2, 34, 32, raio, cor_calca)
        elipse_contornada(surf, andar(pe, ang2, 5), 15, 9, cor_sapato)

    def braco(ang, cor_manga, cor_mao, raio):
        mao = membro(surf, ombro, ang, ang - 0.85, 26, 23, raio, cor_manga)
        bola_contornada(surf, mao, raio * 1.3, cor_mao)

    # membros de tras primeiro: os da frente cobrem e dao a profundidade
    perna(math.pi / 2 - 0.85 * passo, escurecer(calca, 0.68), escurecer(sapato, 0.68), 10)
    braco(math.pi / 2 - 0.55 - 0.65 * passo, escurecer(roupa, 0.68), escurecer(pele, 0.68), 8)

    # tronco, inclinado pra frente
    poligono_contornado(surf, [
        (112, ombro_y - 10), (150, ombro_y - 6),
        (152, quadril_y + 4), (106, quadril_y + 4)], roupa)
    if tipo["corte"] == "social":      # gravata do executivo
        poligono(surf, [(134, ombro_y - 6), (146, ombro_y - 4),
                        (139, quadril_y - 6)], (196, 60, 60))
    poligono(surf, [(106, quadril_y - 10), (152, quadril_y - 8),
                    (152, quadril_y + 4), (106, quadril_y + 4)], escurecer(calca, 0.9))

    perna(math.pi / 2 + 0.85 * passo, calca, sapato, 11)

    # cabeca
    centro = (134, ombro_y - 44)
    bola_contornada(surf, centro, 36, pele)
    bola_contornada(surf, (112, ombro_y - 38), 8, escurecer(pele, 0.94))
    _cabelo(surf, centro, 36, tipo["corte"], tipo["cabelo"])
    _rosto(surf, centro, 36, pele)

    braco(math.pi / 2 - 0.55 + 0.65 * passo, roupa, pele, 9)
    return reduzir(surf)


def gerar_humanos():
    print("humanos:")
    for n, tipo in enumerate(HUMANOS, start=1):
        folha = pygame.Surface((QUADRO * QUADROS, QUADRO), pygame.SRCALPHA)
        for i in range(QUADROS):
            folha.blit(quadro_humano(tipo, i), (i * QUADRO, 0))
        salvar(folha, f"human{n}.png")


# ------------------------------------------------------------------ poderes
def _icone_gigante():
    """Cabecao de zumbi entre setas: a horda cresce."""
    surf = nova_tela(ICONE)
    verde = (120, 196, 96)
    bola_contornada(surf, (64, 74), 40, verde)
    bola(surf, (48, 58), 15, clarear(verde, 0.24))
    poligono_contornado(surf, [(26, 52), (36, 26), (50, 44), (64, 22),
                               (78, 44), (92, 28), (100, 54),
                               (64, 40)], (72, 132, 66))     # topete
    for dx, raio in ((-15, 13), (16, 15)):                   # olhos esbugalhados
        bola(surf, (64 + dx, 74), raio + CONTORNO * 0.7, PRETO)
        bola(surf, (64 + dx, 74), raio, (255, 255, 255))
        bola(surf, (64 + dx + 4, 77), raio * 0.45, (30, 26, 34))
    elipse_contornada(surf, (64, 104), 17, 9, (140, 50, 58)) # boca aberta
    for lado in (-1, 1):                                     # setas de crescimento
        x = 64 + lado * 52
        poligono_contornado(surf, [(x, 12), (x + lado * 14, 30), (x + lado * 6, 30),
                                   (x + lado * 6, 44), (x - lado * 4, 44),
                                   (x - lado * 4, 30), (x - lado * 12, 30)],
                            (250, 214, 92))
    return reduzir(surf, ICONE)


def _icone_dragao():
    """Cabeca de dragao de perfil, cuspindo fogo."""
    surf = nova_tela(ICONE)
    corpo, barriga = (96, 184, 104), (206, 226, 150)
    poligono_contornado(surf, [(22, 44), (34, 22), (46, 40), (62, 32),
                               (74, 44), (70, 60), (30, 66)], (228, 214, 132))
    bola_contornada(surf, (52, 62), 28, corpo)          # cranio
    poligono_contornado(surf, [(58, 44), (108, 50), (114, 62),
                               (96, 66), (58, 68)], corpo)   # focinho
    poligono_contornado(surf, [(60, 74), (104, 72), (98, 86), (60, 86)], barriga)
    for x in (78, 90):                                  # presas
        poligono(surf, [(x, 66), (x + 9, 66), (x + 4, 76)], (255, 255, 255))
    bola(surf, (66, 54), 11, (255, 255, 255))
    bola(surf, (69, 56), 5, (32, 28, 34))
    bola(surf, (104, 56), 3, (40, 34, 38))              # narina
    poligono_contornado(surf, [(110, 58), (128, 44), (118, 62), (128, 74),
                               (108, 70)], (250, 176, 60))   # labareda
    poligono(surf, [(112, 60), (124, 52), (117, 63), (124, 70), (111, 67)],
             (252, 232, 120))
    return reduzir(surf, ICONE)


def _icone_balao():
    """Balao com barbante: o poder que faz a horda flutuar."""
    surf = nova_tela(ICONE)
    vermelho = (228, 76, 84)
    pontos = [(64, 106)]
    for i in range(9):                                  # barbante ondulado
        t = i / 8
        pontos.append((64 + math.sin(t * 7) * 9, 106 + t * 20))
    pygame.draw.lines(surf, PRETO, False, _eps(pontos), int(_e(3.4)))
    elipse_contornada(surf, (64, 58), 34, 40, vermelho)
    poligono_contornado(surf, [(56, 94), (72, 94), (64, 108)], vermelho)
    elipse(surf, (50, 42), 10, 14, clarear(vermelho, 0.55))
    return reduzir(surf, ICONE)


def _icone_ima():
    """Ima de ferradura: puxa as moedas de longe."""
    surf = nova_tela(ICONE)
    centro, re, ri = (64, 62), 38, 21
    corpo = arco(centro, re, 180, 360, 15) + [(64 + re, 96), (64 + ri, 96)] + \
        arco(centro, ri, 360, 180, 15) + [(64 - ri, 96), (64 - re, 96)]
    poligono_contornado(surf, corpo, (216, 68, 68))
    for lado in (-1, 1):                                # polos prateados
        poligono_contornado(surf, [(64 + lado * re, 78), (64 + lado * ri, 78),
                                   (64 + lado * ri, 98), (64 + lado * re, 98)],
                            (218, 222, 230))
    elipse(surf, (46, 34), 6, 9, clarear((216, 68, 68), 0.45))   # brilho
    return reduzir(surf, ICONE)


def _sprite_asas():
    """Par de asas desenhado atras de cada zumbi durante o poder do dragao."""
    lado = 192
    surf = nova_tela(lado)
    membrana, osso = (146, 92, 196), (206, 166, 244)
    for s_ in (-1, 1):
        cx = lado / 2
        pontos = [(cx, 104), (cx + s_ * 26, 40), (cx + s_ * 62, 24),
                  (cx + s_ * 54, 54), (cx + s_ * 84, 52), (cx + s_ * 70, 78),
                  (cx + s_ * 88, 88), (cx + s_ * 56, 100), (cx + s_ * 30, 112)]
        poligono_contornado(surf, pontos, membrana)
        for alvo in ((54, 62), (84, 60), (88, 92)):
            pygame.draw.line(surf, osso, _ep((cx + s_ * 8, 96)),
                             _ep((cx + s_ * alvo[0], alvo[1])), int(_e(3.2)))
    return reduzir(surf, lado)


def _sprite_caixa():
    """A caixa que carrega o poder: caixote de madeira com cantoneira dourada."""
    surf = nova_tela(ICONE)
    madeira, tabua, ouro = (166, 110, 60), (196, 140, 82), (211, 175, 55)
    poligono_contornado(surf, [(14, 20), (114, 20), (114, 114), (14, 114)], madeira)
    for y in (38, 62, 86):                              # frestas entre as tabuas
        pygame.draw.line(surf, escurecer(madeira, 0.72), _ep((18, y)), _ep((110, y)),
                         int(_e(3.0)))
    for y in (28, 52, 76, 100):
        pygame.draw.line(surf, tabua, _ep((20, y)), _ep((108, y)), int(_e(4.0)))
    for x in (14, 102):                                 # cantoneiras de metal
        poligono_contornado(surf, [(x, 20), (x + 12, 20), (x + 12, 114), (x, 114)], ouro)
        for y in (30, 100):
            bola(surf, (x + 6, y), 3.5, escurecer(ouro, 0.6))
    return reduzir(surf, ICONE)


ICONES = {
    "gigante": _icone_gigante,
    "dragao": _icone_dragao,
    "balao": _icone_balao,
    "ima": _icone_ima,
}


def gerar_poderes():
    print("poderes:")
    for nome, desenhar in ICONES.items():
        salvar(desenhar(), f"poder_{nome}.png")
    salvar(_sprite_asas(), "asas.png")
    salvar(_sprite_caixa(), "caixa.png")


if __name__ == "__main__":
    pygame.init()
    os.makedirs(RAIZ, exist_ok=True)
    # os humanos agora saem das folhas de zumbi (ferramentas/gerar_humanos.py);
    # chamar gerar_humanos() aqui regravaria os human*.png com o traco antigo
    gerar_poderes()
    pygame.quit()
