"""Loop principal, estados e regras da horda."""

import math
import random

import pygame

from jogo import config as cfg
from jogo import loja
from jogo import poderes
from jogo import progresso
from jogo import recursos
from jogo import sons
from jogo.cenario import Cenario
from jogo.entidades import Zumbi
from jogo.mundo import Mundo

MENU, LOJA, JOGANDO, FIM = "menu", "loja", "jogando", "fim"

TECLAS_PULO = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
# botoes da tela inicial, na ordem em que aparecem
BOTAO_JOGAR, BOTAO_LOJA, BOTAO_SOM, BOTAO_SAIR = "jogar", "loja", "som", "sair"
BOTOES = (BOTAO_JOGAR, BOTAO_LOJA, BOTAO_SOM, BOTAO_SAIR)
BOTAO_L, BOTAO_A, BOTAO_PASSO = 380, 50, 62
COR_BOTAO = (34, 28, 52)
COR_BOTAO_BORDA = (86, 76, 116)


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
        sons.preparar()
        pygame.init()
        self.tela = pygame.display.set_mode((cfg.LARGURA, cfg.ALTURA))
        pygame.display.set_caption(cfg.TITULO)
        recursos.carregar()     # sprites prontos antes do primeiro quadro
        sons.carregar()
        progresso.carregar()
        sons.ligado = progresso.dados["som"]
        self.relogio = pygame.time.Clock()
        self.fonte = pygame.font.SysFont("arialbold,arial", 24, bold=True)
        self.fonte_g = pygame.font.SysFont("arialbold,arial", 56, bold=True)
        self.fonte_p = pygame.font.SysFont("arialbold,arial", 18)
        self.recorde = progresso.dados["recorde"]
        self.loja = loja.Loja(self)
        self.cenario = Cenario()
        self.estado = MENU
        self.botao = 0              # botao escolhido na tela inicial
        self.ultima = None          # placar da ultima partida, pro menu
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
        self.poder_total = 1.0      # duracao cheia do poder ativo (pra barra)
        self.chance_usada = False   # a segunda chance vale uma vez por partida
        self.guardada = False       # as moedas desta partida ja foram pro cofre
        self.fim_tempo = 0.0        # ha quanto tempo o placar final esta na tela
        self.dragao_rect = None     # onde o dragao foi desenhado (pro fogo)
        self.zumbis = [Zumbi(cfg.X_LIDER, cfg.CHAO_Y, 0, tipo=recursos.tipo_inicial())]
        # item da loja: a horda ja comeca maior
        for i in range(progresso.nivel(loja.HORDA)):
            self.zumbis.append(Zumbi(cfg.X_LIDER, cfg.CHAO_Y, i + 1))

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
            if self.estado == MENU:
                if not self.evento_do_menu(ev):
                    return False
                continue
            if self.estado == LOJA:
                if not self.loja.evento(ev):
                    self.estado = MENU
                continue
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    self.voltar_ao_menu()
                if ev.key == pygame.K_m:
                    self.alternar_som()
                if ev.key in TECLAS_PULO:
                    self.segurando = True
                    self.acionar()
            if ev.type == pygame.KEYUP:
                if ev.key in TECLAS_PULO:
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
        if self.estado == FIM:
            # qualquer tecla pula o placar final (menos no comecinho, pra um
            # pulo apertado tarde demais nao fechar o placar sem querer)
            if self.fim_tempo >= cfg.FIM_TRAVA:
                self.voltar_ao_menu()
        else:
            self.buffer_pulo = 0.12

    def comecar(self):
        self.reiniciar()
        self.estado = JOGANDO

    def alternar_som(self):
        progresso.dados["som"] = sons.alternar()
        progresso.salvar()

    def guardar_partida(self):
        """Manda as moedas da partida pro cofre da loja e grava o recorde."""
        if self.guardada:
            return
        self.guardada = True
        self.recorde = max(self.recorde, self.pontuacao())
        progresso.dados["recorde"] = self.recorde
        progresso.dados["moedas"] += self.moedas
        progresso.salvar()

    def voltar_ao_menu(self):
        if self.estado == JOGANDO:
            self.guardar_partida()      # saiu no meio: as moedas nao se perdem
        if self.estado in (JOGANDO, FIM):
            self.ultima = (self.metros, self.moedas, self.pontuacao())
        self.reiniciar()
        self.estado = MENU
        self.botao = 0

    # ---------------------------------------------------------- tela inicial
    def rect_do_botao(self, i):
        r = pygame.Rect(0, 0, BOTAO_L, BOTAO_A)
        r.center = (cfg.LARGURA // 2, cfg.ALTURA // 2 - 40 + i * BOTAO_PASSO)
        return r

    def botao_em(self, pos):
        for i in range(len(BOTOES)):
            if self.rect_do_botao(i).collidepoint(pos):
                return i
        return None

    def evento_do_menu(self, ev):
        """Trata um evento na tela inicial. Devolve False pra fechar o jogo."""
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                return False
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.botao = (self.botao - 1) % len(BOTOES)
                sons.tocar("clique")
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.botao = (self.botao + 1) % len(BOTOES)
                sons.tocar("clique")
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.apertar_botao(self.botao)
            elif ev.key == pygame.K_m:
                self.apertar_botao(BOTOES.index(BOTAO_SOM))
        elif ev.type == pygame.MOUSEMOTION:
            i = self.botao_em(ev.pos)
            if i is not None:
                self.botao = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            i = self.botao_em(ev.pos)
            if i is not None:
                self.botao = i
                return self.apertar_botao(i)
        return True

    def apertar_botao(self, i):
        nome = BOTOES[i]
        if nome == BOTAO_SAIR:
            return False
        if nome == BOTAO_SOM:
            self.alternar_som()
            sons.tocar("clique")        # so se ouve quando acabou de ligar
        elif nome == BOTAO_LOJA:
            sons.tocar("clique")
            self.loja = loja.Loja(self)
            self.estado = LOJA
        else:
            sons.tocar("clique")
            self.comecar()
        return True

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
            self.loja.atualizar(dt)
            if self.estado == FIM:
                # o placar final fica uns segundos e o jogo volta sozinho
                self.fim_tempo += dt
                if self.fim_tempo >= cfg.FIM_ESPERA:
                    self.voltar_ao_menu()
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
                sons.tocar("pulo")

        alvo_lider = self.camera_x + cfg.X_LIDER
        total = len(self.zumbis)
        subindo = self.segurando and self.poder_tempo > 0
        for z in self.zumbis:
            z.atualizar(dt, self.mundo, alvo_lider, total, self.poder, subindo)
            if z.bateu:
                # deu de cara na parede do buraco: poeira e baque
                z.bateu = False
                self.explodir(z.x + z.largura / 2, z.y - z.altura / 2,
                              self.cenario.paleta_em(z.x + z.largura)["topo"], 5)
                self.tremor = min(1.0, self.tremor + 0.12)
                sons.tocar("parede")
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

        if not self.zumbis and not self.segunda_chance():
            self.guardar_partida()
            self.estado = FIM
            sons.tocar("fim")

    def segunda_chance(self):
        """Item da loja: a horda zerou, mas volta voando com alguns zumbis.

        Volta com o poder do dragao por uns segundos porque a camera pode
        estar bem em cima de um buraco - e o voo nunca acaba sobre um.
        """
        if self.chance_usada or not progresso.nivel(loja.CHANCE):
            return False
        self.chance_usada = True
        progresso.definir_nivel(loja.CHANCE, progresso.nivel(loja.CHANCE) - 1)
        progresso.salvar()
        x = self.camera_x + cfg.X_LIDER
        y = max(cfg.DRAGAO_TETO + cfg.ZUMBI_A + 60,
                self.mundo.teto_em(x) + cfg.ZUMBI_A + 20)
        self.zumbis = [Zumbi(x, y, i, tipo=recursos.tipo_inicial() if i == 0 else None)
                       for i in range(cfg.CHANCE_ZUMBIS)]
        self.ativar_poder(poderes.DRAGAO)
        self.poder_tempo = self.poder_total = cfg.CHANCE_VOO
        return True

    # --------------------------------------------------------------- poderes
    def ativar_poder(self, nome):
        """Pegar uma caixa troca o poder na hora, mesmo com outro rodando."""
        self.poder = nome
        self.dragao_rect = None
        # item da loja: cada nivel estica a duracao de todos os poderes
        bonus = 1.0 + loja.BONUS_TEMPO * progresso.nivel(loja.TEMPO)
        self.poder_tempo = self.poder_total = poderes.duracao(nome) * bonus
        self.aviso = 2.4
        self.tremor = min(1.0, self.tremor + 0.3)
        sons.tocar("poder")
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
        self.dragao_rect = None

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
                if random.random() < 0.25:      # rastro de brilho da moeda puxada
                    p = Particula(m.x, m.y, (255, 244, 190))
                    p.vx, p.vy = random.uniform(-30, 30), random.uniform(-30, 30)
                    p.vida = random.uniform(0.15, 0.3)
                    self.particulas.append(p)

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
                        sons.tocar("explosao")
                    else:
                        o.atingir()
                        z.vivo = False
                        self.explodir(o.x, o.y - o.altura / 2, cfg.COR_OBSTACULO)
                        sons.tocar("batida")
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
                    sons.tocar("moeda")

    def converter(self, humano):
        if len(self.zumbis) >= cfg.MAX_ZUMBIS:
            return
        indice = max((z.indice for z in self.zumbis), default=-1) + 1
        # o mordido vira a versao zumbi dele mesmo - ou, as vezes, um dos
        # monstros comprados na loja
        tipo = recursos.tipo_do_humano(humano.tipo)
        monstros = loja.monstros_comprados()
        if monstros and random.random() < cfg.MONSTRO_CHANCE:
            tipo = random.choice(monstros)
        novo = Zumbi(humano.x, humano.y, indice, tipo=tipo)
        novo.vy = humano.vy
        novo.no_chao = humano.no_chao
        self.zumbis.append(novo)
        self.explodir(humano.x, humano.y - cfg.HUMANO_A / 2, cfg.COR_ZUMBI, 6)
        sons.tocar("mordida")

    def rastro_de_fogo(self):
        """Faiscas saindo do rabo do dragao enquanto a horda voa."""
        ultimo = min(self.zumbis, key=lambda z: z.x)
        x, y = ultimo.x - 6, ultimo.y - cfg.ZUMBI_A * 0.5
        if self.dragao_rect is not None:
            x = self.dragao_rect.left + self.camera_x + 14
            y = self.dragao_rect.top + self.dragao_rect.height * 0.42
        for _ in range(2):
            cor = random.choice((cfg.COR_FOGO, (250, 226, 120), (236, 110, 60)))
            p = Particula(x, y + random.uniform(-8, 8), cor)
            p.vx = random.uniform(-220, -60)
            p.vy = random.uniform(-40, 40)
            p.vida = random.uniform(0.25, 0.55)
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

        self.desenhar_horda(tela, cam)
        for p in self.particulas:
            p.desenhar(tela, cam)
        # a rocha do tunel passa por cima da horda: e ela que esconde a
        # emenda entre o cenario que ficou pra tras e o que vem
        self.cenario.desenhar_tunel(tela, cam, frente=True)

        if self.estado == MENU:
            self.desenhar_menu()
        elif self.estado == LOJA:
            self.loja.desenhar(tela)
        else:
            self.desenhar_hud()
        if self.estado == FIM:
            self.painel("FIM DE JOGO",
                        f"{self.metros} m  -  {self.moedas} moedas  -  {self.pontuacao()} pts",
                        "voltando ao menu...  (ESPACO pula a espera)")
        pygame.display.flip()

    def veu(self):
        veu = pygame.Surface((cfg.LARGURA, cfg.ALTURA), pygame.SRCALPHA)
        veu.fill((10, 8, 18, 170))
        self.tela.blit(veu, (0, 0))

    def rotulo_do_botao(self, nome):
        if nome == BOTAO_JOGAR:
            return "JOGAR"
        if nome == BOTAO_LOJA:
            return "LOJA"
        if nome == BOTAO_SAIR:
            return "SAIR"
        if not sons.disponivel():
            return "EFEITOS SONOROS: SEM AUDIO"
        return "EFEITOS SONOROS: " + ("LIGADOS" if sons.ligado else "DESLIGADOS")

    def desenhar_menu(self):
        """Tela inicial: titulo, jogar, liga/desliga dos efeitos e sair."""
        self.veu()
        cx = cfg.LARGURA // 2
        self.texto("ZUMBI TSUNAMI", self.fonte_g, cx, 104, cfg.COR_ZUMBI, True)
        self.texto("Pegue as caixas: gigante, dragao, balao e ima",
                   self.fonte_p, cx, 156, centro=True)
        for i, nome in enumerate(BOTOES):
            r = self.rect_do_botao(i)
            escolhido = i == self.botao
            cor_texto = cfg.COR_TEXTO
            if nome == BOTAO_SOM and not (sons.ligado and sons.disponivel()):
                cor_texto = (150, 144, 164)
            if escolhido:
                pygame.draw.rect(self.tela, cfg.COR_ZUMBI_ESCURO, r.inflate(8, 8),
                                 border_radius=14)
            pygame.draw.rect(self.tela, COR_BOTAO, r, border_radius=10)
            pygame.draw.rect(self.tela, cfg.COR_ZUMBI if escolhido else COR_BOTAO_BORDA,
                             r, 2, border_radius=10)
            self.texto(self.rotulo_do_botao(nome), self.fonte, r.centerx, r.centery,
                       cfg.COR_ZUMBI if escolhido and nome == BOTAO_JOGAR else cor_texto,
                       True)
        if self.ultima:
            metros, moedas, pontos = self.ultima
            self.texto(f"Ultima partida: {metros} m  -  {moedas} moedas  -  {pontos} pts",
                       self.fonte_p, cx, 182, centro=True)
        rodape = f"Moedas: {progresso.dados['moedas']}"
        if self.recorde:
            rodape += f"   -   Recorde: {self.recorde}"
        self.texto(rodape, self.fonte_p, cx,
                   self.rect_do_botao(len(BOTOES) - 1).bottom + 26, cfg.COR_MOEDA, True)
        self.texto("Setas escolhem  -  ENTER confirma  -  no jogo: ESPACO pula, M liga/desliga o som",
                   self.fonte_p, cx, cfg.ALTURA - 26, centro=True)

    def desenhar_horda(self, tela, cam):
        """A horda, do jeito que o poder ativo manda.

        Gigante e dragao trocam a horda inteira por um bicho so; balao e ima
        desenham os zumbis normais com o enfeite do poder por cima.
        """
        if not self.zumbis:
            return
        if self.poder == poderes.DRAGAO and self.desenhar_dragao(tela, cam):
            return
        if self.poder == poderes.GIGANTE and self.desenhar_gigantao(tela, cam):
            return
        total = len(self.zumbis)
        for z in sorted(self.zumbis, key=lambda z: (-(z.indice % cfg.LARG_FORMACAO), -z.indice)):
            z.desenhar(tela, cam, self.poder, total)
        if self.poder == poderes.IMA:
            self.desenhar_ima(tela, cam)

    def tamanho_do_bicho(self, faixa):
        """Altura do gigante/dragao: cresce com a horda, ate ela encher."""
        menor, maior = faixa
        return menor + (maior - menor) * min(1.0, len(self.zumbis) / 40)

    def desenhar_gigantao(self, tela, cam):
        """Poder gigante: a horda vira um zumbi so, enorme.

        Escalar cada zumbi dava um bolo de corpos encavalados; um gigante
        unico le melhor e ainda mostra o tamanho da horda pela altura.
        """
        lider = max(self.zumbis, key=lambda z: z.x)
        altura = self.tamanho_do_bicho(cfg.GIGANTAO_ALTURA)
        sprite = recursos.gigantao(lider.tipo, lider.quadro(), altura)
        if sprite is None:
            return False
        tras = min(z.x for z in self.zumbis)
        r = sprite.get_rect()
        # o pe da frente fica onde esta o lider: e ali que as coisas batem
        r.midbottom = (int((lider.x * 2 + tras) / 3 - cam), int(lider.y) + 2)
        # sombra no chao, pra ele pesar
        if lider.no_chao:
            sombra = pygame.Surface((r.width, 14), pygame.SRCALPHA)
            pygame.draw.ellipse(sombra, (0, 0, 0, 70), sombra.get_rect())
            tela.blit(sombra, (r.x, r.bottom - 8))
        tela.blit(sprite, r)
        return True

    def desenhar_dragao(self, tela, cam):
        """Poder dragao: a horda vira um dragao que bate as asas."""
        altura = self.tamanho_do_bicho(cfg.DRAGAO_ALTURA)
        sprite = recursos.dragao(self.tempo * cfg.DRAGAO_FPS_ASAS, altura)
        if sprite is None:
            return False
        lider = max(self.zumbis, key=lambda z: z.x)
        tras = min(z.x for z in self.zumbis)
        r = sprite.get_rect()
        # a barriga fica na altura dos pes da horda; perto do teto o dragao
        # desce um pouco pra nao sair da tela
        r.midbottom = (int((lider.x + tras) / 2 - cam) + 12,
                       int(lider.y) + round(altura * 0.08))
        # ... e na boca do tunel acompanha o teto, pra cabeca nao entrar na rocha
        teto = self.mundo.teto_em(lider.x)
        folga = (teto - cfg.TETO) / max(1, cfg.TUNEL_TETO - cfg.TETO)
        r.top = max(r.top, round(4 + folga * cfg.TUNEL_TETO))
        tela.blit(sprite, r)
        self.dragao_rect = r
        return True

    def desenhar_ima(self, tela, cam):
        """Poder ima: um ima flutua sobre o lider soltando aneis de atracao."""
        lider = max(self.zumbis, key=lambda z: z.x)
        cx = int(lider.x - cam) + 6
        cy = int(lider.y) - cfg.ZUMBI_A - 46 + round(math.sin(self.tempo * 4) * 4)
        cor = poderes.cor(poderes.IMA)
        raio_max = 90
        camada = pygame.Surface((raio_max * 2 + 8, raio_max * 2 + 8), pygame.SRCALPHA)
        meio = camada.get_rect().center
        for i in range(cfg.IMA_ONDAS):
            # cada anel nasce grande e fecha em direcao ao ima: e pra dentro
            # que as moedas vao
            t = (self.tempo * 0.9 + i / cfg.IMA_ONDAS) % 1.0
            raio = int(raio_max * (1 - t)) + 14
            pygame.draw.circle(camada, (*cor, int(150 * t)), meio, raio, 3)
        tela.blit(camada, camada.get_rect(center=(cx, cy)))
        sprite = recursos.ima()
        if sprite is None:
            pygame.draw.circle(tela, cor, (cx, cy), 12)
            return
        # o ima aponta pra frente (as pontas viram pra onde vem as moedas)
        sprite = pygame.transform.rotate(sprite, 90 + math.sin(self.tempo * 3) * 10)
        tela.blit(sprite, sprite.get_rect(center=(cx, cy)))

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
        fracao = max(0.0, min(1.0, self.poder_tempo / self.poder_total))
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
        self.veu()
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
