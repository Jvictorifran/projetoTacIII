"""Geracao procedural do cenario: plataformas, buracos, obstaculos e itens."""

import random

import pygame

from jogo import config as cfg
from jogo.entidades import Humano, Moeda, Obstaculo

TEMPO_NO_AR = 2 * abs(cfg.VEL_PULO) / cfg.GRAVIDADE


class Segmento:
    """Um pedaco continuo de chao."""

    def __init__(self, x, largura, topo, nivel):
        self.x = float(x)
        self.largura = float(largura)
        self.topo = float(topo)
        self.nivel = nivel

    @property
    def fim(self):
        return self.x + self.largura

    def contem(self, x):
        return self.x <= x <= self.fim


class Mundo:
    def __init__(self):
        self.segmentos = []
        self.obstaculos = []
        self.humanos = []
        self.moedas = []
        self.predios = []
        base = Segmento(-400, 1600, cfg.CHAO_Y, 0)
        self.segmentos.append(base)
        self._gerar_predios(-400, 2000)

    # ------------------------------------------------------------------ chao
    def chao_em(self, x):
        """Altura do topo do chao na posicao x, ou None se for buraco."""
        for seg in self.segmentos:
            if seg.contem(x):
                return seg.topo
        return None

    # -------------------------------------------------------------- geracao
    def atualizar(self, dt, camera_x, velocidade, lider_x):
        limite = camera_x + cfg.LARGURA * 2
        while self.segmentos[-1].fim < limite:
            self._gerar_segmento(velocidade)
        if self.predios and self.predios[-1][0] < limite:
            self._gerar_predios(self.predios[-1][0], limite + 600)

        self._limpar(camera_x - 300)

        for o in self.obstaculos:
            o.atualizar(dt)
        for h in self.humanos:
            h.atualizar(dt, self, lider_x)
        for m in self.moedas:
            m.atualizar(dt)
        self.humanos = [h for h in self.humanos if h.vivo]

    def _limpar(self, minimo):
        self.segmentos = [s for s in self.segmentos if s.fim > minimo]
        self.obstaculos = [o for o in self.obstaculos if o.vivo and o.x > minimo]
        self.humanos = [h for h in self.humanos if h.x > minimo - 200]
        self.moedas = [m for m in self.moedas if m.vivo and m.x > minimo]
        self.predios = [p for p in self.predios if p[0] + p[2] > minimo - 1200]

    def _gerar_segmento(self, velocidade):
        anterior = self.segmentos[-1]
        alcance = velocidade * TEMPO_NO_AR

        nivel = anterior.nivel
        if random.random() < 0.35:
            nivel = max(0, min(cfg.NIVEIS - 1, nivel + random.choice((-1, 1))))

        if nivel > anterior.nivel:
            # subida: buraco curto, senao vira pulo de precisao impossivel
            buraco = random.uniform(0.10, 0.22) * alcance
        elif nivel < anterior.nivel:
            buraco = random.uniform(0.25, 0.45) * alcance
        elif random.random() < 0.55:
            buraco = random.uniform(0.30, 0.55) * alcance
        else:
            buraco = 0.0

        largura = random.uniform(1.6, 3.0) * alcance
        topo = cfg.CHAO_Y - nivel * cfg.ALTURA_NIVEL
        seg = Segmento(anterior.fim + buraco, largura, topo, nivel)
        self.segmentos.append(seg)

        if buraco > 40 and random.random() < 0.6:
            self._arco_de_moedas(anterior.fim, seg.x, min(anterior.topo, topo))
        self._povoar(seg, alcance)

    def _povoar(self, seg, alcance):
        # margens livres: zona de pouso no inicio e espaco pro pulo no fim,
        # proporcionais ao alcance do pulo na velocidade atual
        ini = seg.x + 0.85 * alcance
        fim = seg.fim - 1.15 * alcance   # da pra pular o obstaculo e ainda pousar
        if seg.x > cfg.INICIO_SEGURO and fim > ini:
            ultimo_x = ini - 200
            for _ in range(random.choice((0, 1, 1, 2, 2, 3))):
                x = random.uniform(max(ini, ultimo_x + 170), fim)
                if x <= ultimo_x + 160:
                    break
                self.obstaculos.append(Obstaculo(x, seg.topo, random.randint(1, 4)))
                ultimo_x = x
        # humanos fugindo (mais gente no comeco pra horda crescer rapido)
        quantidade = random.randint(2, 4) if seg.x < cfg.INICIO_SEGURO else random.choice((0, 1, 1, 2, 3))
        for _ in range(quantidade):
            x = random.uniform(seg.x + 60, seg.fim - 40)
            self.humanos.append(Humano(x, seg.topo))
        # moedas sobre a plataforma
        if random.random() < 0.5:
            x = random.uniform(seg.x + 80, max(seg.x + 90, seg.fim - 160))
            for i in range(random.randint(3, 6)):
                self.moedas.append(Moeda(x + i * 34, seg.topo - 60))

    def _arco_de_moedas(self, x_ini, x_fim, topo):
        n = 6
        largura = x_fim - x_ini
        for i in range(n):
            t = (i + 0.5) / n
            x = x_ini + largura * t
            y = topo - 40 - 90 * (1 - (2 * t - 1) ** 2)
            self.moedas.append(Moeda(x, y))

    # ------------------------------------------------------------- cenario
    def _gerar_predios(self, x_ini, x_fim):
        x = x_ini
        while x < x_fim:
            larg = random.randint(60, 130)
            alt = random.randint(90, 260)
            camada = random.choice((0, 0, 1))
            self.predios.append((x, alt, larg, camada))
            x += larg + random.randint(10, 40)

    # -------------------------------------------------------------- desenho
    def desenhar_fundo(self, tela, camera_x):
        for i in range(cfg.ALTURA):
            t = i / cfg.ALTURA
            cor = [int(a + (b - a) * t) for a, b in zip(cfg.COR_CEU_TOPO, cfg.COR_CEU_BASE)]
            pygame.draw.line(tela, cor, (0, i), (cfg.LARGURA, i))
        pygame.draw.circle(tela, cfg.COR_LUA, (cfg.LARGURA - 140, 90), 44)
        pygame.draw.circle(tela, cfg.COR_CEU_TOPO, (cfg.LARGURA - 158, 78), 40)

        for x, alt, larg, camada in self.predios:
            fator = 0.25 if camada == 0 else 0.5
            px = int(x - camera_x * fator) % (cfg.LARGURA + 2400) - 400
            cor = cfg.COR_PREDIO_LONGE if camada == 0 else cfg.COR_PREDIO_PERTO
            r = pygame.Rect(px, cfg.CHAO_Y - alt, larg, alt)
            pygame.draw.rect(tela, cor, r)
            for jy in range(r.top + 14, r.top + alt - 10, 26):
                for jx in range(r.left + 10, r.right - 12, 22):
                    if (jx + jy) % 3:
                        pygame.draw.rect(tela, cfg.COR_JANELA, (jx, jy, 7, 10))

    def desenhar(self, tela, camera_x):
        # o vao abaixo do nivel base vira abismo, pra leitura dos buracos
        pygame.draw.rect(tela, cfg.COR_ABISMO,
                         (0, cfg.CHAO_Y, cfg.LARGURA, cfg.ALTURA - cfg.CHAO_Y))
        # cada buraco vira uma coluna escura bem visivel
        for a, b in zip(self.segmentos, self.segmentos[1:]):
            if b.x > a.fim + 1:
                topo = min(a.topo, b.topo)
                pygame.draw.rect(tela, cfg.COR_ABISMO,
                                 (int(a.fim - camera_x), int(topo),
                                  int(b.x - a.fim), cfg.ALTURA - int(topo)))
        for seg in self.segmentos:
            r = pygame.Rect(int(seg.x - camera_x), int(seg.topo),
                            int(seg.largura), cfg.ALTURA - int(seg.topo))
            pygame.draw.rect(tela, cfg.COR_CHAO, r)
            pygame.draw.rect(tela, cfg.COR_CHAO_LADO, (r.x, r.y, 4, r.height))
            pygame.draw.rect(tela, cfg.COR_CHAO_LADO, (r.right - 4, r.y, 4, r.height))
            pygame.draw.rect(tela, cfg.COR_CHAO_TOPO, (r.x, r.y, r.width, 9))
            # riscos de asfalto pra dar sensacao de velocidade
            for x in range(r.x - (int(camera_x) % 60), r.right, 60):
                if r.x < x < r.right - 8:
                    pygame.draw.rect(tela, cfg.COR_CHAO_LADO, (x, r.y + 26, 26, 4))
        for m in self.moedas:
            m.desenhar(tela, camera_x)
        for o in self.obstaculos:
            o.desenhar(tela, camera_x)
        for h in self.humanos:
            h.desenhar(tela, camera_x)
