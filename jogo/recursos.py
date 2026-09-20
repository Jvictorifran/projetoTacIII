"""Carregamento dos sprites: fatia as folhas, corta o vazio e pre-renderiza.

Tudo o que o jogo desenha sai daqui ja pronto (escalado e sombreado), porque
com 80 zumbis na tela nao da pra escalar surface dentro do loop de desenho.
"""

import os

import pygame

from jogo import config as cfg

RAIZ = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "image"
)

# [tipo][linha da formacao][quadro] -> Surface
_zumbis = []
_carregado = False


def _fatiar(folha):
    """Quebra a folha em quadros quadrados e corta o vazio ao redor.

    O recorte e o mesmo pra todos os quadros (a uniao das caixas): cortar
    quadro a quadro mudaria a ancora e a animacao ficaria tremendo.
    """
    larg, alt = folha.get_size()
    quadros = [
        folha.subsurface(pygame.Rect(i * alt, 0, alt, alt))
        for i in range(max(1, larg // alt))
    ]
    caixa = quadros[0].get_bounding_rect(min_alpha=8)
    for q in quadros[1:]:
        caixa.union_ip(q.get_bounding_rect(min_alpha=8))
    if caixa.width == 0 or caixa.height == 0:
        caixa = pygame.Rect(0, 0, alt, alt)
    return [q.subsurface(caixa).copy() for q in quadros]


def _escalar(quadro, altura):
    escala = altura / quadro.get_height()
    largura = max(1, round(quadro.get_width() * escala))
    return pygame.transform.smoothscale(quadro, (largura, altura))


def _sombrear(surf, fator):
    """Copia escurecida, pras linhas de tras da horda darem profundidade."""
    if fator >= 1.0:
        return surf
    copia = surf.copy()
    v = max(0, min(255, int(255 * fator)))
    copia.fill((v, v, v, 255), special_flags=pygame.BLEND_RGB_MULT)
    return copia


def carregar():
    """Le as folhas de sprite. Silencioso: sem arte, o jogo cai nas formas."""
    global _carregado
    if _carregado:
        return
    if not pygame.display.get_init() or pygame.display.get_surface() is None:
        # convert_alpha() precisa da janela aberta; tenta de novo depois
        return
    _carregado = True

    try:
        arquivos = sorted(
            f for f in os.listdir(RAIZ)
            if f.startswith("zombie") and f.endswith(".png")
        )
    except OSError:
        arquivos = []

    for nome in arquivos:
        try:
            folha = pygame.image.load(os.path.join(RAIZ, nome)).convert_alpha()
        except pygame.error:
            continue
        cortes = _fatiar(folha)
        # uma copia por linha da formacao: menor e mais escura quanto mais
        # atras, que e o que da perspectiva a massa
        por_linha = []
        for linha in range(cfg.LARG_FORMACAO):
            altura = round(cfg.ZUMBI_SPRITE_A * (1.0 - linha * cfg.ESCALA_LINHA))
            fator = 1.0 - linha * cfg.SOMBRA_LINHA
            por_linha.append([_sombrear(_escalar(q, altura), fator) for q in cortes])
        _zumbis.append(por_linha)


def total_tipos():
    carregar()
    return len(_zumbis)


def zumbi(tipo, quadro, linha=0):
    """Um quadro pronto pra blit, ou None se nao houver sprite carregado."""
    carregar()
    if not _zumbis:
        return None
    animacao = _zumbis[tipo % len(_zumbis)][linha % cfg.LARG_FORMACAO]
    return animacao[quadro % len(animacao)]
