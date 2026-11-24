"""Entidades do jogo: caixas de poder, zumbis, humanos, obstaculos e moedas."""

import math
import random

import pygame

from jogo import config as cfg
from jogo import poderes
from jogo import recursos


class Box:
    """Caixa de poder. Encostar nela ativa o poder sorteado no nascimento.

    O poder ja vem sorteado na criacao porque a tampa mostra o icone dele: o
    jogador ve de longe o que vai ganhar e decide se vale o desvio.
    """

    altura, largura = cfg.CAIXA_A, cfg.CAIXA_L

    def __init__(self, x, y, poder=None):
        self.x = float(x)
        self.y = float(y)          # base
        self.vivo = True
        self.poder = poder if poder is not None else random.choice(poderes.TODOS)
        self.fase = random.uniform(0, math.tau)

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.largura / 2),
            int(self.y - self.altura + self._flutua()),
            self.largura,
            self.altura,
        )

    def _flutua(self):
        return math.sin(self.fase) * cfg.CAIXA_FLUTUA

    def atualizar(self, dt):
        self.fase += dt * 3.0

    def colidir(self):
        self.vivo = False
        return self.poder

    def desenhar(self, tela, camera_x):
        r = self.rect.move(-camera_x, 0)
        cor = poderes.cor(self.poder)
        # halo pulsante na cor do poder: e o que faz a caixa saltar do cenario
        raio = int(self.largura * 0.75 + math.sin(self.fase * 2) * 4)
        pygame.draw.circle(tela, cor, r.center, raio, 3)

        sprite = recursos.caixa()
        if sprite is not None:
            tela.blit(sprite, sprite.get_rect(center=r.center))
        else:
            pygame.draw.rect(tela, (96, 60, 30), r.inflate(6, 6), border_radius=6)
            pygame.draw.rect(tela, cfg.COR_CAIXA, r, border_radius=4)

        icone = recursos.icone(self.poder)
        if icone is not None:
            tela.blit(icone, icone.get_rect(center=r.center))
        else:
            pygame.draw.circle(tela, cor, r.center, 12)


class Corpo:
    """Base com fisica simples de plataforma (gravidade + colisao com o chao)."""

    largura = 24
    altura = 34

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)          # y = base (pes) da entidade
        self.vy = 0.0
        self.no_chao = False
        self.coyote = 0.0
        self.vivo = True
        self.na_parede = False     # encostado na parede de um buraco
        self.bateu = False         # acabou de bater nela (o jogo le e zera)

    def andar(self, novo_x, mundo):
        """Anda ate `novo_x`, mas para na parede da plataforma da frente.

        Quem cai no buraco nao atravessa mais o chao do outro lado: da de
        cara na parede e escorrega por ela ate sumir la embaixo.
        """
        if novo_x > self.x:
            meia = self.largura / 2
            parede = mundo.parede_em(novo_x + meia, self.y)
            # vale tambem pra quem ja enfiou a frente na parede enquanto
            # ainda estava na folga da beirada e depois caiu abaixo dela
            if parede is not None and self.x <= parede + meia:
                novo_x = min(novo_x, parede - meia)
                if not self.na_parede:
                    self.bateu = True
                self.na_parede = True
                self.x = novo_x
                return
        self.na_parede = False
        self.x = novo_x

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.largura / 2),
            int(self.y - self.altura),
            self.largura,
            self.altura,
        )

    def aplicar_fisica(self, dt, mundo, escala_gravidade=1.0):
        self.vy += cfg.GRAVIDADE * escala_gravidade * dt
        self.y += self.vy * dt

        self.coyote = max(0.0, self.coyote - dt)
        topo = mundo.chao_em(self.x)
        if topo is not None and self.vy >= 0 and self.y >= topo:
            # so "cai" na plataforma se vinha de cima dela
            if self.y - self.vy * dt <= topo + cfg.FOLGA_BEIRADA:
                self.y = topo
                self.vy = 0.0
                self.no_chao = True
                self.coyote = cfg.COYOTE
                self.aterrissar()
                return
        self.no_chao = False

        if self.y > cfg.ALTURA + 200:
            self.vivo = False

    def aterrissar(self):
        """Gancho pra quem precisa reagir ao pouso (o zumbi zera os pulos)."""


