"""Monta as folhas de sprite do jogo a partir de pacotes prontos da web.

Personagens: pacotes gratuitos do GameArt2D (https://www.gameart2d.com/freebies.html),
todos em CC0 / dominio publico. Cada pacote traz uma animacao como uma pilha
de PNG soltos ("Run (1).png", "Run (2).png"...). Aqui cada pilha vira uma
folha so, no formato que `jogo/recursos.py` le: quadros quadrados lado a lado,
todos virados pra direita.

Icones: SVG do game-icons.net (CC BY 3.0, veja CREDITOS.md), guardados em
`ferramentas/icones/`. Viram um selo redondo na cor de cada poder.

Uso - baixe e descompacte os pacotes numa pasta, um por subpasta com o nome
do zip (veja `PACOTES`), e rode:

    ./venv/bin/python ferramentas/importar_sprites.py /caminho/dos/pacotes

Sem argumento, so os icones sao refeitos.

O que sai em `assets/image/`:

    zombie_<nome>.png    quem ja nasce na horda, ou a versao zumbi de um humano
    human_<nome>.png     as pessoas da rua
    monstro_<nome>.png   monstros que a loja libera pra horda
    dragao.png           o dragao em que a horda vira no poder do dragao
    poder_<nome>.png     icone de cada poder
    loja_<nome>.png      icones da loja
"""

import os
import re
import sys

import pygame

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "assets", "image")
ICONES_SVG = os.path.join(RAIZ, "ferramentas", "icones")

QUADRO = 160            # lado de cada quadro na folha
QUADROS = 8             # quadros por ciclo (pacotes com mais sao amostrados)

# (prefixo, nome, pasta dentro do download, animacao, zumbifica?)
# `zumbifica` gera tambem zombie_<nome>.png: a pessoa depois de mordida.
PACOTES = (
    ("zombie", "01_zumbi", "zombiefiles/png/male", "Walk", False),
    ("zombie", "02_zumbi_moca", "zombiefiles/png/female", "Walk", False),
    ("human", "garoto", "flatboy/png", "Run", True),
    ("human", "garota", "cutegirlfiles/png", "Run", True),
    ("human", "exploradora", "adventure_girl/png", "Run", True),
    ("human", "explorador", "templerun", "Run", True),
    ("human", "noel", "santasprites/png", "Run", True),
    ("human", "cavaleiro", "freeknight/png", "Run", True),
    ("human", "ninja", "ninjaadventurenew/png", "Run", True),
    ("human", "ninja_moca", "ninjagirlnew/png", "Run", True),
    ("monstro", "abobora", "jackfree/png", "Run", False),
    ("monstro", "dino", "freedinosprite/png", "Run", False),
    ("monstro", "robo", "robotfree/png", "Run", False),
)

# "Flappy Dragon" (bevouliin, CC0, opengameart.org): pasta, subpasta, animacao
DRAGAO = ("dragao", "PNG", "frame-")
DRAGAO_QUADRO = 320

# pele esverdeada e roupa apagada: o humano depois da mordida
ZUMBI_CINZA = 120       # quanto de cinza entra por cima (0-255)
ZUMBI_TINTA = (150, 226, 138)

# nome do arquivo de saida -> (svg, cor do selo)
ICONES = {
    "poder_gigante": ("gigante", (92, 168, 76)),
    "poder_dragao": ("dragao", (138, 84, 190)),
    "poder_balao": ("balao", (224, 84, 96)),
    "poder_ima": ("ima", (226, 120, 52)),
    "loja_horda": ("horda", (92, 168, 76)),
    "loja_tempo": ("tempo", (70, 132, 206)),
    "loja_chance": ("chance", (214, 72, 96)),
    "loja_cadeado": ("cadeado", (96, 90, 112)),
}
ICONE = 128


# ------------------------------------------------------------- personagens
def _numero(nome):
    achados = re.findall(r"\d+", nome)
    return int(achados[-1]) if achados else 0


def quadros_de(pasta, animacao):
    """Os PNG de uma animacao, em ordem, amostrados pra `QUADROS` quadros."""
    nomes = sorted(
        (f for f in os.listdir(pasta)
         if f.lower().startswith(animacao.lower()) and f.lower().endswith(".png")
         and re.fullmatch(re.escape(animacao) + r"[ _]*\(?\d+\)?\.png", f, re.I)),
        key=_numero)
    if not nomes:
        raise SystemExit(f"sem quadros '{animacao}' em {pasta}")
    passo = len(nomes) / QUADROS if len(nomes) > QUADROS else 1
    escolhidos = [nomes[int(i * passo)] for i in range(min(QUADROS, len(nomes)))]
    return [pygame.image.load(os.path.join(pasta, n)) for n in escolhidos]


