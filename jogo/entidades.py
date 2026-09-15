"""Entidades do jogo: zumbis, humanos, obstaculos e moedas."""

import math
import random

import pygame

from jogo import config as cfg

class Box:
    altura, largura = cfg.CAIXA_A, cfg.CAIXA_L
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vivo = True
        self.poder = random.choice(['poder1', 'poder2', 'poder3', 'poder4'])

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.largura/2),
            int(self.y - self.altura),
            self.largura,
            self.altura,
        )

    def colidir(self):
        self.vivo = False
        return self.poder

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

    @property
    def rect(self):
        return pygame.Rect(
            int(self.x - self.largura / 2),
            int(self.y - self.altura),
            self.largura,
            self.altura,
        )

    def aplicar_fisica(self, dt, mundo):
        self.vy += cfg.GRAVIDADE * dt
        self.y += self.vy * dt

        self.coyote = max(0.0, self.coyote - dt)
        topo = mundo.chao_em(self.x)
        if topo is not None and self.vy >= 0 and self.y >= topo:
            # so "cai" na plataforma se vinha de cima dela
            if self.y - self.vy * dt <= topo + 24:
                self.y = topo
                self.vy = 0.0
                self.no_chao = True
                self.coyote = cfg.COYOTE
                return
        self.no_chao = False

        if self.y > cfg.ALTURA + 200:
            self.vivo = False


class Zumbi(Corpo):
    largura = cfg.ZUMBI_L
    altura = cfg.ZUMBI_A

    def __init__(self, x, y, indice):
        super().__init__(x, y)
        self.indice = indice
        self.fase = random.uniform(0, math.tau)   # anima o balanco das pernas
        self.tremor = random.uniform(-4, 4)

    def deslocamento_formacao(self, total):
        """Posicao relativa ao lider dentro do bloco da horda.

        Quanto maior a horda, mais apertado o bloco fica, pra nao sair da tela.
        """
        espaco = max(11.0, 22.0 - total * 0.12)
        coluna = self.indice // cfg.LARG_FORMACAO
        linha = self.indice % cfg.LARG_FORMACAO
        dx = -coluna * espaco - (linha % 2) * espaco * 0.5
        return dx + self.tremor

    def atualizar(self, dt, mundo, alvo_lider_x, total=1):
        alvo = alvo_lider_x + self.deslocamento_formacao(total)
        # aproximacao suave do slot na formacao
        self.x += (alvo - self.x) * min(1.0, dt * 7.0)
        self.fase += dt * 12
        self.aplicar_fisica(dt, mundo)

    def pular(self):
        if self.no_chao or self.coyote > 0:
            self.vy = cfg.VEL_PULO
            self.no_chao = False
            self.coyote = 0.0

    def desenhar(self, tela, camera_x):
        pulo = math.sin(self.fase) * 3 if self.no_chao else 0
        # linhas de tras sobem um pouco e escurecem: da profundidade a massa
        linha = self.indice % cfg.LARG_FORMACAO
        r = self.rect.move(-camera_x, -pulo - linha * 5)
        sombra = 1.0 - linha * 0.11
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

    def atualizar(self, dt, mundo, ameaca_x):
        if not self.panico and self.x - ameaca_x < cfg.RAIO_PANICO:
            self.panico = True

        if self.panico:
            self.x += self.velocidade * dt
            self.fase += dt * 18
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

        self.aplicar_fisica(dt, mundo)

    def desenhar(self, tela, camera_x):
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

    @property
    def rect(self):
        return pygame.Rect(int(self.x - cfg.MOEDA_R), int(self.y - cfg.MOEDA_R),
                           cfg.MOEDA_R * 2, cfg.MOEDA_R * 2)

    def atualizar(self, dt):
        self.fase += dt * 6

    def desenhar(self, tela, camera_x):
        larg = abs(math.cos(self.fase)) * cfg.MOEDA_R + 2
        cx = int(self.x - camera_x)
        cy = int(self.y + math.sin(self.fase) * 3)
        pygame.draw.ellipse(tela, cfg.COR_MOEDA,
                            (cx - larg, cy - cfg.MOEDA_R, larg * 2, cfg.MOEDA_R * 2))
        pygame.draw.ellipse(tela, (200, 150, 30),
                            (cx - larg, cy - cfg.MOEDA_R, larg * 2, cfg.MOEDA_R * 2), 2)
