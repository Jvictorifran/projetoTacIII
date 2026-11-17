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
# [tipo][quadro] -> Surface
_humanos = []
_nomes_zumbi = []   # nome de cada tipo de zumbi, na mesma ordem de _zumbis
_nomes_humano = []
_base = []          # tipos que ja nascem zumbis (nao sao um humano mordido)
_monstros = {}      # nome do monstro da loja -> tipo
_icones_loja = {}   # nome -> icone da loja
_icones = {}        # nome do poder -> icone pro HUD e pra tampa da caixa
_cortes = []        # [tipo][quadro] -> quadro cru, pra escalar sob demanda
_dragao = []        # quadros crus do dragao em que a horda se transforma
_baloes = []        # um balao de cada cor
_ima = None
_sob_medida = {}    # cache dos sprites escalados sob demanda (gigante, dragao)
_caixa = None
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
    """Pares (nome, folha) do disco, em ordem, ja convertidos.

    O nome e o do arquivo sem o prefixo: `human_noel.png` -> "noel".
    """
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
            folha = pygame.image.load(os.path.join(RAIZ, nome)).convert_alpha()
            saida.append((nome[len(prefixo):-4].lstrip("_"), folha))
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
    global _carregado, _caixa, _ima
    if _carregado:
        return
    if not pygame.display.get_init() or pygame.display.get_surface() is None:
        # convert_alpha() precisa da janela aberta; tenta de novo depois
        return
    _carregado = True

    humanos = _folhas("human")
    nomes_humanos = {nome for nome, _ in humanos}
    # a horda junta tres familias: zumbis de nascenca, a versao zumbi de cada
    # humano (mesmo nome do human_*) e os monstros que a loja libera
    folhas = [(p, n, f) for p in ("zombie", "monstro") for n, f in _folhas(p)]
    for prefixo, nome, folha in folhas:
        tipo = len(_zumbis)
        _nomes_zumbi.append(nome)
        if prefixo == "monstro":
            _monstros[nome] = tipo
        elif nome not in nomes_humanos:
            _base.append(tipo)
        cortes = _fatiar(folha)
        _cortes.append(cortes)
        # uma copia por linha da formacao: menor e mais escura quanto mais
        # atras, que e o que da perspectiva a massa
        por_linha = []
        for linha in range(cfg.LARG_FORMACAO):
            altura = round(cfg.ZUMBI_SPRITE_A * (1.0 - linha * cfg.ESCALA_LINHA))
            fator = 1.0 - linha * cfg.SOMBRA_LINHA
            por_linha.append([_sombrear(_escalar(q, altura), fator) for q in cortes])
        _zumbis.append(por_linha)

    for nome, folha in humanos:
        _nomes_humano.append(nome)
        _humanos.append([_escalar(q, cfg.HUMANO_SPRITE_A) for q in _fatiar(folha)])

    try:
        for arq in sorted(os.listdir(RAIZ)):
            if arq.startswith("loja_") and arq.endswith(".png"):
                icone = _avulso(arq, cfg.ICONE_LOJA)
                if icone is not None:
                    _icones_loja[arq[5:-4]] = icone
    except OSError:
        pass

    for nome in poderes.TODOS:
        icone = _avulso(f"poder_{nome}.png", cfg.ICONE_HUD)
        if icone is not None:
            _icones[nome] = icone

    _caixa = _avulso("caixa.png", cfg.CAIXA_SPRITE)
    _ima = _avulso("ima.png", cfg.IMA_SPRITE_A)
    try:
        folha = pygame.image.load(os.path.join(RAIZ, "baloes.png")).convert_alpha()
        _baloes.extend(_escalar(q, cfg.BALAO_SPRITE_A) for q in _fatiar(folha))
        folha = pygame.image.load(os.path.join(RAIZ, "dragao.png")).convert_alpha()
        _dragao.extend(_fatiar(folha))
    except (pygame.error, OSError):
        pass


def _medida(chave, quadro, altura):
    """Quadro escalado pra `altura`, guardado: escalar a cada desenho pesa."""
    chave = chave + (altura,)
    if chave not in _sob_medida:
        _sob_medida[chave] = _escalar(quadro, altura)
    return _sob_medida[chave]


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


def tipo_inicial():
    """Tipo do zumbi que comeca a partida."""
    carregar()
    return _base[0] if _base else 0


def tipos_base():
    """Tipos que ja nascem zumbis; sem nenhum, vale qualquer um."""
    carregar()
    return _base or list(range(len(_zumbis)))


def tipo_do_humano(tipo_humano):
    """Tipo de zumbi em que este humano vira, ou None se nao houver folha."""
    carregar()
    if not _nomes_humano:
        return None
    nome = _nomes_humano[tipo_humano % len(_nomes_humano)]
    return _nomes_zumbi.index(nome) if nome in _nomes_zumbi else None


def tipo_do_monstro(nome):
    carregar()
    return _monstros.get(nome)


def icone_loja(nome):
    carregar()
    return _icones_loja.get(nome)


def total_humanos():
    carregar()
    return len(_humanos)


def humano(tipo, quadro):
    carregar()
    if not _humanos:
        return None
    animacao = _humanos[tipo % len(_humanos)]
    return animacao[quadro % len(animacao)]


def icone(poder):
    carregar()
    return _icones.get(poder)


def caixa():
    carregar()
    return _caixa


def balao(indice):
    """Balao do zumbi `indice`: a cor roda pela folha."""
    carregar()
    return _baloes[indice % len(_baloes)] if _baloes else None


def ima():
    carregar()
    return _ima


def gigantao(tipo, quadro, altura):
    """Um zumbi so, enorme: e nele que a horda vira no poder gigante.

    A altura e arredondada de 8 em 8 px pro cache nao crescer a cada zumbi
    que entra na horda.
    """
    carregar()
    if not _cortes:
        return None
    animacao = _cortes[tipo % len(_cortes)]
    q = quadro % len(animacao)
    return _medida(("gigante", tipo, q), animacao[q], max(8, round(altura / 8) * 8))


def dragao(fase, altura):
    """Quadro do dragao batendo asa, na altura pedida (de 8 em 8 px)."""
    carregar()
    if not _dragao:
        return None
    q = int(fase) % len(_dragao)
    return _medida(("dragao", q), _dragao[q], max(8, round(altura / 8) * 8))