def montar_folha(quadros, QUADRO=QUADRO):
    """Corta o vazio (o mesmo corte pra todos, pra animacao nao tremer),
    reduz e alinha cada quadro pelo pe, no centro do seu quadrado."""
    caixa = quadros[0].get_bounding_rect(min_alpha=8)
    for q in quadros[1:]:
        caixa.union_ip(q.get_bounding_rect(min_alpha=8))
    escala = (QUADRO - 4) / max(caixa.size)
    larg, alt = max(1, round(caixa.width * escala)), max(1, round(caixa.height * escala))
    folha = pygame.Surface((QUADRO * len(quadros), QUADRO), pygame.SRCALPHA)
    for i, q in enumerate(quadros):
        recorte = pygame.Surface(caixa.size, pygame.SRCALPHA)
        recorte.blit(q, (0, 0), caixa)
        pequeno = pygame.transform.smoothscale(recorte, (larg, alt))
        folha.blit(pequeno, (i * QUADRO + (QUADRO - larg) // 2, QUADRO - 2 - alt))
    return folha


def zumbificar(folha):
    """A mesma folha com cara de infectado: menos cor e um banho de verde."""
    saida = folha.copy()
    cinza = pygame.transform.grayscale(folha)
    cinza.set_alpha(ZUMBI_CINZA)
    saida.blit(cinza, (0, 0))
    saida.fill((*ZUMBI_TINTA, 255), special_flags=pygame.BLEND_RGB_MULT)
    return saida


def importar_personagens(origem):
    antigos = [f for f in os.listdir(SAIDA)
               if re.match(r"(zombie|human|monstro)_", f) and f.endswith(".png")]
    for f in antigos:
        os.remove(os.path.join(SAIDA, f))
    # o dragao em que a horda se transforma: 4 quadros do bater de asas
    salvar(montar_folha(quadros_de(os.path.join(origem, *DRAGAO[:-1]), DRAGAO[-1]),
                        DRAGAO_QUADRO), "dragao.png")
    for prefixo, nome, pasta, animacao, zumbifica in PACOTES:
        folha = montar_folha(quadros_de(os.path.join(origem, pasta), animacao))
        salvar(folha, f"{prefixo}_{nome}.png")
        if zumbifica:
            salvar(zumbificar(folha), f"zombie_{nome}.png")


# ------------------------------------------------------------------ icones
def selo(svg, cor):
    """Disco na cor pedida, com contorno escuro e o desenho branco no meio."""
    grande = ICONE * 4
    surf = pygame.Surface((grande, grande), pygame.SRCALPHA)
    c = grande // 2
    pygame.draw.circle(surf, (26, 20, 30), (c, c), c - 4)
    pygame.draw.circle(surf, tuple(int(v * 0.72) for v in cor), (c, c), c - 28)
    pygame.draw.circle(surf, cor, (c, c - 10), c - 40)
    lado = int(grande * 0.62)
    desenho = pygame.image.load_sized_svg(os.path.join(ICONES_SVG, svg + ".svg"),
                                          (lado, lado))
    sombra = desenho.copy()
    sombra.fill((20, 14, 24, 255), special_flags=pygame.BLEND_RGB_MULT)
    sombra.set_alpha(120)
    surf.blit(sombra, sombra.get_rect(center=(c + 6, c + 4)))
    surf.blit(desenho, desenho.get_rect(center=(c, c - 6)))
    return pygame.transform.smoothscale(surf, (ICONE, ICONE))


def gerar_icones():
    for nome, (svg, cor) in ICONES.items():
        salvar(selo(svg, cor), nome + ".png")


def salvar(surf, nome):
    pygame.image.save(surf, os.path.join(SAIDA, nome))
    print(f"  {nome}  {surf.get_width()}x{surf.get_height()}")


if __name__ == "__main__":
    pygame.init()
    os.makedirs(SAIDA, exist_ok=True)
    if len(sys.argv) > 1:
        print("personagens:")
        importar_personagens(sys.argv[1])
    print("icones:")
    gerar_icones()
    pygame.quit()
