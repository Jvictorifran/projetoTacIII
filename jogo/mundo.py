"""Geracao procedural do cenario: plataformas, buracos, obstaculos e itens."""

import random

import pygame

from jogo import config as cfg
from jogo.entidades import Box, Humano, Moeda, Obstaculo

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
        self.caixas = []
        self.predios = []
        base = Segmento(-400, 1600, cfg.CHAO_Y, 0)
        self.segmentos.append(base)
        self._gerar_predios(-400, 2000)
        # a primeira caixa vem antes de qualquer obstaculo: o jogador aprende
        # o que ela faz sem o risco de perder zumbi no meio
        self.caixas.append(Box(cfg.CAIXA_PRIMEIRA_X, cfg.CHAO_Y - 8))
        # dai em diante as caixas seguem uma grade fixa de distancia
        self.proxima_caixa = cfg.CAIXA_PRIMEIRA_X + cfg.CAIXA_DISTANCIA
        # centro do proximo tunel: um a cada troca de cenario
        self.proximo_tunel = cfg.TRECHO_CENARIO

    # ------------------------------------------------------------------ chao
    def chao_em(self, x):
        """Altura do topo do chao na posicao x, ou None se for buraco."""
        for seg in self.segmentos:
            if seg.contem(x):
                return seg.topo
        return None

    def parede_em(self, x, y):
        """Parede que barra quem esta com o pe em y e a frente em x.

        Devolve o x da face esquerda da plataforma, ou None se o caminho
        esta livre. So e parede pra quem ja esta abaixo da beirada: quem
        chega quase na altura dela ainda sobe (mesma folga do pouso).
        """
        for seg in self.segmentos:
            if seg.contem(x):
                return seg.x if y > seg.topo + cfg.FOLGA_BEIRADA else None
        return None

    def teto_em(self, x):
        """Ate onde a horda pode subir no ponto x.

        Dentro do tunel o limite e o teto do vao. Chegando perto ele desce
        em rampa, pra quem vem voando mergulhar na boca do tunel em vez de
        atravessar a rocha.
        """
        k = round(x / cfg.TRECHO_CENARIO)
        if k < 1:
            return cfg.TETO
        fora = abs(x - k * cfg.TRECHO_CENARIO) - cfg.TUNEL_LARGURA / 2
        if fora <= 0:
            return cfg.TUNEL_TETO
        if fora >= cfg.TUNEL_RAMPA:
            return cfg.TETO
        return cfg.TUNEL_TETO + (cfg.TETO - cfg.TUNEL_TETO) * fora / cfg.TUNEL_RAMPA

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
        for c in self.caixas:
            c.atualizar(dt)
        self.humanos = [h for h in self.humanos if h.vivo]
        self.caixas = [c for c in self.caixas if c.vivo]

    def _limpar(self, minimo):
        self.segmentos = [s for s in self.segmentos if s.fim > minimo]
        self.obstaculos = [o for o in self.obstaculos if o.vivo and o.x > minimo]
        self.humanos = [h for h in self.humanos if h.x > minimo - 200]
        self.moedas = [m for m in self.moedas if m.vivo and m.x > minimo]
        self.caixas = [c for c in self.caixas if c.vivo and c.x > minimo]
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
        # chegando no tunel: tenta a menor plataforma possivel e, se nem ela
        # couber, emenda direto no chao reto que atravessa o tunel
        entrada = self.proximo_tunel - cfg.TUNEL_LARGURA / 2 - cfg.TUNEL_MARGEM
        if anterior.fim + buraco + largura > entrada:
            largura = 1.6 * alcance
            if anterior.fim + buraco + largura > entrada:
                self._gerar_chao_do_tunel(anterior, alcance, entrada)
                return
        topo = cfg.CHAO_Y - nivel * cfg.ALTURA_NIVEL
        seg = Segmento(anterior.fim + buraco, largura, topo, nivel)
        self.segmentos.append(seg)

        if buraco > 40 and random.random() < 0.6:
            self._arco_de_moedas(anterior.fim, seg.x, min(anterior.topo, topo))
        self._povoar(seg, alcance)

    def _gerar_chao_do_tunel(self, anterior, alcance, entrada):
        """Plataforma unica, no nivel base e sem carro, que atravessa o tunel."""
        buraco = random.uniform(0.25, 0.45) * alcance if anterior.nivel else 0.0
        x = min(anterior.fim + buraco, entrada)
        fim = self.proximo_tunel + cfg.TUNEL_LARGURA / 2 + cfg.TUNEL_MARGEM
        seg = Segmento(x, fim - x, cfg.CHAO_Y, 0)
        self.segmentos.append(seg)
        for _ in range(random.randint(1, 3)):
            self.humanos.append(Humano(random.uniform(seg.x + 60, seg.fim - 40), seg.topo))
        # fileira de moedas guiando a horda por dentro do tunel
        for i in range(-5, 6):
            self.moedas.append(Moeda(self.proximo_tunel + i * 44, seg.topo - 60))
        self._caixas_do_trecho(seg)
        self.proximo_tunel += cfg.TRECHO_CENARIO

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
        self._caixas_do_trecho(seg)
        # moedas sobre a plataforma
        if random.random() < 0.5:
            x = random.uniform(seg.x + 80, max(seg.x + 90, seg.fim - 160))
            for i in range(random.randint(3, 6)):
                self.moedas.append(Moeda(x + i * 34, seg.topo - 60))

    def _caixas_do_trecho(self, seg):
        """Caixas numa grade fixa: uma a cada `CAIXA_DISTANCIA` px de corrida.

        Se o ponto da grade cai num buraco ou na borda, a caixa vai pro
        comeco desta plataforma; se cai em cima de um carro, anda pra frente
        ate ter folga. A grade em si nao se move: o desvio de uma caixa nao
        empurra as seguintes.
        """
        ini, fim = seg.x + cfg.CAIXA_MARGEM, seg.fim - cfg.CAIXA_MARGEM
        while self.proxima_caixa <= fim:
            x = self._vaga_livre(max(self.proxima_caixa, ini), fim)
            if x is None:
                return              # plataforma lotada: a caixa fica pra proxima
            self.caixas.append(Box(x, seg.topo - 8))
            self.proxima_caixa += cfg.CAIXA_DISTANCIA

    def _vaga_livre(self, x, fim):
        """Primeiro x a partir do pedido que fica longe de todo obstaculo."""
        for o in sorted(self.obstaculos, key=lambda o: o.x):
            if abs(x - o.x) < cfg.CAIXA_FOLGA:
                x = o.x + cfg.CAIXA_FOLGA
        return x if x <= fim else None

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
        """Fundo de reserva, desenhado com formas: so entra sem assets/fundos."""
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

    _sombras = {}       # (topo do vao) -> gradientes prontos, feitos uma vez

    @classmethod
    def _sombra_do_buraco(cls, tela, esq, dire, topo):
        """Sombra do vao entre duas plataformas, de `topo` ate o pe da tela."""
        if dire <= 0 or esq >= cfg.LARGURA or dire <= esq:
            return
        if topo not in cls._sombras:
            alt = cfg.ALTURA - topo
            fundo = pygame.Surface((cfg.LARGURA, alt), pygame.SRCALPHA)
            for y in range(alt):
                forca = int(cfg.BURACO_SOMBRA * (y / alt) ** 0.8)
                pygame.draw.line(fundo, (8, 6, 14, forca), (0, y), (cfg.LARGURA, y))
            lado = pygame.Surface((cfg.BURACO_SOMBRA_LADO, alt), pygame.SRCALPHA)
            for x in range(cfg.BURACO_SOMBRA_LADO):
                forca = int(70 * (1 - x / cfg.BURACO_SOMBRA_LADO) ** 2)
                pygame.draw.line(lado, (8, 6, 14, forca), (x, 0), (x, alt))
            cls._sombras[topo] = (fundo, lado, pygame.transform.flip(lado, True, False))
        fundo, lado_esq, lado_dir = cls._sombras[topo]
        larg = dire - esq
        tela.blit(fundo, (esq, topo), (0, 0, larg, fundo.get_height()))
        faixa = min(cfg.BURACO_SOMBRA_LADO, larg // 2)
        tela.blit(lado_esq, (esq, topo), (0, 0, faixa, fundo.get_height()))
        tela.blit(lado_dir, (dire - faixa, topo),
                  (cfg.BURACO_SOMBRA_LADO - faixa, 0, faixa, fundo.get_height()))

    @staticmethod
    def _pedacos(x_ini, x_fim):
        """Corta o intervalo nas bocas dos tuneis: cada pedaco tem uma paleta so."""
        meio = cfg.TUNEL_LARGURA / 2
        k = max(1, round(x_ini / cfg.TRECHO_CENARIO))
        while k * cfg.TRECHO_CENARIO - meio < x_fim:
            for corte in (k * cfg.TRECHO_CENARIO - meio, k * cfg.TRECHO_CENARIO + meio):
                if x_ini < corte < x_fim:
                    yield x_ini, corte
                    x_ini = corte
            k += 1
        yield x_ini, x_fim

    def desenhar(self, tela, camera_x, paleta_em):
        """`paleta_em(x)` devolve as cores do chao do cenario no ponto x do mundo."""
        # o buraco e so um vao: o fundo aparece por ele, com uma sombra leve
        # que escurece pra baixo e junto das duas paredes
        for a, b in zip(self.segmentos, self.segmentos[1:]):
            if b.x > a.fim + 1:
                self._sombra_do_buraco(tela, int(a.fim - camera_x), int(b.x - camera_x),
                                       int(max(a.topo, b.topo)))
        for seg in self.segmentos:
            topo = int(seg.topo)
            alt = cfg.ALTURA - topo
            for a, b in self._pedacos(seg.x, seg.fim):
                cores = paleta_em((a + b) / 2)
                r = pygame.Rect(int(a - camera_x), topo,
                                int(b - camera_x) - int(a - camera_x), alt)
                pygame.draw.rect(tela, cores["chao"], r)
                pygame.draw.rect(tela, cores["topo"], (r.x, r.y, r.width, 9))
                # riscos de asfalto pra dar sensacao de velocidade
                for x in range(r.x - (int(camera_x) % 60), r.right, 60):
                    if r.x < x < r.right - 8:
                        pygame.draw.rect(tela, cores["lado"], (x, r.y + 26, 26, 4))
            esq, dire = int(seg.x - camera_x), int(seg.fim - camera_x)
            pygame.draw.rect(tela, paleta_em(seg.x)["lado"], (esq, topo, 4, alt))
            pygame.draw.rect(tela, paleta_em(seg.fim)["lado"], (dire - 4, topo, 4, alt))
        for m in self.moedas:
            m.desenhar(tela, camera_x)
        for o in self.obstaculos:
            o.desenhar(tela, camera_x)
        for c in self.caixas:
            c.desenhar(tela, camera_x)
        for h in self.humanos:
            h.desenhar(tela, camera_x)
