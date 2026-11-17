"""A lojinha: catalogo, regras de compra e a tela.

As moedas pegas nas partidas vao pro cofre (`progresso`) e sao gastas aqui.
Ha tres tipos de item:

- melhoria: tem niveis, cada um mais caro (`precos` = preco de cada nivel);
- monstro: compra unica, libera um bicho novo pra horda;
- consumivel: preco fixo, vai pro estoque e e gasto durante a partida.

Quem aplica o efeito de cada item e o `jogo.py`, lendo `progresso.nivel(id)`.
"""

import pygame

from jogo import config as cfg
from jogo import progresso
from jogo import recursos
from jogo import sons

HORDA, TEMPO, CHANCE = "horda", "tempo", "chance"
BONUS_TEMPO = 0.15          # cada nivel de "poder duradouro" soma isso

ITENS = (
    {"id": HORDA, "nome": "Horda inicial", "icone": "horda",
     "dica": "+1 zumbi no comeco de cada partida", "precos": (100, 250, 500, 900)},
    {"id": TEMPO, "nome": "Poder duradouro", "icone": "tempo",
     "dica": "+15% de duracao em todos os poderes", "precos": (150, 350, 700)},
    {"id": CHANCE, "nome": "Segunda chance", "icone": "chance",
     "dica": "perdeu a horda? volta voando com 3 zumbis (1 por partida)",
     "precos": (120,), "estoque": 3},
    {"id": "abobora", "nome": "Cabeca de abobora", "monstro": "abobora",
     "dica": "monstro novo: quem e mordido pode virar um", "precos": (200,)},
    {"id": "dino", "nome": "Dinossauro", "monstro": "dino",
     "dica": "monstro novo: quem e mordido pode virar um", "precos": (350,)},
    {"id": "robo", "nome": "Robo", "monstro": "robo",
     "dica": "monstro novo: quem e mordido pode virar um", "precos": (500,)},
)

LINHA_A, LINHA_PASSO, LINHA_L = 60, 66, 760
TOPO = 96
COR_LINHA = (34, 28, 52)
COR_BORDA = (86, 76, 116)
COR_APAGADO = (150, 144, 164)


# ------------------------------------------------------------------ regras
def maximo(item):
    return item.get("estoque", len(item["precos"]))


def preco(item):
    """Preco da proxima compra, ou None se nao ha mais o que comprar."""
    n = progresso.nivel(item["id"])
    if n >= maximo(item):
        return None
    return item["precos"][min(n, len(item["precos"]) - 1)]


def comprar(item):
    valor = preco(item)
    if valor is None or progresso.dados["moedas"] < valor:
        return False
    progresso.dados["moedas"] -= valor
    progresso.definir_nivel(item["id"], progresso.nivel(item["id"]) + 1)
    progresso.salvar()
    return True


def monstros_comprados():
    """Tipos de zumbi dos monstros ja liberados."""
    tipos = []
    for item in ITENS:
        if "monstro" in item and progresso.nivel(item["id"]):
            tipo = recursos.tipo_do_monstro(item["monstro"])
            if tipo is not None:
                tipos.append(tipo)
    return tipos


def itens_a_venda():
    """O catalogo, sem os monstros que nao tem sprite no disco."""
    return [i for i in ITENS
            if "monstro" not in i or recursos.tipo_do_monstro(i["monstro"]) is not None]