class Zumbi(Corpo):
    largura = cfg.ZUMBI_L
    altura = cfg.ZUMBI_A

    def __init__(self, x, y, indice, tipo=None):
        super().__init__(x, y)
        self.indice = indice
        self.fase = random.uniform(0, math.tau)   # anima o balanco das pernas
        self.tremor = random.uniform(-4, 4)
        # cada zumbi puxa um sprite diferente: a massa fica menos repetitiva
        base = recursos.tipos_base()
        self.tipo = tipo if tipo is not None else (random.choice(base) if base else 0)
        self.anim = random.uniform(0, 5)          # comeca fora de sincronia
        self.pulos = 0                            # pulos gastos desde o chao

    def deslocamento_formacao(self, total):
        """Posicao relativa ao lider dentro do bloco da horda.

        Quanto maior a horda, mais apertado o bloco fica, pra nao sair da tela.
        """
        espaco = max(11.0, 22.0 - total * 0.12)
        coluna = self.indice // cfg.LARG_FORMACAO
        linha = self.indice % cfg.LARG_FORMACAO
        dx = -coluna * espaco - (linha % 2) * espaco * 0.5
        return dx + self.tremor

    @property
    def linha(self):
        return self.indice % cfg.LARG_FORMACAO

    def atualizar(self, dt, mundo, alvo_lider_x, total=1, poder=None, subindo=False):
        alvo = alvo_lider_x + self.deslocamento_formacao(total)
        # aproximacao suave do slot na formacao
        novo_x = self.x + (alvo - self.x) * min(1.0, dt * 7.0)
        if poder == poderes.DRAGAO:
            self.x = novo_x             # voando ninguem bate em parede
            self.na_parede = False
        else:
            self.andar(novo_x, mundo)
        self.fase += dt * 12
        self.anim += dt * cfg.ZUMBI_FPS_ANIM

        if poder == poderes.DRAGAO:
            self._voar(dt, mundo, subindo)
        elif poder == poderes.BALAO:
            self.aplicar_fisica(dt, mundo, cfg.BALAO_GRAVIDADE)
        else:
            self.aplicar_fisica(dt, mundo)

        # sair da plataforma andando ja consome o pulo do chao: senao daria
        # pra "pular" no meio da queda mesmo sem o poder do balao
        if not self.no_chao and self.pulos == 0:
            self.pulos = 1
        # teto: com pulo duplo do balao a horda sairia pela parte de cima
        # (dentro do tunel o teto e o do vao, bem mais baixo)
        teto = mundo.teto_em(self.x) + self.altura
        if self.y < teto:
            self.y = teto
            self.vy = max(self.vy, 0.0)

    def _voar(self, dt, mundo, subindo):
        """Voo do poder dragao: sem gravidade e sem buraco que mate."""
        alvo_vy = cfg.DRAGAO_SUBIDA if subindo else cfg.DRAGAO_DESCIDA
        self.vy += (alvo_vy - self.vy) * min(1.0, dt * 8.0)
        self.y += self.vy * dt

        teto = max(cfg.DRAGAO_TETO, mundo.teto_em(self.x) + 8) + self.altura
        chao = mundo.chao_em(self.x)
        # sobre buraco nao ha chao: o piso vira a linha do nivel base, entao o
        # dragao passa por cima do vao em vez de cair nele
        piso = chao if chao is not None else cfg.CHAO_Y
        self.y = max(teto, min(self.y, piso))
        self.no_chao = False
        self.coyote = 0.0

    def aterrissar(self):
        self.pulos = 0

    def pode_pular(self, extras=0):
        return self.no_chao or self.coyote > 0 or self.pulos <= extras

    def pular(self, extras=0, forca=1.0):
        if self.no_chao or self.coyote > 0:
            self.pulos = 1
        elif self.pulos <= extras:
            self.pulos += 1
        else:
            return
        self.vy = cfg.VEL_PULO * forca
        self.no_chao = False
        self.coyote = 0.0

    def quadro(self):
        """Indice do quadro: no ar a pose e fixa, no chao roda o ciclo."""
        if not self.no_chao:
            return cfg.QUADRO_SUBINDO if self.vy < 0 else cfg.QUADRO_CAINDO
        return int(self.anim)

    # ------------------------------------------------------------- desenho
    def desenhar(self, tela, camera_x, poder=None, total=1):
        # gigante e dragao nao passam por aqui: neles a horda inteira vira um
        # bicho so, desenhado pelo jogo
        self._desenhar_normal(tela, camera_x)
        if poder == poderes.BALAO:
            # horda grande: so parte dos zumbis leva balao, senao vira um borrao
            passo = 1 if total <= 14 else (2 if total <= 40 else 3)
            if self.indice % passo == 0:
                self._desenhar_balao(tela, camera_x)

    def _desenhar_normal(self, tela, camera_x):
        # linhas de tras sobem um pouco e escurecem: da profundidade a massa
        sprite = recursos.zumbi(self.tipo, self.quadro(), self.linha)
        if sprite is None:
            self._desenhar_formas(tela, camera_x, self.linha)
            return
        r = sprite.get_rect()
        r.midbottom = (int(self.x - camera_x), int(self.y) - self.linha * cfg.RECUO_LINHA)
        tela.blit(sprite, r)

    def _desenhar_balao(self, tela, camera_x):
        balao = recursos.balao(self.indice)
        mao = (int(self.x - camera_x) + 4,
               int(self.y) - self.altura + 6 - self.linha * cfg.RECUO_LINHA)
        # o balao balanca devagar, cada um no seu tempo
        vento = math.sin(self.fase * 0.22 + self.indice) * 5
        if balao is None:
            pygame.draw.circle(tela, poderes.cor(poderes.BALAO),
                               (mao[0] + vento, mao[1] - 26), 9)
            return
        r = balao.get_rect()
        r.midbottom = (mao[0] + vento, mao[1] - cfg.BALAO_FIO)
        meio = ((mao[0] + r.centerx) // 2 - vento * 0.4, (mao[1] + r.bottom) // 2)
        pygame.draw.lines(tela, (236, 232, 240), False, (mao, meio, r.midbottom), 1)
        tela.blit(balao, r)

    def _desenhar_formas(self, tela, camera_x, linha):
        """Desenho de reserva, usado quando nao ha sprite carregado."""
        pulo = math.sin(self.fase) * 3 if self.no_chao else 0
        r = self.rect.move(-camera_x, -pulo - linha * cfg.RECUO_LINHA)
        sombra = 1.0 - linha * cfg.SOMBRA_LINHA
        claro = tuple(int(c * sombra) for c in cfg.COR_ZUMBI)
        escuro = tuple(int(c * sombra) for c in cfg.COR_ZUMBI_ESCURO)
        # contorno escuro separa os zumbis dentro da massa
        pygame.draw.rect(tela, (24, 40, 20), r.inflate(4, 4), border_radius=7)
        pygame.draw.rect(tela, escuro, r, border_radius=6)
        pygame.draw.rect(tela, claro, r.inflate(-7, -10), border_radius=5)
        # bracos esticados pra frente
        pygame.draw.line(tela, (24, 40, 20),
                         (r.centerx, r.top + 17), (r.right + 7, r.top + 15 + pulo), 5)
        pygame.draw.line(tela, escuro,
                         (r.centerx, r.top + 17), (r.right + 6, r.top + 15 + pulo), 3)
        # cabeca
        cabeca = pygame.Rect(0, 0, 18, 16)
        cabeca.center = (r.centerx + 1, r.top + 2)
        pygame.draw.rect(tela, (24, 40, 20), cabeca.inflate(4, 4), border_radius=6)
        pygame.draw.rect(tela, claro, cabeca, border_radius=5)
        pygame.draw.circle(tela, (250, 250, 250), (cabeca.centerx + 4, cabeca.centery), 3)
        pygame.draw.circle(tela, (250, 250, 250), (cabeca.centerx - 3, cabeca.centery), 3)
        pygame.draw.circle(tela, (20, 20, 20), (cabeca.centerx + 5, cabeca.centery), 1)
        pygame.draw.circle(tela, (20, 20, 20), (cabeca.centerx - 2, cabeca.centery), 1)


class Humano(Corpo):
    largura = cfg.HUMANO_L
    altura = cfg.HUMANO_A

    def __init__(self, x, y):
        super().__init__(x, y)
        self.fase = random.uniform(0, math.tau)
        self.velocidade = cfg.VEL_HUMANO * random.uniform(0.9, 1.1)
        self.direcao = random.choice((-1, 1))
        self.panico = False
        self.gritou = False         # o grito sai uma vez so, quando ve a horda
        tipos = recursos.total_humanos()
        self.tipo = random.randrange(tipos) if tipos else 0
        self.anim = random.uniform(0, 5)

    def atualizar(self, dt, mundo, ameaca_x):
        if not self.panico and self.x - ameaca_x < cfg.RAIO_PANICO:
            self.panico = True

        if self.panico:
            self.andar(self.x + self.velocidade * dt, mundo)
            self.fase += dt * 18
            self.anim += dt * cfg.HUMANO_FPS_ANIM
            self.direcao = 1
            # tenta pular o buraco pra fugir
            if self.no_chao and mundo.chao_em(self.x + 50) is None:
                self.vy = cfg.VEL_PULO * 0.8
                self.no_chao = False
        else:
            # passeia sem perceber a horda e volta na beirada
            if mundo.chao_em(self.x + self.direcao * 30) is None:
                self.direcao *= -1
            self.x += self.direcao * cfg.VEL_PASSEIO * dt
            self.fase += dt * 7
            self.anim += dt * cfg.HUMANO_FPS_PASSEIO

        self.aplicar_fisica(dt, mundo)

    def quadro(self):
        if not self.no_chao:
            return cfg.QUADRO_SUBINDO if self.vy < 0 else cfg.QUADRO_CAINDO
        return int(self.anim)

    def desenhar(self, tela, camera_x):
        sprite = recursos.humano(self.tipo, self.quadro())
        if sprite is None:
            self._desenhar_formas(tela, camera_x)
            return
        if self.direcao < 0:            # passeando pra esquerda: espelha
            sprite = pygame.transform.flip(sprite, True, False)
        r = sprite.get_rect()
        r.midbottom = (int(self.x - camera_x), int(self.y))
        tela.blit(sprite, r)

    def _desenhar_formas(self, tela, camera_x):
        r = self.rect.move(-camera_x, 0)
        pygame.draw.rect(tela, (18, 26, 46), r.inflate(4, 4), border_radius=7)
        pygame.draw.rect(tela, cfg.COR_HUMANO_ROUPA, r, border_radius=5)
        cabeca = pygame.Rect(0, 0, 15, 15)
        cabeca.center = (r.centerx, r.top + 3)
        pygame.draw.rect(tela, cfg.COR_HUMANO, cabeca, border_radius=5)
        pygame.draw.circle(tela, (40, 40, 40), (cabeca.centerx + 4, cabeca.centery), 2)
        perna = math.sin(self.fase) * 6 if self.no_chao else 3
        pygame.draw.line(tela, cfg.COR_HUMANO_ROUPA,
                         (r.centerx, r.bottom - 6), (r.centerx + perna, r.bottom + 2), 4)


class Obstaculo:
    """Carro / barricada. Cada zumbi que bate tira 1 de vida e morre."""

    def __init__(self, x, y, vida=3):
        self.x = float(x)
        self.y = float(y)          # base
        self.vida = vida
        self.vida_max = vida
        self.largura = cfg.OBSTACULO_L
        self.altura = cfg.OBSTACULO_A
        self.vivo = True
        self.impacto = 0.0

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.largura / 2),
            int(self.y - self.altura),
            self.largura,
            self.altura,
        )

    def atualizar(self, dt):
        self.impacto = max(0.0, self.impacto - dt * 4)

    def atingir(self):
        self.vida -= 1
        self.impacto = 1.0
        if self.vida <= 0:
            self.vivo = False

    def destruir(self):
        """Passagem da horda com poder: o obstaculo some de uma vez so."""
        self.vida = 0
        self.impacto = 1.0
        self.vivo = False

    def desenhar(self, tela, camera_x):
        r = self.rect.move(-camera_x, 0)
        if self.impacto > 0:
            r = r.move(random.randint(-2, 2), 0)
        pygame.draw.rect(tela, cfg.COR_OBSTACULO_ESCURO, r, border_radius=6)
        pygame.draw.rect(tela, cfg.COR_OBSTACULO, r.inflate(-8, -8), border_radius=4)
        pygame.draw.circle(tela, (35, 35, 40), (r.left + 12, r.bottom - 4), 7)
        pygame.draw.circle(tela, (35, 35, 40), (r.right - 12, r.bottom - 4), 7)
        # barra de vida
        for i in range(self.vida):
            pygame.draw.rect(tela, (250, 230, 120),
                             (r.left + 4 + i * 10, r.top - 10, 7, 5))


