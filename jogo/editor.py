"""Editor de fases: paleta de pecas, grade de colunas e teste na hora.

Cada mudanca na fase e um *comando* (padrao Command) com `executar` e
`desfazer`, guardado num historico - e isso que da o Ctrl+Z / Ctrl+Y. Uma
pincelada arrastando o mouse vira um comando so (`Grupo`), entao desfazer
volta a pincelada inteira.

A previa e o proprio jogo: o editor monta um `Mundo` com o `GeradorDeFase` e
desenha com o mesmo codigo da partida, entao o que se ve e o que se joga.
"""

import pygame

from jogo import config as cfg
from jogo import fase as fases
from jogo import poderes
from jogo import recursos
from jogo import sons
from jogo.cenario import nomes as nomes_dos_cenarios
from jogo.mundo import TEMPO_NO_AR, Mundo
from jogo.telas import COR_ALERTA, COR_APAGADO, COR_BORDA, COR_BOTAO, CampoTexto

COLUNA = fases.COLUNA
BARRA_TOPO = 52
BARRA_BAIXO = cfg.ALTURA - 50
ROLAGEM = 900               # px/s com as setas (SHIFT: x3)
FERRAMENTAS = (("chao", "CHAO"), ("buraco", "BURACO"), ("carro", "CARRO"),
               ("humano", "HUMANO"), ("moeda", "MOEDA"), ("caixa", "CAIXA"),
               ("borracha", "APAGAR"))
PASSO_TAMANHO = 25          # colunas que + e - acrescentam/tiram (20 m)


# ------------------------------------------------------------------ comandos
class Comando:
    def executar(self, fase):
        raise NotImplementedError

    def desfazer(self, fase):
        raise NotImplementedError


class MudarColuna(Comando):
    """Nivel do chao de uma coluna. Virar buraco derruba o que estava em cima."""

    def __init__(self, fase, col, nivel):
        self.col, self.antes, self.depois = col, fase.colunas[col], nivel
        obj = fase.objetos.get(col)
        self.derrubado = obj if nivel == fases.BURACO and obj and obj["tipo"] != "moeda" else None

    def executar(self, fase):
        fase.colunas[self.col] = self.depois
        if self.derrubado:
            del fase.objetos[self.col]

    def desfazer(self, fase):
        fase.colunas[self.col] = self.antes
        if self.derrubado:
            fase.objetos[self.col] = self.derrubado


class TrocarObjeto(Comando):
    """Poe, troca ou tira (depois=None) o objeto de uma coluna."""

    def __init__(self, fase, col, depois):
        self.col, self.antes, self.depois = col, fase.objetos.get(col), depois

    def _por(self, fase, obj):
        if obj is None:
            fase.objetos.pop(self.col, None)
        else:
            fase.objetos[self.col] = obj

    def executar(self, fase):
        self._por(fase, self.depois)

    def desfazer(self, fase):
        self._por(fase, self.antes)


class MudarTamanho(Comando):
    def __init__(self, fase, total):
        self.antes = (list(fase.colunas), dict(fase.objetos))
        self.total = total
        self.depois = None

    def executar(self, fase):
        if self.depois is None:
            if self.total > fase.total:
                fase.colunas += [0] * (self.total - fase.total)
            else:
                del fase.colunas[self.total:]
            fase.travar()           # o tunel pode ter entrado no trecho novo
            self.depois = (list(fase.colunas), dict(fase.objetos))
        else:
            fase.colunas, fase.objetos = list(self.depois[0]), dict(self.depois[1])

    def desfazer(self, fase):
        fase.colunas, fase.objetos = list(self.antes[0]), dict(self.antes[1])


class Grupo(Comando):
    """Varios comandos que se desfazem juntos (uma pincelada)."""

    def __init__(self):
        self.partes = []

    def adicionar(self, fase, comando):
        comando.executar(fase)
        self.partes.append(comando)

    def executar(self, fase):
        for c in self.partes:
            c.executar(fase)

    def desfazer(self, fase):
        for c in reversed(self.partes):
            c.desfazer(fase)


class Historico:
    def __init__(self):
        self.feitos, self.desfeitos = [], []

    def registrar(self, comando):
        self.feitos.append(comando)
        self.desfeitos.clear()

    def desfazer(self, fase):
        if not self.feitos:
            return False
        c = self.feitos.pop()
        c.desfazer(fase)
        self.desfeitos.append(c)
        return True

    def refazer(self, fase):
        if not self.desfeitos:
            return False
        c = self.desfeitos.pop()
        c.executar(fase)
        self.feitos.append(c)
        return True