# -------------------------------------------------------------------- tela
class Loja:
    def __init__(self, jogo):
        self.jogo = jogo            # so pra usar as fontes e o texto com sombra
        self.itens = itens_a_venda()
        self.escolhido = 0
        self.recusa = 0.0           # pisca o preco quando falta moeda

    def rect(self, i):
        r = pygame.Rect(0, 0, LINHA_L, LINHA_A)
        r.midtop = (cfg.LARGURA // 2, TOPO + i * LINHA_PASSO)
        return r

    def item_em(self, pos):
        for i in range(len(self.itens)):
            if self.rect(i).collidepoint(pos):
                return i
        return None

    def evento(self, ev):
        """Devolve False quando o jogador pede pra sair da loja."""
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return False
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.escolhido = (self.escolhido - 1) % len(self.itens)
                sons.tocar("clique")
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.escolhido = (self.escolhido + 1) % len(self.itens)
                sons.tocar("clique")
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.tentar(self.escolhido)
        elif ev.type == pygame.MOUSEMOTION:
            i = self.item_em(ev.pos)
            if i is not None:
                self.escolhido = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.rect_voltar().collidepoint(ev.pos):
                return False
            i = self.item_em(ev.pos)
            if i is not None:
                self.escolhido = i
                self.tentar(i)
        return True

    def tentar(self, i):
        if comprar(self.itens[i]):
            sons.tocar("poder")
        elif preco(self.itens[i]) is not None:
            self.recusa = 0.5
            sons.tocar("parede")

    def atualizar(self, dt):
        self.recusa = max(0.0, self.recusa - dt)

    def rect_voltar(self):
        r = pygame.Rect(0, 0, 150, 34)
        r.topleft = (24, 26)
        return r

    # ---------------------------------------------------------------- desenho
    def desenhar(self, tela):
        j = self.jogo
        j.veu()
        cx = cfg.LARGURA // 2
        j.texto("LOJA", j.fonte_g, cx, 46, cfg.COR_ZUMBI, True)
        moedas = f"Moedas: {progresso.dados['moedas']}"
        j.texto(moedas, j.fonte, cfg.LARGURA - 24 - j.fonte.size(moedas)[0], 30,
                cfg.COR_MOEDA)
        r = self.rect_voltar()
        pygame.draw.rect(tela, COR_LINHA, r, border_radius=8)
        pygame.draw.rect(tela, COR_BORDA, r, 2, border_radius=8)
        j.texto("< ESC voltar", j.fonte_p, r.centerx, r.centery, centro=True)

        for i, item in enumerate(self.itens):
            self.desenhar_item(tela, i, item)
        j.texto("Setas escolhem  -  ENTER compra  -  as moedas das partidas vem pra ca",
                j.fonte_p, cx, cfg.ALTURA - 22, centro=True)

    def desenhar_item(self, tela, i, item):
        j = self.jogo
        r = self.rect(i)
        escolhido = i == self.escolhido
        if escolhido:
            pygame.draw.rect(tela, cfg.COR_ZUMBI_ESCURO, r.inflate(8, 8), border_radius=14)
        pygame.draw.rect(tela, COR_LINHA, r, border_radius=10)
        pygame.draw.rect(tela, cfg.COR_ZUMBI if escolhido else COR_BORDA, r, 2,
                         border_radius=10)

        icone = self.icone(item)
        if icone is not None:
            tela.blit(icone, icone.get_rect(center=(r.x + 38, r.centery)))
        j.texto(item["nome"], j.fonte, r.x + 76, r.y + 6)
        j.texto(item["dica"], j.fonte_p, r.x + 76, r.y + 34, COR_APAGADO)

        # bolinhas: uma por nivel (ou por unidade em estoque)
        n, total = progresso.nivel(item["id"]), maximo(item)
        if total > 1:
            x = r.x + 86 + j.fonte.size(item["nome"])[0]
            for k in range(total):
                cor = cfg.COR_MOEDA if k < n else (70, 64, 90)
                pygame.draw.circle(tela, cor, (x + k * 16, r.y + 20), 5)

        valor = preco(item)
        if valor is None:
            rotulo = "LIBERADO" if "monstro" in item else \
                     ("CHEIO" if "estoque" in item else "MAXIMO")
            cor = cfg.COR_ZUMBI
        else:
            rotulo = f"{valor} moedas"
            falta = progresso.dados["moedas"] < valor
            cor = COR_APAGADO if falta else cfg.COR_MOEDA
            if falta and escolhido and self.recusa > 0 and int(self.recusa * 12) % 2 == 0:
                cor = (236, 96, 96)
        j.texto(rotulo, j.fonte, r.right - 18 - j.fonte.size(rotulo)[0], r.y + 16, cor)

    def icone(self, item):
        if "monstro" in item:
            tipo = recursos.tipo_do_monstro(item["monstro"])
            sprite = recursos.zumbi(tipo, 2) if tipo is not None else None
            if sprite is not None and not progresso.nivel(item["id"]):
                # ainda trancado: so a silhueta
                sprite = sprite.copy()
                sprite.fill((60, 54, 78, 255), special_flags=pygame.BLEND_RGB_MULT)
            return sprite
        return recursos.icone_loja(item["icone"])