class Moeda:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)          # centro
        self.vivo = True
        self.fase = random.uniform(0, math.tau)
        self.atraida = False

    @property
    def rect(self):
        return pygame.Rect(int(self.x - cfg.MOEDA_R), int(self.y - cfg.MOEDA_R),
                           cfg.MOEDA_R * 2, cfg.MOEDA_R * 2)

    def atualizar(self, dt):
        self.fase += dt * 6
        self.atraida = False

    def atrair(self, dt, alvo_x, alvo_y):
        """Puxada do poder ima: a moeda persegue a horda."""
        t = min(1.0, dt * cfg.IMA_VELOCIDADE)
        self.x += (alvo_x - self.x) * t
        self.y += (alvo_y - self.y) * t
        self.atraida = True

    def desenhar(self, tela, camera_x):
        larg = abs(math.cos(self.fase)) * cfg.MOEDA_R + 2
        cx = int(self.x - camera_x)
        cy = int(self.y + math.sin(self.fase) * 3)
        if self.atraida:
            # puxada pelo ima: um brilho claro em volta
            pygame.draw.circle(tela, (255, 244, 190), (cx, cy), cfg.MOEDA_R + 3)
        pygame.draw.ellipse(tela, cfg.COR_MOEDA,
                            (cx - larg, cy - cfg.MOEDA_R, larg * 2, cfg.MOEDA_R * 2))
        pygame.draw.ellipse(tela, (200, 150, 30),
                            (cx - larg, cy - cfg.MOEDA_R, larg * 2, cfg.MOEDA_R * 2), 2)
