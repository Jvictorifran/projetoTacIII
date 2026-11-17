"""Gera os fundos do jogo em SVG, um conjunto de tres camadas por cenario.

Roda fora do jogo, uma vez, e grava em assets/fundos:

    ./venv/bin/python ferramentas/gerar_fundos.py

Cada cenario vira tres arquivos:

    <nome>_ceu.svg     960x540, opaco, fica parado
    <nome>_longe.svg  1920x540, transparente, rola devagar
    <nome>_perto.svg  1920x540, transparente, rola mais rapido

Alem dos cenarios sai o tunel que fica na divisa entre dois deles, em duas
camadas de 800x540: `tunel_fundo.svg` (o interior, atras da horda) e
`tunel_frente.svg` (a rocha e o arco de pedra, na frente dela).

As camadas que rolam se repetem na horizontal, entao a borda esquerda tem que
casar com a direita: os morros usam ondas com periodo inteiro na largura e os
objetos soltos (predio, arvore, cacto) nunca atravessam a borda.

O SVG e lido pelo pygame (nanosvg), que nao entende <use>, filtros, mascaras
nem texto. Por isso aqui so sai forma basica, gradiente e opacidade.
"""

import math
import os
import random

LARG = 1920                 # largura das camadas que rolam (duas telas)
TELA = 960                  # largura do ceu
ALT = 540
CHAO = 430                  # linha do chao do jogo: abaixo dela nada aparece

RAIZ = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fundos"
)


# ------------------------------------------------------------------- svg
def n(v):
    """Numero curto: uma casa decimal, sem '.0' sobrando."""
    txt = f"{v:.1f}"
    return txt[:-2] if txt.endswith(".0") else txt


class Svg:
    def __init__(self, largura):
        self.largura = largura
        self.defs = []
        self.corpo = []

    @staticmethod
    def _paradas(paradas):
        saida = []
        for p in paradas:
            opacidade = p[2] if len(p) > 2 else 1
            saida.append(f'<stop offset="{n(p[0] * 100)}%" stop-color="{p[1]}" '
                         f'stop-opacity="{opacidade:.2f}"/>')
        return "".join(saida)

    def gradiente(self, y1, y2, paradas):
        """Gradiente vertical entre y1 e y2. Paradas: (posicao, cor[, opacidade])."""
        gid = f"g{len(self.defs)}"
        self.defs.append(
            f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" '
            f'y1="{n(y1)}" x2="0" y2="{n(y2)}">{self._paradas(paradas)}</linearGradient>')
        return f"url(#{gid})"

    def brilho(self, cx, cy, r, paradas):
        """Gradiente radial, pro halo de lua, sol e luzes."""
        gid = f"g{len(self.defs)}"
        self.defs.append(
            f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="{n(cx)}" '
            f'cy="{n(cy)}" r="{n(r)}">{self._paradas(paradas)}</radialGradient>')
        return f"url(#{gid})"

    def forma(self, tag, **attrs):
        txt = " ".join(
            f'{k.replace("_", "-")}="{n(v) if isinstance(v, (int, float)) else v}"'
            for k, v in attrs.items())
        self.corpo.append(f"<{tag} {txt}/>")

    def ret(self, x, y, larg, alt, fill, **kw):
        self.forma("rect", x=x, y=y, width=larg, height=alt, fill=fill, **kw)

    def circ(self, cx, cy, r, fill, **kw):
        self.forma("circle", cx=cx, cy=cy, r=r, fill=fill, **kw)

    def elipse(self, cx, cy, rx, ry, fill, **kw):
        self.forma("ellipse", cx=cx, cy=cy, rx=rx, ry=ry, fill=fill, **kw)

    def poligono(self, pontos, fill, **kw):
        self.forma("polygon", points=" ".join(f"{n(x)},{n(y)}" for x, y in pontos),
                   fill=fill, **kw)

    def linha(self, pontos, cor, espessura, **kw):
        self.forma("polyline", points=" ".join(f"{n(x)},{n(y)}" for x, y in pontos),
                   fill="none", stroke=cor, stroke_width=espessura,
                   stroke_linecap="round", stroke_linejoin="round", **kw)

    def caminho(self, d, fill, **kw):
        self.forma("path", d=d, fill=fill, **kw)

    def salvar(self, nome):
        destino = os.path.join(RAIZ, nome)
        with open(destino, "w", encoding="utf-8") as arq:
            arq.write(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.largura}" '
                f'height="{ALT}" viewBox="0 0 {self.largura} {ALT}">\n'
                f'<defs>{"".join(self.defs)}</defs>\n'
                + "\n".join(self.corpo) + "\n</svg>\n")
        print(f"  {nome}  ({os.path.getsize(destino) // 1024} KB)")