# -------------------------------------------------------------------- editor
class Editor:
    def __init__(self, jogo, fase):
        self.jogo = jogo
        self.fase = fase
        self.historico = Historico()
        self.ferramenta = 0
        self.poder = 0                  # poder da proxima caixa
        self.camera = -100.0
        self.mouse = (0, 0)
        self.pincelada = None           # Grupo em andamento (mouse apertado)
        self.visitadas = set()
        self.apagando = False           # pincelada com o botao direito
        self.sujo = fase.caminho is None
        self.sair_confirmar = False
        self.campo = None
        self.relogio = 0.0
        self.mensagem = None
        self.previa = None
        self.problemas = []
        self.atualizar_previa()
        jogo.cenario.comecar_em(fase.cenario)

    # ------------------------------------------------------------- apoio
    def avisar(self, texto, tempo=2.5):
        self.mensagem = (texto, tempo)

    def atualizar_previa(self):
        self.previa = Mundo(fases.GeradorDeFase(self.fase))
        self.problemas = self.fase.problemas()

    def mudou(self):
        self.sujo = True
        self.sair_confirmar = False
        self.atualizar_previa()

    def coluna_em(self, x_tela):
        return int((x_tela + self.camera) // COLUNA)

    @staticmethod
    def nivel_em(y):
        return max(0, min(cfg.NIVEIS - 1, round((cfg.CHAO_Y - y) / cfg.ALTURA_NIVEL)))

    def rect_ferramenta(self, i):
        return pygame.Rect(8 + i * 122, 8, 116, 36)

    def na_area(self, pos):
        return BARRA_TOPO <= pos[1] < BARRA_BAIXO

    # ----------------------------------------------------------- entrada
    def evento(self, ev):
        if self.campo is not None:
            r = self.campo.evento(ev)
            if r == "ok":
                nome = self.campo.texto.strip()[:32]
                if nome and nome != self.fase.nome:
                    self.fase.nome = nome
                    self.sujo = True
            if r is not None:
                self.campo = None
            return
        if ev.type == pygame.KEYDOWN:
            self.tecla(ev)
        elif ev.type == pygame.MOUSEMOTION:
            self.mouse = ev.pos
            if self.pincelada is not None and self.na_area(ev.pos):
                self.pincelar(ev.pos, primeiro=False)
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            self.mouse = ev.pos
            if ev.button in (1, 3) and ev.pos[1] < BARRA_TOPO:
                for i in range(len(FERRAMENTAS)):
                    if self.rect_ferramenta(i).collidepoint(ev.pos):
                        self.escolher(i)
            elif ev.button in (1, 3) and self.na_area(ev.pos):
                self.pincelada = Grupo()
                self.visitadas = set()
                self.apagando = ev.button == 3
                self.pincelar(ev.pos, primeiro=True)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button in (1, 3):
            self.fechar_pincelada()
        elif ev.type == pygame.MOUSEWHEEL:
            self.camera += (ev.x - ev.y) * 120

    def tecla(self, ev):
        ctrl = ev.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
        k = ev.key
        if ctrl and k == pygame.K_z:
            refazer = ev.mod & pygame.KMOD_SHIFT
            feito = (self.historico.refazer if refazer else self.historico.desfazer)(self.fase)
            if feito:
                self.mudou()
            else:
                self.avisar("Nada pra " + ("refazer" if refazer else "desfazer"))
        elif ctrl and k == pygame.K_y:
            if self.historico.refazer(self.fase):
                self.mudou()
        elif ctrl and k == pygame.K_s:
            self.salvar()
        elif k in (pygame.K_F5, pygame.K_t):
            self.fechar_pincelada()
            self.jogo.comecar(self.fase, origem="editor")
        elif k == pygame.K_ESCAPE:
            if self.sujo and not self.sair_confirmar:
                self.sair_confirmar = True
                self.avisar("Fase nao salva! ESC de novo sai sem salvar (Ctrl+S salva)", 4)
            else:
                from jogo.telas import TelaFases
                self.jogo.fundo_novo()
                self.jogo.ir(self.jogo.FASES, TelaFases(self.jogo, editar=True))
        elif pygame.K_1 <= k <= pygame.K_7:
            self.escolher(k - pygame.K_1)
        elif k == pygame.K_HOME:
            self.camera = -100
        elif k == pygame.K_END:
            self.camera = self.fase.chegada - cfg.LARGURA + 300
        elif k == pygame.K_v:
            vs = fases.VELOCIDADES
            self.fase.velocidade = vs[(vs.index(self.fase.velocidade) + 1) % len(vs)]
            self.mudou()
            self.avisar(f"Velocidade {self.fase.velocidade} px/s: o tamanho maximo dos buracos mudou")
        elif k == pygame.K_c:
            nomes = nomes_dos_cenarios()
            i = nomes.index(self.fase.cenario) if self.fase.cenario in nomes else -1
            self.fase.cenario = nomes[(i + 1) % len(nomes)]
            self.jogo.cenario.comecar_em(self.fase.cenario)
            self.sujo = True
        elif k == pygame.K_n:
            self.campo = CampoTexto(self.fase.nome, 32)
            pygame.key.start_text_input()
        elif k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_MINUS,
                   pygame.K_KP_MINUS):
            mais = k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS)
            total = self.fase.total + (PASSO_TAMANHO if mais else -PASSO_TAMANHO)
            total = max(fases.MIN_COLUNAS, min(fases.MAX_COLUNAS, total))
            if total == self.fase.total:
                self.avisar("Tamanho no limite (%d a %d m)" % (
                    fases.MIN_COLUNAS * COLUNA // cfg.PX_POR_METRO,
                    fases.MAX_COLUNAS * COLUNA // cfg.PX_POR_METRO))
                return
            c = MudarTamanho(self.fase, total)
            c.executar(self.fase)
            self.historico.registrar(c)
            self.mudou()

    def escolher(self, i):
        self.ferramenta = i
        sons.tocar("clique")

    # ---------------------------------------------------------- pintar
    def pincelar(self, pos, primeiro):
        col = self.coluna_em(pos[0])
        if not 0 <= col < self.fase.total:
            return
        chave = (col, pos[1] // 10) if FERRAMENTAS[self.ferramenta][0] == "moeda" else col
        if chave in self.visitadas:
            return
        self.visitadas.add(chave)
        tamanho = len(self.pincelada.partes)
        ferramenta = "borracha" if self.apagando else FERRAMENTAS[self.ferramenta][0]
        self.aplicar(ferramenta, col, pos[1], primeiro)
        if len(self.pincelada.partes) != tamanho:
            self.mudou()

    def aplicar(self, ferramenta, col, y, primeiro):
        f, g = self.fase, self.pincelada
        travada = col in f.travadas()
        obj = f.objetos.get(col)
        if ferramenta in ("chao", "buraco"):
            nivel = self.nivel_em(y) if ferramenta == "chao" else fases.BURACO
            if travada:
                if primeiro:
                    self.avisar("Largada e tunel sao chao reto: nao da pra mexer ai")
            elif f.colunas[col] != nivel:
                g.adicionar(f, MudarColuna(f, col, nivel))
        elif ferramenta == "borracha":
            if obj is not None:
                g.adicionar(f, TrocarObjeto(f, col, None))
            elif f.colunas[col] == fases.BURACO:
                g.adicionar(f, MudarColuna(f, col, 0))
        elif ferramenta == "moeda":
            alto, baixo = fases.MOEDA_Y
            my = max(alto, min(baixo, round(y / 10) * 10))
            if obj is None or obj["tipo"] == "moeda":
                if obj is None or obj["y"] != my:
                    g.adicionar(f, TrocarObjeto(f, col, {"tipo": "moeda", "col": col, "y": my}))
            elif primeiro:
                self.avisar("Essa coluna ja tem um objeto (botao direito apaga)")
        elif primeiro:
            self.por_objeto(ferramenta, col, obj)

    def por_objeto(self, tipo, col, obj):
        f, g = self.fase, self.pincelada
        if obj is not None and obj["tipo"] == tipo:
            # clicar de novo no mesmo objeto muda ele
            novo = dict(obj)
            if tipo == "carro":
                novo["vida"] = obj["vida"] % 4 + 1
            elif tipo == "caixa":
                self.poder = (poderes.TODOS.index(obj["poder"]) + 1) % len(poderes.TODOS)
                novo["poder"] = poderes.TODOS[self.poder]
            else:
                return
            g.adicionar(f, TrocarObjeto(f, col, novo))
            return
        if not f.pode_por(tipo, col):
            if f.colunas[col] == fases.BURACO:
                self.avisar("Nao da pra por isso no buraco")
            else:
                self.avisar("Carro nao entra na largada nem no tunel")
            return
        novo = {"tipo": tipo, "col": col}
        if tipo == "carro":
            novo["vida"] = 2
        elif tipo == "caixa":
            novo["poder"] = poderes.TODOS[self.poder]
        g.adicionar(f, TrocarObjeto(f, col, novo))
        sons.tocar("clique")

    def fechar_pincelada(self):
        if self.pincelada is not None and self.pincelada.partes:
            self.historico.registrar(self.pincelada)
        self.pincelada = None

    # ------------------------------------------------------------ salvar
    def salvar(self):
        if self.problemas:
            self.avisar("Tem trecho impossivel (em vermelho): arrume antes de salvar", 4)
            sons.tocar("parede")
            return
        try:
            caminho = self.fase.salvar()
        except OSError as e:
            self.avisar(f"Nao deu pra salvar: {e.strerror}", 4)
            return
        self.sujo = False
        self.sair_confirmar = False
        self.avisar("Salvo em fases/" + caminho.replace("\\", "/").split("/")[-1])
        sons.tocar("moeda")

    # --------------------------------------------------------- atualizar
    def atualizar(self, dt):
        self.relogio += dt
        teclas = pygame.key.get_pressed()
        if self.campo is None:
            rapido = 3 if teclas[pygame.K_LSHIFT] or teclas[pygame.K_RSHIFT] else 1
            if teclas[pygame.K_RIGHT] or teclas[pygame.K_d]:
                self.camera += ROLAGEM * rapido * dt
            if teclas[pygame.K_LEFT] or teclas[pygame.K_a]:
                self.camera -= ROLAGEM * rapido * dt
        self.camera = max(-300.0, min(self.camera, self.fase.chegada - cfg.LARGURA + 400.0))
        if self.mensagem:
            texto, t = self.mensagem
            self.mensagem = (texto, t - dt) if t > dt else None

    # ----------------------------------------------------------- desenho
    def desenhar(self, tela):
        j = self.jogo
        cam = self.camera
        if not j.cenario.desenhar(tela, cam):
            self.previa.desenhar_fundo(tela, cam)
        j.cenario.desenhar_tunel(tela, cam, frente=False)
        self.previa.desenhar(tela, cam, j.cenario.paleta_em)
        j.cenario.desenhar_tunel(tela, cam, frente=True)
        self.desenhar_grade(tela, cam)
        self.desenhar_cursor(tela, cam)
        self.desenhar_barras(tela)

    def x_da_coluna(self, col):
        return int(col * COLUNA - self.camera)

    def desenhar_grade(self, tela, cam):
        f = self.fase
        camada = pygame.Surface((cfg.LARGURA, cfg.ALTURA), pygame.SRCALPHA)
        primeira = max(0, self.coluna_em(0))
        ultima = min(f.total, self.coluna_em(cfg.LARGURA) + 1)
        travadas = f.travadas()
        for col in range(primeira, ultima):
            x = self.x_da_coluna(col)
            if col in travadas:
                camada.fill((90, 110, 160, 50), (x, BARRA_TOPO, COLUNA, BARRA_BAIXO - BARRA_TOPO))
            forte = col % 25 == 0
            pygame.draw.line(camada, (255, 255, 255, 60 if forte else 18),
                             (x, BARRA_TOPO), (x, BARRA_BAIXO))
            if forte:
                j = self.jogo
                rot = j.fonte_p.render(f"{col * COLUNA // cfg.PX_POR_METRO} m", True, (230, 230, 240))
                camada.blit(rot, (x + 4, BARRA_TOPO + 4))
        for nivel in range(cfg.NIVEIS):
            y = fases.topo_do_nivel(nivel)
            for x in range(-int(cam) % 24, cfg.LARGURA, 24):
                pygame.draw.line(camada, (255, 255, 255, 40), (x, y), (x + 12, y))
        for p in self.problemas:
            x = self.x_da_coluna(p.ini)
            larg = (p.fim - p.ini + 1) * COLUNA
            camada.fill((236, 70, 80, 90), (x, BARRA_TOPO, larg, BARRA_BAIXO - BARRA_TOPO))
            pygame.draw.rect(camada, (236, 70, 80, 220), (x, BARRA_TOPO, larg, BARRA_BAIXO - BARRA_TOPO), 2)
        tela.blit(camada, (0, 0))
        # rotulos das areas travadas
        j = self.jogo
        if self.x_da_coluna(0) > -fases.LARGADA * COLUNA:
            j.texto("LARGADA", j.fonte_p, self.x_da_coluna(0) + 8, BARRA_TOPO + 28, (190, 205, 240))
        # chegada: mastro quadriculado
        x = self.x_da_coluna(f.total)
        if -20 < x < cfg.LARGURA + 20:
            for i, y in enumerate(range(BARRA_TOPO + 20, cfg.CHAO_Y, 16)):
                pygame.draw.rect(tela, (245, 245, 245) if i % 2 else (20, 20, 24), (x - 4, y, 8, 16))
            j.texto("CHEGADA", j.fonte, x + 10, BARRA_TOPO + 24, cfg.COR_MOEDA)

    def desenhar_cursor(self, tela, cam):
        if not self.na_area(self.mouse) or self.campo is not None:
            return
        col = self.coluna_em(self.mouse[0])
        if not 0 <= col < self.fase.total:
            return
        x = self.x_da_coluna(col)
        ferramenta = FERRAMENTAS[self.ferramenta][0]
        destaque = pygame.Surface((COLUNA, BARRA_BAIXO - BARRA_TOPO), pygame.SRCALPHA)
        destaque.fill((255, 255, 255, 30))
        tela.blit(destaque, (x, BARRA_TOPO))
        if ferramenta == "chao":
            y = fases.topo_do_nivel(self.nivel_em(self.mouse[1]))
            pygame.draw.rect(tela, cfg.COR_ZUMBI, (x, y, COLUNA, 9), 2)
        elif ferramenta == "moeda":
            alto, baixo = fases.MOEDA_Y
            y = max(alto, min(baixo, round(self.mouse[1] / 10) * 10))
            pygame.draw.circle(tela, cfg.COR_MOEDA, (x + COLUNA // 2, y), cfg.MOEDA_R, 2)
        # arco do pulo saindo desta coluna, na velocidade da fase
        nivel = self.fase.colunas[col]
        if nivel != fases.BURACO and ferramenta in ("chao", "buraco"):
            topo = fases.topo_do_nivel(nivel)
            v = self.fase.velocidade
            t = 0.0
            while t <= TEMPO_NO_AR + 0.25:
                px = x + COLUNA / 2 + v * t
                py = topo + cfg.VEL_PULO * t + cfg.GRAVIDADE * t * t / 2
                if py > cfg.ALTURA:
                    break
                pygame.draw.circle(tela, cfg.COR_MOEDA, (int(px), int(py)), 3)
                t += 0.035

    def desenhar_barras(self, tela):
        j = self.jogo
        f = self.fase
        faixa = pygame.Surface((cfg.LARGURA, BARRA_TOPO), pygame.SRCALPHA)
        faixa.fill((14, 11, 22, 225))
        tela.blit(faixa, (0, 0))
        for i, (chave, nome) in enumerate(FERRAMENTAS):
            r = self.rect_ferramenta(i)
            escolhida = i == self.ferramenta
            pygame.draw.rect(tela, cfg.COR_ZUMBI_ESCURO if escolhida else COR_BOTAO, r, border_radius=8)
            pygame.draw.rect(tela, cfg.COR_ZUMBI if escolhida else COR_BORDA, r, 2, border_radius=8)
            icone = None
            if chave == "caixa":
                icone = recursos.icone(poderes.TODOS[self.poder])
            if icone is not None:
                icone = pygame.transform.smoothscale(icone, (24, 24))
                tela.blit(icone, (r.x + 6, r.y + 6))
                j.texto(f"{i + 1} {nome}", j.fonte_p, r.x + 34, r.y + 8)
            else:
                j.texto(f"{i + 1} {nome}", j.fonte_p, r.centerx, r.centery, centro=True)

        faixa = pygame.Surface((cfg.LARGURA, cfg.ALTURA - BARRA_BAIXO), pygame.SRCALPHA)
        faixa.fill((14, 11, 22, 225))
        tela.blit(faixa, (0, BARRA_BAIXO))
        nome = f.nome if self.campo is None else self.campo.mostrar(self.relogio)
        info = (f"[N] {nome}{' *' if self.sujo else ''}    [V] vel {f.velocidade}    "
                f"[C] {f.cenario}    [+/-] {f.metros} m    "
                f"Ctrl+Z/Y  Ctrl+S salva  F5 testa  ESC sai")
        j.texto(info, j.fonte_p, 10, BARRA_BAIXO + 4)
        linha = None
        cor = COR_APAGADO
        if self.mensagem:
            linha, cor = self.mensagem[0], cfg.COR_MOEDA
        else:
            col = self.coluna_em(self.mouse[0])
            for p in self.problemas:
                if p.ini <= col <= p.fim:
                    linha, cor = "Impossivel: " + p.texto, COR_ALERTA
            if linha is None:
                if self.problemas:
                    linha, cor = f"{len(self.problemas)} trecho(s) impossivel(is) em vermelho", COR_ALERTA
                else:
                    linha = ("Clique poe a peca, arrasta pinta, botao direito apaga. "
                             "Clicar de novo no carro/caixa muda a vida/poder. Setas rolam.")
        j.texto(linha, j.fonte_p, 10, BARRA_BAIXO + 25, cor)
