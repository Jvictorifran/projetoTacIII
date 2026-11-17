"""Loop principal, estados e regras da horda."""

import random

import pygame

from jogo import config as cfg
from jogo import poderes
from jogo import recursos
from jogo.cenario import Cenario
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
        recursos.carregar()     # sprites prontos antes do primeiro quadro
        self.relogio = pygame.time.Clock()
        self.fonte = pygame.font.SysFont("arialbold,arial", 24, bold=True)
        self.fonte_g = pygame.font.SysFont("arialbold,arial", 56, bold=True)
        self.fonte_p = pygame.font.SysFont("arialbold,arial", 18)
        self.recorde = 0
        self.cenario = Cenario()
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
        self.poder = None           # poder ativo, vindo de uma caixa
        self.poder_tempo = 0.0      # quanto falta dele
        self.aviso = 0.0            # tempo do aviso na tela ao pegar a caixa
        self.segurando = False      # tecla de pulo presa (o dragao usa isso)
        self.zumbis = [Zumbi(cfg.X_LIDER, cfg.CHAO_Y, 0, tipo=0)]

    @property
    def metros(self):
        return int(self.camera_x / cfg.PX_POR_METRO)

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
                    self.segurando = True
                    self.acionar()
                if ev.key == pygame.K_r and self.estado == FIM:
                    self.reiniciar()
                    self.estado = JOGANDO
            if ev.type == pygame.KEYUP:
                if ev.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    self.segurando = False
                    self.cortar_pulo()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                self.segurando = True
                self.acionar()
            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                self.segurando = False
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
        if self.poder == poderes.DRAGAO:
            return          # voando a tecla so controla a altura, nao o pulo
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

        self.atualizar_poder(dt)

        balao = self.poder == poderes.BALAO
        extras = cfg.BALAO_PULOS_EXTRA if balao else 0
        forca = cfg.BALAO_PULO if balao else 1.0
        if self.buffer_pulo > 0:
            self.buffer_pulo -= dt
            if self.poder == poderes.DRAGAO:
                self.buffer_pulo = 0.0      # voando, quem manda e segurar a tecla
            elif any(z.pode_pular(extras) for z in self.zumbis):
                for z in self.zumbis:
                    z.pular(extras, forca)
                self.buffer_pulo = 0.0

        alvo_lider = self.camera_x + cfg.X_LIDER
        total = len(self.zumbis)
        subindo = self.segurando and self.poder_tempo > 0
        for z in self.zumbis:
            z.atualizar(dt, self.mundo, alvo_lider, total, self.poder, subindo)
            # quem fica muito pra tras e sai da tela se perde
            if z.x < self.camera_x - 40:
                z.vivo = False

        self.atrair_moedas(dt)
        if self.poder == poderes.DRAGAO and self.zumbis:
            self.rastro_de_fogo()
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

    # --------------------------------------------------------------- poderes
    def ativar_poder(self, nome):
        """Pegar uma caixa troca o poder na hora, mesmo com outro rodando."""
        self.poder = nome
        self.poder_tempo = poderes.duracao(nome)
        self.aviso = 2.4
        self.tremor = min(1.0, self.tremor + 0.3)
        cor = poderes.cor(nome)
        for z in self.zumbis[:24]:
            self.explodir(z.x, z.y - cfg.ZUMBI_A / 2, cor, 3)

    def atualizar_poder(self, dt):
        self.aviso = max(0.0, self.aviso - dt)
        if not self.poder:
            return
        self.poder_tempo = max(0.0, self.poder_tempo - dt)
        if self.poder_tempo > 0:
            return
        # o voo nao pode acabar em cima de um buraco: a horda desce e so
        # perde as asas depois que tem chao embaixo dos pes
        if self.poder == poderes.DRAGAO and self.sobre_buraco():
            return
        self.encerrar_poder()

    def sobre_buraco(self):
        return any(self.mundo.chao_em(z.x) is None for z in self.zumbis)

    def encerrar_poder(self):
        if self.poder == poderes.DRAGAO:
            for z in self.zumbis:
                z.vy = max(z.vy, 0.0)       # solta a horda numa queda mansa
        self.poder = None
        self.poder_tempo = 0.0

    def atrair_moedas(self, dt):
        """Poder do ima: as moedas por perto perseguem o lider da horda."""
        if self.poder != poderes.IMA or not self.zumbis:
            return
        lider = max(self.zumbis, key=lambda z: z.x)
        ax, ay = lider.x, lider.y - cfg.ZUMBI_A / 2
        for m in self.mundo.moedas:
            if not m.vivo:
                continue
            if abs(m.x - ax) < cfg.IMA_RAIO and abs(m.y - ay) < cfg.IMA_RAIO:
                m.atrair(dt, ax, ay)

    def reindexar(self):
        for i, z in enumerate(sorted(self.zumbis, key=lambda z: z.indice)):
            z.indice = i

    def colisoes(self):
        # gigante e dragao passam por cima dos carros em vez de morrer neles
        arrasa = self.poder in (poderes.GIGANTE, poderes.DRAGAO)
        ganho = cfg.IMA_MULTIPLICADOR if self.poder == poderes.IMA else 1
        for z in self.zumbis:
            if not z.vivo:
                continue
            rz = z.rect
            if self.poder == poderes.GIGANTE:
                # o corpo desenhado e maior: o alcance acompanha
                rz = rz.inflate(cfg.GIGANTE_ALCANCE, cfg.GIGANTE_ALCANCE)

            for c in self.mundo.caixas:
                if c.vivo and rz.colliderect(c.rect):
                    self.ativar_poder(c.colidir())

            for o in self.mundo.obstaculos:
                if o.vivo and rz.colliderect(o.rect):
                    if arrasa:
                        o.destruir()
                        self.explodir(o.x, o.y - o.altura / 2, cfg.COR_FOGO, 16)
                        self.tremor = min(1.0, self.tremor + 0.25)
                    else:
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
                    self.moedas += ganho
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

    def rastro_de_fogo(self):
        """Faiscas saindo de tras da horda enquanto ela voa."""
        ultimo = min(self.zumbis, key=lambda z: z.x)
        for _ in range(2):
            p = Particula(ultimo.x - 6, ultimo.y - cfg.ZUMBI_A * 0.5, cfg.COR_FOGO)
            p.vx = random.uniform(-220, -60)
            p.vy = random.uniform(-40, 40)
            p.vida = random.uniform(0.2, 0.45)
            self.particulas.append(p)

    def explodir(self, x, y, cor, n=10):
        for _ in range(n):
            self.particulas.append(Particula(x, y, cor))

    # ------------------------------------------------------------- desenho
    def desenhar(self):
        tela = self.tela
        cam = self.camera_x
        if self.tremor > 0:
            cam += random.uniform(-6, 6) * self.tremor

        if not self.cenario.desenhar(tela, cam):
            self.mundo.desenhar_fundo(tela, cam)    # sem arte: fundo de formas
        self.cenario.desenhar_tunel(tela, cam, frente=False)
        self.mundo.desenhar(tela, cam, self.cenario.paleta_em)

        if self.poder == poderes.DRAGAO:
            self.desenhar_asas(tela, cam)
        for z in sorted(self.zumbis, key=lambda z: (-(z.indice % cfg.LARG_FORMACAO), -z.indice)):
            z.desenhar(tela, cam, self.poder)
        for p in self.particulas:
            p.desenhar(tela, cam)
        # a rocha do tunel passa por cima da horda: e ela que esconde a
        # emenda entre o cenario que ficou pra tras e o que vem
        self.cenario.desenhar_tunel(tela, cam, frente=True)

        self.desenhar_hud()
        if self.estado == MENU:
            self.painel("ZUMBI TSUNAMI", "ESPACO ou clique para comecar",
                        "Pegue as caixas: gigante, dragao, balao e ima")
        elif self.estado == FIM:
            self.painel("FIM DE JOGO",
                        f"{self.metros} m  -  {self.moedas} moedas  -  {self.pontuacao()} pts",
                        "R ou ESPACO para jogar de novo")
        pygame.display.flip()

    def desenhar_asas(self, tela, camera_x):
        """Um par de asas atras da horda inteira.

        Uma asa por zumbi viraria uma mancha roxa: com 80 deles o espaco
        entre um e outro e menor que a propria asa.
        """
        asas = recursos.asas(self.tempo * cfg.DRAGAO_FPS_ASAS)
        if asas is None or not self.zumbis:
            return
        esquerda = min(z.x for z in self.zumbis)
        direita = max(z.x for z in self.zumbis)
        topo = min(z.y - z.altura for z in self.zumbis)
        larg = int(direita - esquerda) + cfg.DRAGAO_ASAS_FOLGA
        alt = max(1, round(asas.get_height() * larg / asas.get_width()))
        asas = pygame.transform.smoothscale(asas, (larg, alt))
        tela.blit(asas, asas.get_rect(center=(
            int((esquerda + direita) / 2 - camera_x), int(topo + cfg.ZUMBI_A * 0.55))))

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
        self.desenhar_poder()
        if self.aviso > 0 and self.poder:
            self.desenhar_aviso()

    def desenhar_poder(self):
        """Icone do poder ativo mais a barra do tempo que falta."""
        if not self.poder:
            return
        cor = poderes.cor(self.poder)
        total = poderes.duracao(self.poder)
        fracao = max(0.0, min(1.0, self.poder_tempo / total))
        larg, alt = 150, 12
        x = cfg.LARGURA - 16 - larg
        y = 78                      # abaixo do recorde, pra nao encavalar

        icone = recursos.icone(self.poder)
        if icone is not None:
            self.tela.blit(icone, icone.get_rect(midright=(x - 8, y + alt // 2)))
        self.texto(poderes.nome(self.poder), self.fonte_p, x, y - 22, cor)
        pygame.draw.rect(self.tela, (16, 12, 22), (x - 2, y - 2, larg + 4, alt + 4),
                         border_radius=4)
        # a barra pisca no fim, pra avisar que o poder esta acabando
        if fracao < 0.25 and int(self.tempo * 8) % 2:
            cor = cfg.COR_BARRA_PODER
        pygame.draw.rect(self.tela, cor, (x, y, int(larg * fracao), alt),
                         border_radius=3)

    def desenhar_aviso(self):
        """Faixa que anuncia o poder recem-pego e explica o que ele faz."""
        cor = poderes.cor(self.poder)
        subida = min(1.0, (2.4 - self.aviso) * 6)
        y = int(96 + (1 - subida) * 30)
        cx = cfg.LARGURA // 2
        faixa = pygame.Surface((520, 62), pygame.SRCALPHA)
        faixa.fill((10, 8, 18, 160))
        self.tela.blit(faixa, faixa.get_rect(center=(cx, y + 10)))
        icone = recursos.icone(self.poder)
        if icone is not None:
            self.tela.blit(icone, icone.get_rect(center=(cx - 200, y + 10)))
        self.texto(poderes.nome(self.poder), self.fonte, cx + 26, y - 4, cor, True)
        self.texto(poderes.dica(self.poder), self.fonte_p, cx + 26, y + 24, centro=True)

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