# ------------------------------------------------------- pecas em comum
def estrelas(s, rng, quantidade, y_max, cor="#ffffff", forca=1.0):
    """Ceu estrelado: mais denso no alto, com algumas estrelas de halo."""
    for _ in range(quantidade):
        x = rng.uniform(0, s.largura)
        y = y_max * rng.random() ** 1.5
        s.circ(x, y, rng.choice((0.6, 0.8, 0.8, 1.0, 1.3)), cor,
               opacity=round(rng.uniform(0.3, 0.95) * forca, 2))
    for _ in range(quantidade // 14):
        x = rng.uniform(20, s.largura - 20)
        y = y_max * 0.8 * rng.random() ** 1.5 + 8
        s.circ(x, y, 7, s.brilho(x, y, 7, [(0, cor, 0.5 * forca), (1, cor, 0)]))
        s.circ(x, y, 1.6, cor, opacity=round(forca, 2))


def crista(rng, base, amplitude, ondas, largura=LARG):
    """Funcao de altura de um morro que emenda consigo mesmo na borda.

    Cada onda da um numero inteiro de voltas na largura: f(0) == f(largura).
    """
    partes = [(k, rng.uniform(0, math.tau), amplitude / (i + 1))
              for i, k in enumerate(ondas)]

    def altura(x):
        return base - sum(a * math.sin(math.tau * k * x / largura + f)
                          for k, f, a in partes)
    return altura


def morro(s, altura, fill, passo=12, **kw):
    pontos = [(x, altura(x)) for x in range(0, s.largura + 1, passo)]
    s.poligono(pontos + [(s.largura, ALT), (0, ALT)], fill, **kw)
    return pontos


def nuvem(s, x, y, largura, fill, **kw):
    """Nuvem cartoon num caminho so (sobrepor formas mancharia a opacidade)."""
    proporcoes = (0.55, 0.9, 1.2, 0.85, 0.5)
    escala = largura / (2 * sum(proporcoes))
    h = escala * 0.5
    d = [f"M{n(x)} {n(y)}"]
    cx = x
    for p in proporcoes:
        r = p * escala
        cx += 2 * r
        d.append(f"A{n(r)} {n(r)} 0 0 1 {n(cx)} {n(y)}")
    d.append(f"A{n(h)} {n(h)} 0 0 1 {n(cx)} {n(y + 2 * h)}")
    d.append(f"L{n(x)} {n(y + 2 * h)}")
    d.append(f"A{n(h)} {n(h)} 0 0 1 {n(x)} {n(y)}Z")
    s.caminho("".join(d), fill, **kw)


def crescente(cx, cy, r, dx, dy, r2, passos=40):
    """Contorno de lua crescente: o disco menos um segundo disco deslocado."""
    d = math.hypot(dx, dy)
    phi = math.atan2(dy, dx)
    alfa = math.acos((d * d + r * r - r2 * r2) / (2 * d * r))
    beta = math.acos((d * d + r2 * r2 - r * r) / (2 * d * r2))
    fora = []
    for i in range(passos + 1):
        a = phi + alfa + (math.tau - 2 * alfa) * i / passos
        fora.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    dentro = []
    for i in range(passos + 1):
        a = phi + math.pi - beta + 2 * beta * i / passos
        dentro.append((cx + dx + r2 * math.cos(a), cy + dy + r2 * math.sin(a)))
    # o arco de dentro tem que comecar onde o de fora terminou
    if math.dist(fora[-1], dentro[0]) > math.dist(fora[-1], dentro[-1]):
        dentro.reverse()
    return fora + dentro


def pinheiro(s, rng, x, base, h, cor, neve=None, camadas=5):
    """Pinheiro em camadas com a barra serrilhada; `neve` cobre o topo de cada uma."""
    s.ret(x - h * 0.03, base - h * 0.16, h * 0.06, h * 0.16 + 3, cor)
    passo = 0.9 * h / (camadas + 0.6)
    for i in range(camadas):
        yb = base - h * 0.1 - i * passo
        th = passo * 1.6
        hw = h * (0.05 + 0.17 * (1 - i / camadas)) * rng.uniform(0.92, 1.08)
        pontos = [(x, yb - th), (x + hw, yb)]
        for k in range(1, 6):
            pontos.append((x + hw - k * 2 * hw / 6, yb - (k % 2) * th * 0.13))
        pontos.append((x - hw, yb))
        s.poligono(pontos, cor)
        if neve:
            s.poligono([(x, yb - th), (x + hw * 0.5, yb - th * 0.5),
                        (x + hw * 0.22, yb - th * 0.36), (x + hw * 0.04, yb - th * 0.5),
                        (x - hw * 0.2, yb - th * 0.34), (x - hw * 0.5, yb - th * 0.5)],
                       neve)


# ================================================================ cidade
def cidade():
    rng = random.Random(11)
    s = Svg(TELA)
    s.ret(0, 0, TELA, ALT, s.gradiente(0, CHAO, [
        (0, "#110e25"), (0.5, "#2d2250"), (0.85, "#6a4074"), (1, "#8a4f78")]))
    estrelas(s, rng, 120, 300)
    lx, ly = 806, 98
    s.circ(lx, ly, 150, s.brilho(lx, ly, 150, [(0, "#f0ecd2", 0.28), (1, "#f0ecd2", 0)]))
    s.poligono(crescente(lx, ly, 44, -19, -12, 41), "#f4efd6")
    nuvem(s, 90, 168, 210, "#9a86c4", opacity=0.16)
    nuvem(s, 470, 118, 150, "#9a86c4", opacity=0.12)
    nuvem(s, 640, 236, 250, "#b58ac0", opacity=0.14)
    s.salvar("cidade_ceu.svg")

    # --- silhueta distante: predios colados, janelinhas apagadas
    rng = random.Random(12)
    s = Svg(LARG)
    parede = s.gradiente(190, CHAO, [(0, "#2a2246"), (1, "#5c3f6c")])
    x = 0
    while x < LARG:
        larg = rng.randint(46, 112)
        if LARG - x - larg < 46:
            larg = LARG - x
        topo = CHAO - rng.randint(70, 232)
        s.ret(x, topo, larg + 0.5, ALT - topo, parede)
        sorte = rng.random()
        if sorte < 0.18:                               # torre com agulha
            s.poligono([(x + larg * 0.5 - 7, topo), (x + larg * 0.5, topo - 44),
                        (x + larg * 0.5 + 7, topo)], "#2a2246")
        elif sorte < 0.45:                             # topo em degrau
            s.ret(x + larg * 0.22, topo - 14, larg * 0.56, 15, "#2a2246")
        for jy in range(topo + 10, CHAO - 8, 14):
            for jx in range(x + 6, x + larg - 8, 11):
                if rng.random() < 0.15:
                    s.ret(jx, jy, 4, 6, "#f6cf86", opacity=round(rng.uniform(0.3, 0.7), 2))
        x += larg
    s.salvar("cidade_longe.svg")

    # --- predios de perto: janelas acesas, antenas e caixas d'agua
    rng = random.Random(13)
    s = Svg(LARG)
    parede = s.gradiente(150, CHAO, [(0, "#191430"), (1, "#2c2144")])
    beiral, apagada = "#2b2348", "#2a2346"
    acesas = ("#fad678", "#fad678", "#ffe9a8", "#f2a65a", "#9fd8e8")
    x = rng.randint(4, 24)
    while x < LARG - 76:
        larg = min(rng.randint(72, 150), LARG - x - 6)
        topo = CHAO - rng.randint(92, 268)
        s.ret(x, topo, larg, ALT - topo, parede)
        s.ret(x - 3, topo - 1, larg + 6, 6, beiral)

        enfeite = rng.random()
        if enfeite < 0.3:                              # antena com luz de aviso
            ax = x + larg * rng.uniform(0.25, 0.75)
            ponta = topo - rng.randint(26, 54)
            s.linha([(ax, topo), (ax, ponta)], beiral, 2.5)
            s.linha([(ax - 7, ponta + 12), (ax + 7, ponta + 12)], beiral, 2)
            s.circ(ax, ponta, 9, s.brilho(ax, ponta, 9, [(0, "#ff5a6a", 0.6),
                                                         (1, "#ff5a6a", 0)]))
            s.circ(ax, ponta, 2.4, "#ff7a86")
        elif enfeite < 0.55 and larg > 84:             # caixa d'agua
            cx = x + larg * rng.uniform(0.3, 0.7)
            for lado in (-10, 10):
                s.linha([(cx + lado, topo), (cx + lado, topo - 14)], beiral, 2.5)
            s.ret(cx - 14, topo - 34, 28, 21, "#191430", rx=3)
            s.poligono([(cx - 17, topo - 33), (cx, topo - 45), (cx + 17, topo - 33)],
                       beiral)
        elif enfeite < 0.75:                           # cobertura recuada
            s.ret(x + larg * 0.2, topo - 16, larg * 0.6, 16, "#191430")
            s.ret(x + larg * 0.2 - 2, topo - 18, larg * 0.6 + 4, 4, beiral)

        largas = rng.random() < 0.35
        jl, ja, px, py = (15, 8, 24, 21) if largas else (8, 11, 21, 25)
        chance = rng.uniform(0.14, 0.48)
        margem = (larg - ((larg - 16 - jl) // px * px + jl)) / 2
        for jy in range(topo + 16, CHAO - 6, py):
            jx = x + margem
            while jx + jl <= x + larg - 7:
                if rng.random() < chance:
                    s.ret(jx, jy, jl, ja, rng.choice(acesas), rx=1)
                else:
                    s.ret(jx, jy, jl, ja, apagada, rx=1)
                jx += px
        x += larg + rng.randint(14, 58)
    s.salvar("cidade_perto.svg")


# =============================================================== deserto
def cacto(s, rng, x, base, h, cor, luz):
    esp = h * 0.17
    s.linha([(x, base), (x, base - h)], cor, esp)
    for lado in (-1, 1):
        if rng.random() < 0.8:
            y1 = base - h * rng.uniform(0.28, 0.55)
            d = esp * rng.uniform(1.5, 2.0) * lado
            s.linha([(x, y1), (x + d, y1), (x + d, y1 - h * rng.uniform(0.2, 0.36))],
                    cor, esp * 0.7)
    s.linha([(x + esp * 0.3, base - 3), (x + esp * 0.3, base - h + 2)], luz, 1.6,
            opacity=0.45)


def mesa(s, rng, x0, x1, topo, fill, luz, sombra):
    """Chapadao: paredao reto em cima e rampa de entulho embaixo."""
    h = CHAO - topo
    meio = topo + h * rng.uniform(0.5, 0.62)
    saia = h * rng.uniform(0.28, 0.42)
    pontos = [(x0 - saia, ALT), (x0 - saia, CHAO), (x0 - 8, meio), (x0 - 5, topo + 12),
              (x0, topo + 9), (x0 + 3, topo)]
    # o topo ganha um ou dois dentes pra nao ficar regua
    cx = x0 + 3
    nivel = topo
    while cx < x1 - 40 and rng.random() < 0.6:
        cx += rng.uniform(24, (x1 - x0) * 0.5)
        if cx >= x1 - 14:
            break
        pontos.append((cx, nivel))
        nivel = topo + rng.choice((0, 7, 12))
        pontos.append((cx + 2, nivel))
    pontos += [(x1 - 3, nivel), (x1, nivel + 9), (x1 + 5, nivel + 12), (x1 + 8, meio),
               (x1 + saia, CHAO), (x1 + saia, ALT)]
    s.poligono(pontos, fill)
    s.linha([(x0 + 4, topo + 1), (x1 - 4, topo + 1)], luz, 2, opacity=0.5)
    for dy in (20, 38, 54):
        if topo + dy < meio - 6:
            s.linha([(x0 - 2, topo + dy), (x1 + 2, topo + dy)], sombra, 2, opacity=0.4)


def deserto():
    rng = random.Random(21)
    s = Svg(TELA)
    s.ret(0, 0, TELA, ALT, s.gradiente(0, CHAO, [
        (0, "#1d1645"), (0.3, "#54296a"), (0.56, "#b3446c"), (0.8, "#f07f50"),
        (1, "#fcca6b")]))
    estrelas(s, rng, 60, 170, forca=0.7)
    sx, sy = 684, 348
    s.circ(sx, sy, 250, s.brilho(sx, sy, 250, [(0, "#ffe2a0", 0.6), (0.4, "#ffb070", 0.25),
                                               (1, "#ffb070", 0)]))
    s.circ(sx, sy, 62, s.gradiente(sy - 62, sy + 62, [(0, "#fff6d0"), (1, "#ffb65a")]))
    for cx, cy, rx, ry, cor, op in (
            (210, 196, 170, 7, "#4a2466", 0.45), (330, 214, 110, 5, "#4a2466", 0.4),
            (560, 150, 140, 6, "#4a2466", 0.35), (800, 240, 150, 7, "#7a3070", 0.4),
            (120, 300, 130, 6, "#c2506c", 0.4), (470, 318, 180, 7, "#ffa070", 0.35),
            (850, 330, 120, 5, "#ffc080", 0.4), (640, 372, 150, 5, "#ffd89a", 0.45)):
        s.elipse(cx, cy, rx, ry, cor, opacity=op)
    for bx, by, t in ((300, 120, 9), (332, 104, 7), (356, 128, 6)):     # passaros
        s.linha([(bx - t, by - t * 0.5), (bx, by), (bx + t, by - t * 0.5)], "#2a1840", 1.8)
    s.salvar("deserto_ceu.svg")

    # --- chapadoes distantes
    rng = random.Random(22)
    s = Svg(LARG)
    morro(s, crista(rng, 404, 12, (1, 2, 4)), "#c2596a", opacity=0.85)
    rocha = s.gradiente(210, CHAO, [(0, "#7c3766"), (1, "#b9535f")])
    x = 70
    while x < LARG - 320:
        if rng.random() < 0.3:                         # agulha de pedra
            larg = rng.randint(26, 44)
            mesa(s, rng, x, x + larg, CHAO - rng.randint(120, 190), rocha,
                 "#ffb080", "#6a2d5c")
        else:
            larg = rng.randint(120, 250)
            mesa(s, rng, x, x + larg, CHAO - rng.randint(86, 176), rocha,
                 "#ffb080", "#6a2d5c")
        x += larg + rng.randint(150, 300)
    s.salvar("deserto_longe.svg")

    # --- dunas e cactos de perto
    rng = random.Random(23)
    s = Svg(LARG)
    duna = crista(rng, 404, 15, (1, 2, 3, 5))
    cor, luz = "#33183a", "#e0688a"
    x = 50
    while x < LARG - 60:
        sorte = rng.random()
        base = duna(x) + 5
        if sorte < 0.55:
            cacto(s, rng, x, base, rng.uniform(58, 124), cor, luz)
        elif sorte < 0.8:                              # pedras
            larg = rng.uniform(34, 70)
            s.poligono([(x - larg / 2, base + 4), (x - larg * 0.34, base - larg * 0.3),
                        (x - larg * 0.05, base - larg * 0.46), (x + larg * 0.3, base - larg * 0.3),
                        (x + larg / 2, base + 4)], cor)
            s.linha([(x - larg * 0.05, base - larg * 0.46), (x + larg * 0.3, base - larg * 0.3)],
                    luz, 1.6, opacity=0.4)
        else:                                          # arbusto seco
            for _ in range(7):
                ang = rng.uniform(-2.7, -0.45)
                comp = rng.uniform(16, 34)
                s.linha([(x, base), (x + math.cos(ang) * comp, base + math.sin(ang) * comp)],
                        cor, 2.2)
        x += rng.uniform(120, 260)
    morro(s, duna, s.gradiente(384, CHAO, [(0, "#4b2247"), (1, "#2a1530")]))
    s.linha([(x, duna(x) + 1) for x in range(0, LARG + 1, 12)], luz, 1.6, opacity=0.3)
    s.salvar("deserto_perto.svg")


# ============================================================== floresta
def arvore_seca(s, rng, x, base, h, cor):
    s.linha([(x, base + 4), (x + h * 0.03, base - h)], cor, h * 0.07)
    for i in range(5):
        y = base - h * (0.35 + i * 0.13)
        lado = 1 if i % 2 else -1
        comp = h * rng.uniform(0.2, 0.34) * (1 - i * 0.1)
        ponta = (x + lado * comp, y - comp * rng.uniform(0.5, 0.9))
        s.linha([(x, y), (x + lado * comp * 0.55, y - comp * 0.2), ponta], cor, h * 0.03)
        s.linha([(x + lado * comp * 0.55, y - comp * 0.2),
                 (x + lado * comp * 0.8, y + comp * 0.05)], cor, h * 0.02)


def floresta():
    rng = random.Random(31)
    s = Svg(TELA)
    s.ret(0, 0, TELA, ALT, s.gradiente(0, CHAO, [
        (0, "#06111d"), (0.5, "#0e2f40"), (1, "#2f6a6c")]))
    estrelas(s, rng, 100, 280, cor="#e4f6ee")
    lx, ly = 214, 122
    s.circ(lx, ly, 200, s.brilho(lx, ly, 200, [(0, "#d6f0e2", 0.42), (0.35, "#d6f0e2", 0.14),
                                               (1, "#d6f0e2", 0)]))
    s.circ(lx, ly, 52, s.gradiente(ly - 52, ly + 52, [(0, "#f2f8e8"), (1, "#cfe0cc")]))
    for cx, cy, rx, ry in ((-18, -14, 13, 10), (16, 8, 9, 8), (-6, 22, 7, 5),
                           (22, -22, 6, 5), (-28, 12, 5, 6)):
        s.elipse(lx + cx, ly + cy, rx, ry, "#b9cdb8", opacity=0.6)
    nuvem(s, 236, 172, 230, "#12384a", opacity=0.8)
    nuvem(s, 520, 96, 200, "#16404f", opacity=0.5)
    nuvem(s, 640, 214, 270, "#1b4a57", opacity=0.45)
    s.salvar("floresta_ceu.svg")

    # --- serras com fileira de pinheiros e neblina
    rng = random.Random(32)
    s = Svg(LARG)
    morro(s, crista(rng, 322, 44, (1, 2, 3, 5)),
          s.gradiente(240, CHAO, [(0, "#143644"), (1, "#2e6468")]))
    serra = crista(rng, 372, 24, (2, 3, 4, 7))
    x = 14
    while x < LARG - 14:
        h = rng.uniform(24, 56)
        pinheiro(s, rng, x, serra(x) + 5, h, "#0e2a35", camadas=3)
        x += rng.uniform(13, 30)
    morro(s, serra, s.gradiente(345, CHAO, [(0, "#0e2a35"), (1, "#1c4950")]))
    s.ret(0, 318, LARG, 122, s.gradiente(318, 440, [
        (0, "#cfeadf", 0), (0.55, "#cfeadf", 0.24), (1, "#cfeadf", 0.1)]))
    s.salvar("floresta_longe.svg")

    # --- pinheiros grandes, arvores secas, lapides e vaga-lumes
    rng = random.Random(33)
    s = Svg(LARG)
    solo = crista(rng, 416, 7, (2, 3, 5))
    escuro, medio = "#06171c", "#0a242b"
    x = 70
    while x < LARG - 80:
        sorte = rng.random()
        base = solo(x) + 5
        if sorte < 0.62:
            h = rng.uniform(150, 292)
            pinheiro(s, rng, x, base, h, rng.choice((escuro, medio)),
                     camadas=rng.choice((5, 6)))
            x += h * 0.36 + rng.uniform(30, 120)
        elif sorte < 0.8:
            arvore_seca(s, rng, x, base, rng.uniform(110, 170), escuro)
            x += rng.uniform(90, 150)
        else:                                          # trecho de cemiterio
            for _ in range(rng.randint(2, 4)):
                base = solo(x) + 4
                if rng.random() < 0.4:                 # cruz
                    s.ret(x - 3, base - 40, 6, 42, "#12343b")
                    s.ret(x - 12, base - 31, 24, 6, "#12343b")
                else:                                  # lapide arredondada
                    larg, alt = rng.uniform(20, 28), rng.uniform(24, 36)
                    s.caminho(
                        f"M{n(x - larg / 2)} {n(base + 4)}L{n(x - larg / 2)} {n(base - alt)}"
                        f"A{n(larg / 2)} {n(larg / 2)} 0 0 1 {n(x + larg / 2)} {n(base - alt)}"
                        f"L{n(x + larg / 2)} {n(base + 4)}Z", "#12343b")
                    s.linha([(x - larg * 0.22, base - alt * 0.75),
                             (x + larg * 0.22, base - alt * 0.75)], "#06171c", 2, opacity=0.6)
                x += rng.uniform(38, 60)
            x += rng.uniform(40, 90)
    morro(s, solo, escuro)
    for _ in range(26):
        x, y = rng.uniform(20, LARG - 20), rng.uniform(250, 408)
        s.circ(x, y, 8, s.brilho(x, y, 8, [(0, "#d8ff9a", 0.5), (1, "#d8ff9a", 0)]))
        s.circ(x, y, 1.5, "#efffc0")
    s.salvar("floresta_perto.svg")


# ================================================================== neve
def aurora(s, rng, y0, amplitude, espessura, cor, forca):
    """Cortina de aurora em tiras verticais: cada tira some pra cima."""
    f1, f2, f3 = (rng.uniform(0, math.tau) for _ in range(3))
    passo = 8

    def barra(x):
        return (y0 + amplitude * math.sin(x / 150 + f1)
                + amplitude * 0.45 * math.sin(x / 57 + f2))

    for x in range(0, TELA, passo):
        # a tira e um trapezio que acompanha a curva: com retangulo a barra
        # da cortina vira escada
        b0, b1 = barra(x), barra(x + passo)
        base = (b0 + b1) / 2
        alt = espessura * (0.7 + 0.3 * math.sin(x / 96 + f3)) * rng.uniform(0.9, 1.1)
        op = forca * (0.6 + 0.4 * math.sin(x / 41 + f2) ** 2) * rng.uniform(0.85, 1.0)
        s.poligono([(x, b0 - alt), (x + passo, b1 - alt), (x + passo, b1 + 10), (x, b0 + 10)],
                   s.gradiente(base - alt, base + 10, [
                       (0, cor, 0), (0.72, cor, op * 0.55), (0.92, cor, op), (1, cor, 0)]))


def serra_nevada(s, rng, pico_min, pico_max, vale_min, vale_max, fill, sombra,
                 neve, neve_sombra):
    """Cordilheira pontuda com face sombreada e capa de neve em cada pico."""
    borda = (vale_min + vale_max) / 2
    pts = [(0, borda)]
    x = rng.uniform(90, 150)
    while x < LARG - 150:
        pts.append((x, rng.uniform(pico_min, pico_max)))            # pico
        x += rng.uniform(80, 150)
        if x >= LARG - 60:
            break
        pts.append((x, rng.uniform(vale_min, vale_max)))            # vale
        x += rng.uniform(80, 150)
    if len(pts) % 2:                    # terminou num vale: tira, a borda fecha
        pts.pop()
    pts.append((LARG, borda))
    s.poligono(pts + [(LARG, ALT), (0, ALT)], fill)

    def entre(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    for i in range(1, len(pts) - 1, 2):
        esq, pico, dire = pts[i - 1], pts[i], pts[i + 1]
        s.poligono([pico, dire, (dire[0], ALT), (pico[0], ALT)], sombra, opacity=0.45)
        t = rng.uniform(0.3, 0.42)
        a, b = entre(pico, esq, t), entre(pico, dire, t)
        barra = []
        for k in range(1, 6):
            p = entre(b, a, k / 6)
            barra.append((p[0], p[1] + (9 if k % 2 else -7) * rng.uniform(0.7, 1.3)))
        s.poligono([pico, b] + barra + [a], neve)
        s.poligono([pico, b, barra[0], barra[1], (pico[0], barra[1][1] - 4)], neve_sombra)


def neve():
    rng = random.Random(41)
    s = Svg(TELA)
    s.ret(0, 0, TELA, ALT, s.gradiente(0, CHAO, [
        (0, "#040b1f"), (0.45, "#0d2850"), (1, "#3f7799")]))
    estrelas(s, rng, 150, 330, cor="#eaf4ff")
    aurora(s, rng, 210, 34, 150, "#8a6cf0", 0.34)
    aurora(s, rng, 168, 30, 130, "#4df0a0", 0.5)
    aurora(s, rng, 250, 24, 100, "#58e8d0", 0.36)
    s.salvar("neve_ceu.svg")

    rng = random.Random(42)
    s = Svg(LARG)
    serra_nevada(s, rng, 236, 300, 340, 376,
                 s.gradiente(230, CHAO, [(0, "#3c6592"), (1, "#6c97ba")]),
                 "#284a78", "#dcebfa", "#a9c6e4")
    serra_nevada(s, rng, 176, 262, 352, 396,
                 s.gradiente(170, CHAO, [(0, "#24416f"), (1, "#4f79a3")]),
                 "#152b52", "#f0f7ff", "#b4cfea")
    s.salvar("neve_longe.svg")

    rng = random.Random(43)
    s = Svg(LARG)
    colina = crista(rng, 404, 14, (1, 2, 3, 5))
    x = 60
    cabana_x = 1180
    while x < LARG - 70:
        if abs(x - cabana_x) < 110:                    # deixa a clareira da cabana
            x = cabana_x + 120
        h = rng.uniform(92, 226)
        pinheiro(s, rng, x, colina(x) + 6, h, "#11304a", neve="#e8f2fc",
                 camadas=rng.choice((4, 5)))
        x += h * 0.34 + rng.uniform(26, 130)

    # cabana com a janela acesa e fumaca na chamine
    cy = colina(cabana_x) + 4
    s.ret(cabana_x + 16, cy - 76, 10, 24, "#2a1c22")
    for i, (dx, dy, r) in enumerate(((22, -88, 7), (30, -104, 9), (24, -122, 11),
                                     (36, -142, 13))):
        s.circ(cabana_x + dx, cy + dy, r, "#dfeaf6", opacity=round(0.34 - i * 0.07, 2))
    s.ret(cabana_x - 38, cy - 40, 76, 44, "#3a2830")
    for dy in (-30, -20, -10):
        s.linha([(cabana_x - 36, cy + dy), (cabana_x + 36, cy + dy)], "#2a1c22", 1.6)
    s.poligono([(cabana_x - 48, cy - 38), (cabana_x, cy - 74), (cabana_x + 48, cy - 38)],
               "#2a1c22")
    s.poligono([(cabana_x - 50, cy - 40), (cabana_x, cy - 78), (cabana_x + 50, cy - 40),
                (cabana_x + 42, cy - 42), (cabana_x, cy - 68), (cabana_x - 42, cy - 42)],
               "#eef6ff")
    s.circ(cabana_x - 14, cy - 20, 26, s.brilho(cabana_x - 14, cy - 20, 26, [
        (0, "#ffd27a", 0.55), (1, "#ffd27a", 0)]))
    s.ret(cabana_x - 23, cy - 29, 18, 16, "#ffd98a", rx=1.5)
    s.linha([(cabana_x - 14, cy - 29), (cabana_x - 14, cy - 13)], "#3a2830", 1.6)
    s.linha([(cabana_x - 23, cy - 21), (cabana_x - 5, cy - 21)], "#3a2830", 1.6)
    s.ret(cabana_x + 10, cy - 26, 14, 30, "#2a1c22", rx=1.5)

    morro(s, colina, s.gradiente(386, CHAO, [(0, "#a9c4de"), (1, "#5d80a8")]))
    s.linha([(x, colina(x) + 1) for x in range(0, LARG + 1, 12)], "#f2f8ff", 3, opacity=0.9)
    s.salvar("neve_perto.svg")


# ================================================================= tunel
TUNEL_L = 800               # largura da arte; o vao tem 720 na base
TUNEL_TETO = 215            # altura do teto do vao (cfg.TUNEL_TETO)


def _arco(cx, cy, r, a0, a1, passos=8):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / passos)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / passos)))
            for i in range(passos + 1)]


