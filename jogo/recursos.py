"""Carregamento dos sprites: fatia as folhas, corta o vazio e pre-renderiza.

Tudo o que o jogo desenha sai daqui ja pronto (escalado e sombreado), porque
com 80 zumbis na tela nao da pra escalar surface dentro do loop de desenho.
"""

import math
import os

import pygame

from jogo import config as cfg
from jogo import poderes

RAIZ = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "image"
)

RAIZ_FUNDOS = os.path.join(os.path.dirname(RAIZ), "fundos")
CAMADAS_FUNDO = ("ceu", "longe", "perto")

# [tipo][linha da formacao][quadro] -> Surface
_zumbis = []
# [tipo][quadro] -> Surface, na escala do poder gigante
_gigantes = []
# [tipo][quadro] -> Surface
_humanos = []
_icones = {}        # nome do poder -> icone pro HUD e pra tampa da caixa
_asas = []          # quadros do bater de asas do poder dragao
_caixa = None
_balao = None
_fundos = {}        # nome do cenario -> (ceu, longe, perto), ou None sem arte
_tunel = False      # False = ainda nao tentou; depois (fundo, frente) ou None
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


def _folhas(prefixo):
    """Folhas de sprite do disco, em ordem, ja convertidas."""
    try:
        nomes = sorted(
            f for f in os.listdir(RAIZ)
            if f.startswith(prefixo) and f.endswith(".png")
        )
    except OSError:
        return []
    saida = []
    for nome in nomes:
        try:
            saida.append(pygame.image.load(os.path.join(RAIZ, nome)).convert_alpha())
        except pygame.error:
            continue
    return saida


def _avulso(nome, altura):
    """Um PNG unico (icone, caixa, asas), escalado pela altura pedida."""
    try:
        img = pygame.image.load(os.path.join(RAIZ, nome)).convert_alpha()
    except (pygame.error, OSError):
        return None
    caixa = img.get_bounding_rect(min_alpha=8)
    if caixa.width and caixa.height:
        img = img.subsurface(caixa).copy()
    return _escalar(img, altura)


def carregar():
    """Le as folhas de sprite. Silencioso: sem arte, o jogo cai nas formas."""
    global _carregado, _caixa, _balao
    if _carregado:
        return
    if not pygame.display.get_init() or pygame.display.get_surface() is None:
        # convert_alpha() precisa da janela aberta; tenta de novo depois
        return
    _carregado = True

    for folha in _folhas("zombie"):
        cortes = _fatiar(folha)
        # uma copia por linha da formacao: menor e mais escura quanto mais
        # atras, que e o que da perspectiva a massa
        por_linha = []
        for linha in range(cfg.LARG_FORMACAO):
            altura = round(cfg.ZUMBI_SPRITE_A * (1.0 - linha * cfg.ESCALA_LINHA))
            fator = 1.0 - linha * cfg.SOMBRA_LINHA
            por_linha.append([_sombrear(_escalar(q, altura), fator) for q in cortes])
        _zumbis.append(por_linha)
        # versao do poder gigante: so uma escala, sem as linhas da formacao
        gigante = round(cfg.ZUMBI_SPRITE_A * cfg.GIGANTE_ESCALA)
        _gigantes.append([_escalar(q, gigante) for q in cortes])

    for folha in _folhas("human"):
        _humanos.append([_escalar(q, cfg.HUMANO_SPRITE_A) for q in _fatiar(folha)])

    for nome in poderes.TODOS:
        icone = _avulso(f"poder_{nome}.png", cfg.ICONE_HUD)
        if icone is not None:
            _icones[nome] = icone

    _caixa = _avulso("caixa.png", cfg.CAIXA_SPRITE)
    _balao = _avulso("poder_balao.png", cfg.BALAO_SPRITE_A)

    asas = _avulso("asas.png", cfg.DRAGAO_ASAS_A)
    if asas is not None:
        # o bater de asa e so a mesma arte achatada: pre-escalar aqui evita
        # um transform.scale por zumbi por quadro no meio do desenho
        larg, alt = asas.get_size()
        for i in range(4):
            f = 1.0 - 0.45 * abs(math.sin(i / 4 * math.pi))
            _asas.append(pygame.transform.smoothscale(
                asas, (larg, max(1, round(alt * f)))))


def _camada_fundo(nome, camada):
    """Uma camada do cenario, em SVG ou PNG, na altura da tela.

    O SVG e rasterizado direto no tamanho certo; o PNG e reescalado. A
    largura acompanha a proporcao do arquivo: camada mais larga que a tela
    demora mais pra se repetir.
    """
    for ext in ("svg", "png"):
        caminho = os.path.join(RAIZ_FUNDOS, f"{nome}_{camada}.{ext}")
        if not os.path.exists(caminho):
            continue
        try:
            img = pygame.image.load(caminho)
            if img.get_height() != cfg.ALTURA:
                tamanho = (max(1, round(img.get_width() * cfg.ALTURA / img.get_height())),
                           cfg.ALTURA)
                if ext == "svg":
                    img = pygame.image.load_sized_svg(caminho, tamanho)
                else:
                    img = pygame.transform.smoothscale(img, tamanho)
        except (pygame.error, OSError):
            continue
        if camada == "ceu":
            # o ceu fica parado e cobre a tela toda: opaco, que e mais barato
            if img.get_width() != cfg.LARGURA:
                img = pygame.transform.smoothscale(img, (cfg.LARGURA, cfg.ALTURA))
            return img.convert()
        return img.convert_alpha()
    return None


def fundo(nome):
    """(ceu, longe, perto) do cenario, ou None se nem o ceu existir.

    As camadas longe e perto sao opcionais: um cenario pode ser so uma imagem.
    """
    if nome not in _fundos:
        if not pygame.display.get_init() or pygame.display.get_surface() is None:
            return None                 # sem janela nao da pra converter ainda
        camadas = tuple(_camada_fundo(nome, c) for c in CAMADAS_FUNDO)
        _fundos[nome] = camadas if camadas[0] is not None else None
    return _fundos[nome]


def tunel():
    """(interior, frente) do tunel entre cenarios, ou None sem a arte."""
    global _tunel
    if _tunel is False:
        if not pygame.display.get_init() or pygame.display.get_surface() is None:
            return None
        camadas = tuple(_camada_fundo("tunel", c) for c in ("fundo", "frente"))
        _tunel = camadas if all(c is not None for c in camadas) else None
    return _tunel


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


def total_humanos():
    carregar()
    return len(_humanos)


def humano(tipo, quadro):
    carregar()
    if not _humanos:
        return None
    animacao = _humanos[tipo % len(_humanos)]
    return animacao[quadro % len(animacao)]


def zumbi_gigante(tipo, quadro):
    """O mesmo zumbi, na escala do poder gigante."""
    carregar()
    if not _gigantes:
        return None
    animacao = _gigantes[tipo % len(_gigantes)]
    return animacao[quadro % len(animacao)]


def icone(poder):
    carregar()
    return _icones.get(poder)


def caixa():
    carregar()
    return _caixa


def balao():
    carregar()
    return _balao


def asas(fase):
    carregar()
    if not _asas:
        return None
    return _asas[int(fase) % len(_asas)]
