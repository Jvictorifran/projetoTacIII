"""Loop principal, estados e regras da horda."""

import math
import random

import pygame

from jogo import config as cfg
from jogo import fase as fases
from jogo import loja
from jogo import poderes
from jogo import progresso
from jogo import recursos
from jogo import sons
from jogo import telas
from jogo.cenario import Cenario
from jogo.editor import Editor
from jogo.entidades import Zumbi
from jogo.mundo import Mundo

MENU, LOJA, JOGANDO, FIM = "menu", "loja", "jogando", "fim"
PAUSA, CONFIG, FASES, EDITOR = "pausa", "config", "fases", "editor"
MULTI, SALA = "multi", "sala"

TECLAS_PULO = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
BONUS_POR_ZUMBI = 10        # cruzar a chegada de uma fase vale isso por zumbi vivo
PROGRESSO_A_CADA = 1.0      # segundos entre dois avisos de pontos pro placar da LAN


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
    # os estados tambem ficam na classe, pras telas nao importarem este modulo
    MENU, LOJA, JOGANDO, FIM = MENU, LOJA, JOGANDO, FIM
    PAUSA, CONFIG, FASES, EDITOR, MULTI, SALA = PAUSA, CONFIG, FASES, EDITOR, MULTI, SALA

    def __init__(self):
        sons.preparar()
        pygame.init()
        progresso.carregar()
        bandeiras = pygame.SCALED | (pygame.FULLSCREEN if progresso.dados["tela_cheia"] else 0)
        try:
            self.tela = pygame.display.set_mode((cfg.LARGURA, cfg.ALTURA), bandeiras)
        except pygame.error:
            self.tela = pygame.display.set_mode((cfg.LARGURA, cfg.ALTURA))
        pygame.display.set_caption(cfg.TITULO)
        recursos.carregar()     # sprites prontos antes do primeiro quadro
        sons.carregar()
        sons.ligado = progresso.dados["som"]
        sons.musica_ligada = progresso.dados["musica"]
        sons.definir_volume(progresso.dados["volume"] / 100)
        self.relogio = pygame.time.Clock()
        self.fonte = pygame.font.SysFont("arialbold,arial", 24, bold=True)
        self.fonte_g = pygame.font.SysFont("arialbold,arial", 56, bold=True)
        self.fonte_m = pygame.font.SysFont("arialbold,arial", 20, bold=True)
        self.fonte_p = pygame.font.SysFont("arialbold,arial", 18)
        self.recorde = progresso.dados["recorde"]
        self.loja = loja.Loja(self)
        self.cenario = Cenario()
        self.estado = MENU
        self.tela_atual = telas.MenuPrincipal(self)
        self.editor = None
        self.sair = False
        self.ultima = None          # placar da ultima partida, pro menu
        # como a partida foi aberta: fase do editor ou None (infinito), semente
        # do mapa e de onde veio (menu, fases, editor ou sala)
        self.fase = None
        self.seed = None
        self.origem = "menu"
        self.pedido = (None, None, "menu")
        self.cliente = None         # placar da LAN (rede/cliente.py)
        self.servidor = None        # so quando esta maquina hospeda a sala
        self.reiniciar()
        sons.tocar_musica()

    # ------------------------------------------------------------- partida
    def reiniciar(self):
        gerador = fases.GeradorDeFase(self.fase) if self.fase else None
        self.mundo = Mundo(gerador, seed=self.seed)
        self.camera_x = 0.0
        self.velocidade = self.fase.velocidade if self.fase else cfg.VEL_INICIAL
        self.tempo = 0.0
        self.moedas = 0
        self.bonus = 0              # zumbis que cruzaram a chegada da fase
        self.concluiu = False
        self.buffer_pulo = 0.0
        self.particulas = []
        self.tremor = 0.0
        self.poder = None           # poder ativo, vindo de uma caixa
        self.poder_tempo = 0.0      # quanto falta dele
        self.aviso = 0.0            # tempo do aviso na tela ao pegar a caixa
        self.segurando = False      # tecla de pulo presa (o dragao usa isso)
        self.poder_total = 1.0      # duracao cheia do poder ativo (pra barra)
        self.chance_usada = False   # a segunda chance vale uma vez por partida
        self.guardada = False       # a partida ja foi contabilizada
        self.fim_tempo = 0.0        # ha quanto tempo o placar final esta na tela
        self.dragao_rect = None     # onde o dragao foi desenhado (pro fogo)
        self.envio = 0.0            # contagem pro proximo aviso ao placar
        self.gemido = random.uniform(2.0, 5.0)  # proximo gemido da horda
        self.zumbis = [Zumbi(cfg.X_LIDER, cfg.CHAO_Y, 0, tipo=recursos.tipo_inicial())]
        # item da loja: a horda ja comeca maior
        for i in range(progresso.nivel(loja.HORDA)):
            self.zumbis.append(Zumbi(cfg.X_LIDER, cfg.CHAO_Y, i + 1))
        self.horda_max = len(self.zumbis)

    @property
    def metros(self):
        return int(self.camera_x / cfg.PX_POR_METRO)

    def pontuacao(self):
        return self.metros + self.moedas * 5 + self.bonus

    def na_sala(self):
        return self.origem == "sala" and self.cliente is not None

    # -------------------------------------------------------------- entrada
    def processar_eventos(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if self.estado == LOJA:
                if not self.loja.evento(ev):
                    self.ir(MENU)
                continue
            if self.estado == EDITOR:
                self.editor.evento(ev)
                continue
            if self.estado not in (JOGANDO, FIM):
                self.tela_atual.evento(ev)
                continue
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    if self.estado == JOGANDO:
                        self.ir(PAUSA, telas.Pausa(self))
                        continue
                    self.voltar_da_partida()
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
        return not self.sair

    def acionar(self):
        if self.estado == FIM:
            # qualquer tecla pula o placar final (menos no comecinho, pra um
            # pulo apertado tarde demais nao fechar o placar sem querer)
            if self.fim_tempo >= cfg.FIM_TRAVA:
                self.voltar_da_partida()
        else:
            self.buffer_pulo = 0.12

    # -------------------------------------------------------------- telas
    def ir(self, estado, tela=None):
        """Troca de tela. Cada estado de menu tem o seu objeto de tela."""
        if isinstance(self.tela_atual, telas.TelaMultiplayer) and estado != MULTI:
            self.tela_atual.fechar()
        self.estado = estado
        if tela is not None:
            self.tela_atual = tela
        elif estado == MENU:
            self.tela_atual = telas.MenuPrincipal(self)
        elif estado == SALA:
            self.tela_atual = telas.TelaSala(self)

    def abrir_loja(self):
        self.loja = loja.Loja(self)
        self.ir(LOJA)

    def abrir_editor(self, fase):
        self.editor = Editor(self, fase)
        self.ir(EDITOR)

    def comecar(self, fase=None, seed=None, origem="menu"):
        """Partida nova. Sem fase e o modo infinito; sem semente, mapa sorteado."""
        self.pedido = (fase, seed, origem)
        self.fase, self.origem = fase, origem
        self.seed = seed if seed is not None else random.randrange(1, 10 ** 6)
        self.cenario.comecar_em(fase.cenario if fase else None)
        self.reiniciar()
        self.ir(JOGANDO)
        if self.na_sala():
            self.cliente.comecei()

    def repetir_partida(self):
        self.comecar(*self.pedido)

    def alternar_som(self):
        progresso.dados["som"] = sons.alternar()
        progresso.salvar()

    def alternar_musica(self):
        progresso.dados["musica"] = sons.alternar_musica()
        progresso.salvar()

    def alternar_tela_cheia(self):
        progresso.dados["tela_cheia"] = not progresso.dados["tela_cheia"]
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error:
            pass
        progresso.salvar()

    def terminar_partida(self):
        """Contabiliza a partida uma vez so: cofre, recorde e placar da LAN.

        Moeda de fase nao vai pro cofre (senao bastava montar uma fase cheia
        de moedas), e o recorde e so do modo infinito.
        """
        if self.guardada:
            return
        self.guardada = True
        pontos = self.pontuacao()
        if self.fase is None:
            self.recorde = max(self.recorde, pontos)
            progresso.dados["recorde"] = self.recorde
            progresso.dados["moedas"] += self.moedas
            progresso.salvar()
        self.ultima = (self.metros, self.moedas, pontos)
        if self.na_sala():
            self.cliente.resultado(pontos, self.metros, self.moedas, self.horda_max,
                                   max(self.tempo, 0.01), self.seed,
                                   self.fase.nome if self.fase else None)

    def voltar_da_partida(self):
        """Depois da partida volta pra onde ela foi aberta."""
        self.terminar_partida()
        origem = self.origem
        if origem == "editor" and self.editor is not None:
            self.cenario.comecar_em(self.editor.fase.cenario)
            self.ir(EDITOR)
            return
        self.fundo_novo()
        if origem == "sala" and self.cliente is not None:
            self.ir(SALA)
        elif origem == "fases":
            self.ir(FASES, telas.TelaFases(self, editar=False))
        else:
            self.ir(MENU)

    def fundo_novo(self):
        """Mundo novo e parado atras dos menus (sem a partida que acabou)."""
        self.fase, self.seed, self.origem = None, None, "menu"
        self.cenario.comecar_em(None)
        self.reiniciar()

    # ---------------------------------------------------------- placar LAN
    def hospedar(self, modo, minutos=10, fase=None):
        """Abre o servidor do placar nesta maquina e entra na sala.

        Devolve uma mensagem de erro, ou None se deu certo.
        """
        from rede.protocolo import PORTA
        from rede.servidor import ServidorPlacar
        seed = random.randrange(1, 10 ** 6) if modo == "desafio" and fase is None else None
        sala = f"Sala de {progresso.dados['nome']}"
        servidor = ServidorPlacar(sala, modo, seed, minutos, fase.para_dict() if fase else None)
        try:
            servidor.iniciar()
        except OSError as e:
            return f"Nao deu pra abrir a porta {PORTA}: {e.strerror}"
        self.servidor = servidor
        self.entrar_na_sala("127.0.0.1")
        return None

    def entrar_na_sala(self, ip, porta=None):
        from rede.cliente import ClientePlacar
        from rede.protocolo import PORTA
        self.cliente = ClientePlacar(ip, progresso.dados["nome"], porta or PORTA)
        self.ir(SALA)

    def jogar_na_sala(self):
        c = self.cliente
        fase = None
        if c.fase:
            try:
                fase = fases.Fase.de_dict(c.fase)
            except (ValueError, KeyError, TypeError):
                self.tela_atual.avisar("A fase do desafio veio estragada")
                return
        seed = c.seed if c.modo == "desafio" else None
        self.comecar(fase, seed, "sala")

    def sair_da_sala(self):
        if self.cliente is not None:
            self.cliente.fechar()
            self.cliente = None
        if self.servidor is not None:
            self.servidor.encerrar()
            self.servidor = None
        self.ir(MULTI, telas.TelaMultiplayer(self))

    def cortar_pulo(self):
        """Solta a tecla cedo = pulo mais baixo."""
        if self.poder == poderes.DRAGAO:
            return          # voando a tecla so controla a altura, nao o pulo
        for z in self.zumbis:
            if z.vy < cfg.VEL_PULO * cfg.PULO_CURTO:
                z.vy = cfg.VEL_PULO * cfg.PULO_CURTO

    # ----------------------------------------------------------- atualizar
    def atualizar(self, dt):
        if self.cliente is not None:
            self.cliente.processar()
        if self.estado == EDITOR:
            sons.passos(0.0)
            self.editor.atualizar(dt)
            return
        if self.estado != JOGANDO:
            sons.passos(0.0)
            self.loja.atualizar(dt)
            if self.estado not in (LOJA, FIM):
                self.tela_atual.atualizar(dt)
            if self.estado == FIM:
                # o placar final fica uns segundos e o jogo volta sozinho
                self.fim_tempo += dt
                if self.fim_tempo >= cfg.FIM_ESPERA:
                    self.voltar_da_partida()
            if self.estado != PAUSA:
                for p in self.particulas:
                    p.atualizar(dt)
                self.particulas = [p for p in self.particulas if p.vida > 0]
            return

        self.tempo += dt
        if self.fase is None:
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

        self.sons_da_partida(dt)
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

        self.horda_max = max(self.horda_max, len(self.zumbis))
        if self.na_sala():
            self.envio -= dt
            if self.envio <= 0:
                self.envio = PROGRESSO_A_CADA
                self.cliente.progresso(self.pontuacao(), self.metros)

        if self.fase is not None and self.zumbis and \
                max(z.x for z in self.zumbis) >= self.fase.chegada:
            # cruzou a chegada: cada zumbi que chegou vale bonus
            self.concluiu = True
            self.bonus = BONUS_POR_ZUMBI * len(self.zumbis)
            self.terminar_partida()
            self.estado = FIM
            sons.tocar("poder")
        elif not self.zumbis and not self.segunda_chance():
            self.terminar_partida()
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

    def sons_da_partida(self, dt):
        """Gritos de quem ve a horda, passos da horda e um gemido de vez em quando."""
        for h in self.mundo.humanos:
            if h.panico and not h.gritou:
                h.gritou = True
                if self.camera_x < h.x < self.camera_x + cfg.LARGURA:
                    sons.tocar("grito")
        no_chao = sum(1 for z in self.zumbis if z.no_chao)
        if self.poder == poderes.DRAGAO or not self.zumbis:
            intensidade = 0.0
        else:
            intensidade = min(1.0, 0.35 + len(self.zumbis) / 40) * no_chao / len(self.zumbis)
        sons.passos(intensidade)
        self.gemido -= dt
        if self.gemido <= 0:
            self.gemido = random.uniform(3.0, 7.0) / (1 + len(self.zumbis) / 20)
            sons.tocar("zumbi")

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
                        sons.tocar("quebra")
                    else:
                        o.atingir()
                        z.vivo = False
                        self.explodir(o.x, o.y - o.altura / 2, cfg.COR_OBSTACULO)
                        sons.tocar("batida")
                        if not o.vivo:
                            sons.tocar("quebra")        # o carro nao aguentou
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
        sons.tocar("zumbi")         # o mordido levanta ja gemendo

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
        if self.estado == EDITOR:
            self.editor.desenhar(tela)
            pygame.display.flip()
            return
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

        if self.estado == LOJA:
            self.loja.desenhar(tela)
        elif self.estado in (JOGANDO, FIM, PAUSA):
            self.desenhar_hud()
        if self.estado == FIM:
            self.desenhar_fim()
        elif self.estado not in (JOGANDO, LOJA):
            self.tela_atual.desenhar(tela)
        pygame.display.flip()

    def veu(self):
        veu = pygame.Surface((cfg.LARGURA, cfg.ALTURA), pygame.SRCALPHA)
        veu.fill((10, 8, 18, 170))
        self.tela.blit(veu, (0, 0))

    def desenhar_fim(self):
        titulo = "FASE CONCLUIDA!" if self.concluiu else "FIM DE JOGO"
        linha = f"{self.metros} m  -  {self.moedas} moedas  -  {self.pontuacao()} pts"
        if self.concluiu:
            linha += f"  (bonus {self.bonus})"
        destino = {"editor": "voltando ao editor", "sala": "voltando a sala",
                   "fases": "voltando as fases"}.get(self.origem, "voltando ao menu")
        rodape = f"{destino}...  (ESPACO pula a espera)"
        if self.na_sala():
            aviso = self.cliente.aviso
            rodape = aviso[0] if aviso else "mandando o resultado pro placar da sala..."
        self.painel(titulo, linha, rodape)

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
        cx = cfg.LARGURA // 2
        if self.fase is not None:
            fracao = max(0.0, min(1.0, self.camera_x / self.fase.chegada))
            larg = 260
            pygame.draw.rect(self.tela, (16, 12, 22), (cx - larg // 2 - 2, 14, larg + 4, 12),
                             border_radius=4)
            pygame.draw.rect(self.tela, cfg.COR_MOEDA, (cx - larg // 2, 16, int(larg * fracao), 8),
                             border_radius=3)
            self.texto(self.fase.nome, self.fonte_p, cx, 40, centro=True)
        if self.na_sala():
            lugar, total, alvo = self.cliente.posicao(self.pontuacao())
            linha = f"{lugar}o de {total} na sala"
            if alvo:
                linha += f"  -  faltam {alvo[1]} pts pra passar {alvo[0]}"
            elif total > 1:
                linha += "  -  liderando!"
            if not self.cliente.conectado:
                linha += "  (sem conexao)"
            self.texto(linha, self.fonte_p, cx, 64 if self.fase else 22, cfg.COR_ZUMBI, True)
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
        if isinstance(self.tela_atual, telas.TelaMultiplayer):
            self.tela_atual.fechar()
        if self.cliente is not None:
            self.cliente.fechar()
        if self.servidor is not None:
            self.servidor.encerrar()
        pygame.quit()