def _reamostrar(pontos, passo):
    """Pontos igualmente espacados ao longo da linha, pros blocos do arco."""
    total = sum(math.dist(a, b) for a, b in zip(pontos, pontos[1:]))
    quantidade = max(2, round(total / passo))
    alvo = total / quantidade
    saida, sobra = [pontos[0]], alvo
    for a, b in zip(pontos, pontos[1:]):
        trecho = math.dist(a, b)
        pos = 0.0
        while trecho - pos >= sobra - 1e-6:
            pos += sobra
            t = pos / trecho
            saida.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            sobra = alvo
        sobra -= trecho - pos
    saida[-1] = pontos[-1]
    return saida


def tunel():
    base = CHAO + 2
    r = 42
    # contorno do vao: parede esquerda, teto com os cantos arredondados, direita
    vao = ([(40, base), (56, TUNEL_TETO + r + 5)]
           + _arco(56 + r, TUNEL_TETO + r, r, 180, 270)
           + _arco(TUNEL_L - 56 - r, TUNEL_TETO + r, r, 270, 360)
           + [(TUNEL_L - 56, TUNEL_TETO + r + 5), (TUNEL_L - 40, base)])

    # --- interior: parede do fundo, lampadas e cabos
    s = Svg(TUNEL_L)
    meio = TUNEL_L / 2
    s.poligono([(x + (4 if x > meio else -4), y - (4 if y < 400 else 0)) for x, y in vao],
               s.gradiente(TUNEL_TETO, CHAO, [(0, "#14111b"), (1, "#282231")]))
    for x in range(120, TUNEL_L - 100, 80):            # emendas dos paineis
        s.linha([(x, TUNEL_TETO + 6), (x, CHAO)], "#0d0b13", 3, opacity=0.7)
        s.linha([(x + 3, TUNEL_TETO + 6), (x + 3, CHAO)], "#352e42", 1, opacity=0.8)
    s.ret(52, 372, TUNEL_L - 104, 10, "#3a3349", opacity=0.7)       # faixa pintada
    s.linha([(60, 296), (TUNEL_L - 60, 296)], "#0d0b13", 3)         # cabo
    s.linha([(60, 304), (TUNEL_L - 60, 304)], "#0d0b13", 2)
    for x in range(100, TUNEL_L - 80, 80):
        s.ret(x - 3, 290, 6, 20, "#3a3349", rx=1)
    for x in range(160, TUNEL_L - 100, 160):           # lampadas do teto
        s.poligono([(x - 11, 228), (x + 11, 228), (x + 86, CHAO), (x - 86, CHAO)],
                   s.gradiente(228, CHAO, [(0, "#ffd98a", 0.3), (1, "#ffd98a", 0.02)]))
        s.circ(x, 228, 50, s.brilho(x, 228, 50, [(0, "#ffe2a0", 0.55), (1, "#ffe2a0", 0)]))
        s.ret(x - 14, TUNEL_TETO + 3, 28, 8, "#40384e", rx=2)
        s.elipse(x, TUNEL_TETO + 12, 10, 4, "#fff0c0")
    s.ret(36, 404, TUNEL_L - 72, 28, s.gradiente(404, base, [
        (0, "#000000", 0), (1, "#000000", 0.4)]))
    s.salvar("tunel_fundo.svg")

    # --- frente: o morro de rocha com o vao recortado e o arco de pedra
    rng = random.Random(52)
    s = Svg(TUNEL_L)
    encosta = [(4, base), (15, 374), (24, 320), (21, 264), (35, 208), (50, 160),
               (79, 118), (96, 70), (129, 36), (150, 0)]
    direita = [(TUNEL_L - x + rng.uniform(-6, 6) * (0 < y < base), y + rng.uniform(-8, 8) * (0 < y < base))
               for x, y in encosta]
    s.poligono(encosta + direita[::-1] + vao[::-1],
               s.gradiente(0, CHAO, [(0, "#2a2634"), (1, "#4a4356")]))
    # facetas e veios: quebram o chapado da rocha
    for _ in range(18):
        cx, cy = rng.uniform(190, TUNEL_L - 190), rng.uniform(14, 176)
        lados = rng.choice((3, 4, 5))
        raio = rng.uniform(18, 46)
        inicio = rng.uniform(0, math.tau)
        s.poligono([(cx + math.cos(inicio + math.tau * i / lados) * raio * rng.uniform(0.6, 1.2),
                     cy + math.sin(inicio + math.tau * i / lados) * raio * rng.uniform(0.4, 0.8))
                    for i in range(lados)],
                   rng.choice(("#5b5368", "#1f1b28")), opacity=round(rng.uniform(0.2, 0.4), 2))
    for y in (52, 104, 158):
        xs = range(150 + y // 3, TUNEL_L - 150 - y // 3, 34)
        s.linha([(x, y + rng.uniform(-7, 7)) for x in xs], "#1f1b28", 2.2, opacity=0.45)
    for _ in range(7):                                 # rachaduras
        x, y = rng.uniform(170, TUNEL_L - 170), rng.uniform(20, 150)
        pontos = [(x, y)]
        for _ in range(rng.randint(3, 5)):
            x += rng.uniform(-16, 16)
            y += rng.uniform(8, 18)
            pontos.append((x, y))
        s.linha(pontos, "#17141d", 1.8, opacity=0.6)
    s.linha(encosta, "#7c738a", 2.5, opacity=0.5)       # luz na beira da encosta
    s.linha(direita, "#17141d", 2.5, opacity=0.5)

    # arco de pedra: um bloco por trecho, acompanhando a curva do vao
    linha = _reamostrar(vao, 27)
    normais = []
    for i, ponto in enumerate(linha):
        a, b = linha[max(0, i - 1)], linha[min(len(linha) - 1, i + 1)]
        comp = math.dist(a, b) or 1
        normais.append(((b[1] - a[1]) / comp, -(b[0] - a[0]) / comp))
    borda = [(p[0] + nx * 17, p[1] + ny * 17) for p, (nx, ny) in zip(linha, normais)]
    for i in range(len(linha) - 1):
        s.poligono([linha[i], linha[i + 1], borda[i + 1], borda[i]],
                   ("#756c80", "#675f73")[i % 2], stroke="#2a2634", stroke_width=1.6,
                   stroke_linejoin="round")
    s.linha(linha, "#191620", 3, opacity=0.7)           # sombra na boca do vao
    for lado, xs in ((1, (0, 6, 14, 26)), (-1, (TUNEL_L, TUNEL_L - 8, TUNEL_L - 18, TUNEL_L - 30))):
        s.poligono([(xs[0], base), (xs[1], base - 12), (xs[2], base - 18),
                    (xs[3], base - 9), (xs[3] + lado * 6, base)], "#3a3446")
    s.salvar("tunel_frente.svg")


CENARIOS = (cidade, deserto, floresta, neve, tunel)

if __name__ == "__main__":
    os.makedirs(RAIZ, exist_ok=True)
    print("fundos:")
    for gerar in CENARIOS:
        gerar()
