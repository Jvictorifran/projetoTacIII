"""Loop principal, estados e regras da horda."""

import random

import pygame

from jogo import config as cfg
from jogo.entidades import Zumbi
from jogo.mundo import Mundo

MENU, JOGANDO, FIM = "menu", "jogando", "fim"


class Particula:
    def __init__(self, x, y, cor):
        self.x, self.y = x, y
        self.vx = random.uniform(-160, 160)
        self.vy = random.uniform(-320, -80)
        self.vida = random.uniform(0.4, 0.9)
        self.cor = cor

    def atualizar(self, dt):
        self.vx *= 0.98
        self.vy += cfg.GRAVIDADE * 0.5 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vida -= dt

    def desenhar(self, tela, camera_x):
        if self.vida > 0:
            tam = max(2, int(self.vida * 8))
            pygame.draw.rect(tela, self.cor, (self.x - camera_x, self.y, tam, tam))


class Jogo:
    def __init__(self):
        pygame.init()
        self.tela = pygame.display.set_mode((cfg.LARGURA, cfg.ALTURA))
        pygame.display.set_caption(cfg.TITULO)
        self.relogio = pygame.time.Clock()
        self.fonte = pygame.font.SysFont("arialbold,arial", 24, bold=True)
        self.fonte_g = pygame.font.SysFont("arialbold,arial", 56, bold=True)
        self.fonte_p = pygame.font.SysFont("arialbold,arial", 18)
        self.recorde = 0
        self.estado = MENU
        self.reiniciar()

    # ------------------------------------------------------------- partida
    def reiniciar(self):
        self.mundo = Mundo()
        self.camera_x = 0.0
        self.velocidade = cfg.VEL_INICIAL
        self.tempo = 0.0
        self.moedas = 0
        self.buffer_pulo = 0.0
        self.particulas = []
        self.tremor = 0.0
        self.zumbis = [Zumbi(cfg.X_LIDER, cfg.CHAO_Y, 0)]

    @property
    def metros(self):
        return int(self.camera_x / 50)

    def pontuacao(self):
        return self.metros + self.moedas * 5

    # -------------------------------------------------------------- entrada
    def processar_eventos(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return False
                if ev.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    self.acionar()
                if ev.key == pygame.K_r and self.estado == FIM:
                    self.reiniciar()
                    self.estado = JOGANDO
            if ev.type == pygame.KEYUP:
                if ev.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    self.cortar_pulo()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                self.acionar()
            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                self.cortar_pulo()
        return True

    def acionar(self):
        if self.estado == MENU:
            self.estado = JOGANDO
        elif self.estado == FIM:
            self.reiniciar()
            self.estado = JOGANDO
        else:
            self.buffer_pulo = 0.12

    def cortar_pulo(self):
        """Solta a tecla cedo = pulo mais baixo."""
        for z in self.zumbis:
            if z.vy < cfg.VEL_PULO * cfg.PULO_CURTO:
                z.vy = cfg.VEL_PULO * cfg.PULO_CURTO

    # ----------------------------------------------------------- atualizar
    def atualizar(self, dt):
        if self.estado != JOGANDO:
            for p in self.particulas:
                p.atualizar(dt)
            self.particulas = [p for p in self.particulas if p.vida > 0]
            return

        self.tempo += dt
        self.velocidade = min(cfg.VEL_MAXIMA, cfg.VEL_INICIAL + cfg.ACELERACAO * self.tempo)
        self.camera_x += self.velocidade * dt
        self.tremor = max(0.0, self.tremor - dt * 3)

        lider_x = min((z.x for z in self.zumbis), default=self.camera_x)
        self.mundo.atualizar(dt, self.camera_x, self.velocidade, lider_x)

        if self.buffer_pulo > 0:
            self.buffer_pulo -= dt
            if any(z.no_chao or z.coyote > 0 for z in self.zumbis):
                for z in self.zumbis:
                    z.pular()
                self.buffer_pulo = 0.0

        alvo_lider = self.camera_x + cfg.X_LIDER
        total = len(self.zumbis)
        for z in self.zumbis:
            z.atualizar(dt, self.mundo, alvo_lider, total)
            # quem fica muito pra tras e sai da tela se perde
            if z.x < self.camera_x - 40:
                z.vivo = False

        self.colisoes()

        mortos = [z for z in self.zumbis if not z.vivo]
        for z in mortos:
            self.explodir(z.x, z.y - cfg.ZUMBI_A / 2, cfg.COR_ZUMBI)
        if mortos:
            self.tremor = min(1.0, self.tremor + 0.4)
        self.zumbis = [z for z in self.zumbis if z.vivo]
        self.reindexar()

        for p in self.particulas:
            p.atualizar(dt)
        self.particulas = [p for p in self.particulas if p.vida > 0]

        if not self.zumbis:
            self.recorde = max(self.recorde, self.pontuacao())
            self.estado = FIM

    def reindexar(self):
        for i, z in enumerate(sorted(self.zumbis, key=lambda z: z.indice)):
            z.indice = i

    def colisoes(self):
        for z in self.zumbis:
            if not z.vivo:
                continue
            rz = z.rect

            for o in self.mundo.obstaculos:
                if o.vivo and rz.colliderect(o.rect):
                    o.atingir()
                    z.vivo = False
                    self.explodir(o.x, o.y - o.altura / 2, cfg.COR_OBSTACULO)
                    break
            if not z.vivo:
                continue

            for h in self.mundo.humanos:
                if h.vivo and rz.colliderect(h.rect):
                    h.vivo = False
                    self.converter(h)

            for m in self.mundo.moedas:
                if m.vivo and rz.colliderect(m.rect):
                    m.vivo = False
                    self.moedas += 1
                    self.explodir(m.x, m.y, cfg.COR_MOEDA, 5)

    def converter(self, humano):
        if len(self.zumbis) >= cfg.MAX_ZUMBIS:
            return
        indice = max((z.indice for z in self.zumbis), default=-1) + 1
        novo = Zumbi(humano.x, humano.y, indice)
        novo.vy = humano.vy
        novo.no_chao = humano.no_chao
        self.zumbis.append(novo)
        self.explodir(humano.x, humano.y - cfg.HUMANO_A / 2, cfg.COR_ZUMBI, 6)

    def explodir(self, x, y, cor, n=10):
        for _ in range(n):
            self.particulas.append(Particula(x, y, cor))

    # ------------------------------------------------------------- desenho
    def desenhar(self):
        tela = self.tela
        cam = self.camera_x
        if self.tremor > 0:
            cam += random.uniform(-6, 6) * self.tremor

        self.mundo.desenhar_fundo(tela, cam)
        self.mundo.desenhar(tela, cam)

        for z in sorted(self.zumbis, key=lambda z: (-(z.indice % cfg.LARG_FORMACAO), -z.indice)):
            z.desenhar(tela, cam)
        for p in self.particulas:
            p.desenhar(tela, cam)

        self.desenhar_hud()
        if self.estado == MENU:
            self.painel("ZUMBI TSUNAMI", "ESPACO ou clique para comecar",
                        "Segure para pular mais alto - toda a horda pula junto")
        elif self.estado == FIM:
            self.painel("FIM DE JOGO",
                        f"{self.metros} m  -  {self.moedas} moedas  -  {self.pontuacao()} pts",
                        "R ou ESPACO para jogar de novo")
        pygame.display.flip()

    def texto(self, txt, fonte, x, y, cor=cfg.COR_TEXTO, centro=False):
        s = fonte.render(txt, True, cor)
        sombra = fonte.render(txt, True, cfg.COR_SOMBRA)
        r = s.get_rect()
        if centro:
            r.center = (x, y)
        else:
            r.topleft = (x, y)
        self.tela.blit(sombra, r.move(2, 2))
        self.tela.blit(s, r)

    def desenhar_hud(self):
        self.texto(f"Zumbis: {len(self.zumbis)}", self.fonte, 16, 14, cfg.COR_ZUMBI)
        self.texto(f"{self.metros} m", self.fonte, 16, 44)
        self.texto(f"Moedas: {self.moedas}", self.fonte, 16, 74, cfg.COR_MOEDA)
        if self.recorde:
            self.texto(f"Recorde: {self.recorde}", self.fonte_p,
                       cfg.LARGURA - 16 - self.fonte_p.size(f"Recorde: {self.recorde}")[0], 16)

    def painel(self, titulo, linha1, linha2):
        veu = pygame.Surface((cfg.LARGURA, cfg.ALTURA), pygame.SRCALPHA)
        veu.fill((10, 8, 18, 170))
        self.tela.blit(veu, (0, 0))
        cx = cfg.LARGURA // 2
        self.texto(titulo, self.fonte_g, cx, cfg.ALTURA // 2 - 60, cfg.COR_ZUMBI, True)
        self.texto(linha1, self.fonte, cx, cfg.ALTURA // 2 + 10, centro=True)
        self.texto(linha2, self.fonte_p, cx, cfg.ALTURA // 2 + 50, centro=True)

    # ---------------------------------------------------------------- loop
    def rodar(self):
        rodando = True
        while rodando:
            dt = min(self.relogio.tick(cfg.FPS) / 1000.0, 0.05)
            rodando = self.processar_eventos()
            self.atualizar(dt)
            self.desenhar()
        pygame.quit()
