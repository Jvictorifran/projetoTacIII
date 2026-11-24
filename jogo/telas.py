"""Telas de menu: inicial, pausa, configuracoes, lista de fases, multiplayer e sala.

Toda tela segue o mesmo contrato (o `Jogo` nao precisa saber qual e qual):
`evento(ev)`, `atualizar(dt)` e `desenhar(tela)`. As de botoes herdam de
`MenuLista`, que cuida de setas, mouse, rolagem e desenho dos botoes - cada
tela so diz quais sao as opcoes e o que cada uma faz.
"""

import pygame

from jogo import config as cfg
from jogo import fase as fases
from jogo import progresso
from jogo import sons

COR_BOTAO = (34, 28, 52)
COR_BORDA = (86, 76, 116)
COR_APAGADO = (150, 144, 164)
COR_ALERTA = (236, 96, 96)
TECLAS_OK = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)


def botao(jogo, r, rotulo, escolhido, cor=None, fonte=None):
    tela = jogo.tela
    if escolhido:
        pygame.draw.rect(tela, cfg.COR_ZUMBI_ESCURO, r.inflate(8, 8), border_radius=14)
    pygame.draw.rect(tela, COR_BOTAO, r, border_radius=10)
    pygame.draw.rect(tela, cfg.COR_ZUMBI if escolhido else COR_BORDA, r, 2, border_radius=10)
    jogo.texto(rotulo, fonte or jogo.fonte, r.centerx, r.centery,
               cor or (cfg.COR_ZUMBI if escolhido else cfg.COR_TEXTO), True)


class CampoTexto:
    """Uma linha de texto digitada (nome do jogador, IP, nome da fase)."""

    def __init__(self, texto="", limite=16, permitido=None):
        self.texto = texto
        self.limite = limite
        self.permitido = permitido      # string com os caracteres aceitos

    def evento(self, ev):
        """Devolve "ok", "cancelar" ou None."""
        if ev.type == pygame.TEXTINPUT:
            for ch in ev.text:
                if len(self.texto) < self.limite and ch.isprintable() and \
                        (self.permitido is None or ch in self.permitido):
                    self.texto += ch
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "ok"
            if ev.key == pygame.K_ESCAPE:
                return "cancelar"
            if ev.key == pygame.K_BACKSPACE:
                self.texto = self.texto[:-1]
        return None

    def mostrar(self, agora):
        return self.texto + ("_" if int(agora * 2) % 2 == 0 else " ")


class MenuLista:
    titulo = ""
    largura, altura, passo = 420, 40, 48
    topo = 200                  # centro do primeiro botao
    max_visiveis = 7

    def __init__(self, jogo):
        self.jogo = jogo
        self.escolhido = 0
        self.rolagem = 0
        self.campo = None           # CampoTexto ativo e a chave dele
        self.campo_chave = None
        self.relogio = 0.0
        self.mensagem = None        # (texto, tempo restante)

    # ---- o que cada tela define
    def opcoes(self):
        return []

    def acionar(self, chave):
        pass

    def ajustar(self, chave, direcao):
        """Setas pros lados numa opcao (volume, minutos...)."""

    def voltar(self):
        pass

    def campo_ok(self, chave, texto):
        pass

    def desenhar_fundo(self, tela):
        pass

    def cor(self, chave):
        return None

    # ---- comportamento comum
    def avisar(self, texto, tempo=2.5):
        self.mensagem = (texto, tempo)

    def editar(self, chave, campo):
        self.campo, self.campo_chave = campo, chave
        pygame.key.start_text_input()

    def rect(self, i):
        r = pygame.Rect(0, 0, self.largura, self.altura)
        r.center = (cfg.LARGURA // 2, self.topo + (i - self.rolagem) * self.passo)
        return r

    def visiveis(self, total):
        return range(self.rolagem, min(total, self.rolagem + self.max_visiveis))

    def em(self, pos, total):
        for i in self.visiveis(total):
            if self.rect(i).collidepoint(pos):
                return i
        return None

    def mover(self, passo, total):
        self.escolhido = (self.escolhido + passo) % total
        if self.escolhido < self.rolagem:
            self.rolagem = self.escolhido
        elif self.escolhido >= self.rolagem + self.max_visiveis:
            self.rolagem = self.escolhido - self.max_visiveis + 1
        sons.tocar("clique")

    def evento(self, ev):
        if self.campo is not None:
            r = self.campo.evento(ev)
            if r is not None:
                campo, chave = self.campo, self.campo_chave
                self.campo = self.campo_chave = None
                if r == "ok":
                    self.campo_ok(chave, campo.texto)
            return
        ops = self.opcoes()
        if not ops:
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.voltar()
            return
        self.escolhido = min(self.escolhido, len(ops) - 1)
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.voltar()
            elif ev.key in (pygame.K_UP, pygame.K_w):
                self.mover(-1, len(ops))
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.mover(1, len(ops))
            elif ev.key in (pygame.K_LEFT, pygame.K_a):
                self.ajustar(ops[self.escolhido][0], -1)
            elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                self.ajustar(ops[self.escolhido][0], 1)
            elif ev.key in TECLAS_OK:
                sons.tocar("clique")
                self.acionar(ops[self.escolhido][0])
        elif ev.type == pygame.MOUSEMOTION:
            i = self.em(ev.pos, len(ops))
            if i is not None:
                self.escolhido = i
        elif ev.type == pygame.MOUSEWHEEL:
            self.mover(-ev.y, len(ops))
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            i = self.em(ev.pos, len(ops))
            if i is not None:
                self.escolhido = i
                sons.tocar("clique")
                self.acionar(ops[i][0])

    def atualizar(self, dt):
        self.relogio += dt
        if self.mensagem:
            texto, t = self.mensagem
            self.mensagem = (texto, t - dt) if t - dt > 0 else None

    def desenhar(self, tela):
        j = self.jogo
        j.veu()
        if self.titulo:
            j.texto(self.titulo, j.fonte_g, cfg.LARGURA // 2, 64, cfg.COR_ZUMBI, True)
        self.desenhar_fundo(tela)
        ops = self.opcoes()
        for i in self.visiveis(len(ops)):
            chave, rotulo = ops[i]
            if self.campo is not None and chave == self.campo_chave:
                rotulo = rotulo.split(":")[0] + ": " + self.campo.mostrar(self.relogio)
            botao(j, self.rect(i), rotulo, i == self.escolhido, self.cor(chave), j.fonte_m)
        if self.rolagem > 0:
            j.texto("^", j.fonte, cfg.LARGURA // 2, self.rect(self.rolagem).top - 14, centro=True)
        if self.rolagem + self.max_visiveis < len(ops):
            j.texto("v", j.fonte, cfg.LARGURA // 2,
                    self.rect(self.rolagem + self.max_visiveis - 1).bottom + 12, centro=True)
        if self.mensagem:
            j.texto(self.mensagem[0], j.fonte_p, cfg.LARGURA // 2, cfg.ALTURA - 50,
                    cfg.COR_MOEDA, True)


# ------------------------------------------------------------------ inicial
class MenuPrincipal(MenuLista):
    topo, passo = 198, 46

    def opcoes(self):
        return [("novo", "NOVO JOGO"), ("fases", "FASES"), ("editor", "EDITOR DE FASES"),
                ("multi", "MULTIPLAYER (PLACAR LAN)"), ("loja", "LOJA"),
                ("config", "CONFIGURACOES"), ("sair", "SAIR")]

    def acionar(self, chave):
        j = self.jogo
        if chave == "novo":
            j.comecar()
        elif chave == "fases":
            j.ir(j.FASES, TelaFases(j, editar=False))
        elif chave == "editor":
            j.ir(j.FASES, TelaFases(j, editar=True))
        elif chave == "multi":
            j.ir(j.MULTI, TelaMultiplayer(j))
        elif chave == "loja":
            j.abrir_loja()
        elif chave == "config":
            j.ir(j.CONFIG, Configuracoes(j))
        else:
            j.sair = True

    def voltar(self):
        self.jogo.sair = True

    def desenhar_fundo(self, tela):
        j = self.jogo
        cx = cfg.LARGURA // 2
        j.texto("ZUMBI TSUNAMI", j.fonte_g, cx, 64, cfg.COR_ZUMBI, True)
        linha = f"Moedas: {progresso.dados['moedas']}"
        if j.recorde:
            linha += f"   -   Recorde: {j.recorde}"
        j.texto(linha, j.fonte_p, cx, 108, cfg.COR_MOEDA, True)
        if j.ultima:
            metros, moedas, pontos = j.ultima
            j.texto(f"Ultima partida: {metros} m  -  {moedas} moedas  -  {pontos} pts",
                    j.fonte_p, cx, 134, centro=True)
        j.texto("Setas escolhem  -  ENTER confirma  -  no jogo: ESPACO pula, ESC pausa, M som",
                j.fonte_p, cx, cfg.ALTURA - 20, centro=True)


# -------------------------------------------------------------------- pausa
class Pausa(MenuLista):
    titulo = "PAUSA"
    topo = 220

    def opcoes(self):
        destino = {"editor": "VOLTAR AO EDITOR", "sala": "VOLTAR A SALA",
                   "fases": "VOLTAR AS FASES"}.get(self.jogo.origem, "MENU PRINCIPAL")
        return [("continuar", "CONTINUAR"), ("reiniciar", "REINICIAR"), ("sair", destino)]

    def acionar(self, chave):
        j = self.jogo
        if chave == "continuar":
            j.estado = j.JOGANDO
        elif chave == "reiniciar":
            j.terminar_partida()
            j.repetir_partida()
        else:
            j.terminar_partida()
            j.voltar_da_partida()

    def voltar(self):
        self.jogo.estado = self.jogo.JOGANDO

    def desenhar_fundo(self, tela):
        j = self.jogo
        j.texto(f"{j.metros} m  -  {len(j.zumbis)} zumbis  -  {j.pontuacao()} pts",
                j.fonte_p, cfg.LARGURA // 2, 112, centro=True)
        if j.cliente:
            j.texto("Sair ou reiniciar manda o resultado desta partida pro placar",
                    j.fonte_p, cfg.LARGURA // 2, 140, COR_APAGADO, True)


# ------------------------------------------------------------ configuracoes
class Configuracoes(MenuLista):
    titulo = "CONFIGURACOES"
    topo = 160

    def __init__(self, jogo):
        super().__init__(jogo)
        self.confirmar_zerar = False

    def opcoes(self):
        d = progresso.dados
        som = "SEM AUDIO" if not sons.disponivel() else ("LIGADOS" if sons.ligado else "DESLIGADOS")
        return [("som", f"EFEITOS SONOROS: {som}"),
                ("musica", "MUSICA TEMA: " + ("LIGADA" if d["musica"] else "DESLIGADA")),
                ("volume", f"VOLUME:  < {d['volume']}% >"),
                ("tela", "TELA CHEIA: " + ("SIM" if d["tela_cheia"] else "NAO")),
                ("nome", f"NOME NO PLACAR: {d['nome']}"),
                ("zerar", "CONFIRMA? ENTER DE NOVO" if self.confirmar_zerar else "ZERAR PROGRESSO"),
                ("voltar", "VOLTAR")]

    def cor(self, chave):
        if chave == "zerar" and self.confirmar_zerar:
            return COR_ALERTA
        return None

    def acionar(self, chave):
        j = self.jogo
        if chave != "zerar":
            self.confirmar_zerar = False
        if chave == "som":
            j.alternar_som()
        elif chave == "musica":
            j.alternar_musica()
        elif chave == "volume":
            self.ajustar(chave, 1 if progresso.dados["volume"] < 100 else -10)
        elif chave == "tela":
            j.alternar_tela_cheia()
        elif chave == "nome":
            self.editar("nome", CampoTexto(progresso.dados["nome"], 16))
        elif chave == "zerar":
            if self.confirmar_zerar:
                progresso.zerar()
                j.recorde = 0
                self.confirmar_zerar = False
                self.avisar("Progresso zerado: moedas, compras e recorde")
            else:
                self.confirmar_zerar = True
        else:
            self.voltar()

    def ajustar(self, chave, direcao):
        if chave == "volume":
            d = progresso.dados
            d["volume"] = max(0, min(100, d["volume"] + 10 * (1 if direcao > 0 else -1)))
            sons.definir_volume(d["volume"] / 100)
            sons.tocar("moeda")
            progresso.salvar()

    def campo_ok(self, chave, texto):
        progresso.dados["nome"] = texto.strip()[:16] or "Jogador"
        progresso.salvar()

    def voltar(self):
        self.jogo.ir(self.jogo.MENU)

    def desenhar_fundo(self, tela):
        j = self.jogo
        j.texto("Setas pros lados mudam o volume  -  ENTER escolhe  -  ESC volta",
                j.fonte_p, cfg.LARGURA // 2, cfg.ALTURA - 20, centro=True)


# ------------------------------------------------------------------- fases
class TelaFases(MenuLista):
    topo = 160
    max_visiveis = 7

    def __init__(self, jogo, editar):
        super().__init__(jogo)
        self.editar_fases = editar
        self.titulo = "EDITOR DE FASES" if editar else "FASES"
        self.lista = fases.listar()
        self.largura = 600

    def opcoes(self):
        ops = [("nova", "+ CRIAR FASE NOVA")] if self.editar_fases else []
        for i, f in enumerate(self.lista):
            ops.append((i, f"{f.nome}  -  {f.metros} m  -  vel {f.velocidade}"))
        return ops + [("voltar", "VOLTAR")]

    def acionar(self, chave):
        j = self.jogo
        if chave == "voltar":
            self.voltar()
        elif chave == "nova":
            numero = len(self.lista) + 1
            nomes = {f.nome for f in self.lista}
            while f"Fase {numero}" in nomes:
                numero += 1
            j.abrir_editor(fases.Fase(f"Fase {numero}", progresso.dados["nome"]))
        elif self.editar_fases:
            j.abrir_editor(self.lista[chave])
        else:
            j.comecar(self.lista[chave], origem="fases")

    def voltar(self):
        self.jogo.ir(self.jogo.MENU)

    def desenhar_fundo(self, tela):
        j = self.jogo
        cx = cfg.LARGURA // 2
        if not self.lista and not self.editar_fases:
            j.texto("Nenhuma fase salva ainda: crie a primeira no EDITOR DE FASES.",
                    j.fonte_p, cx, 112, COR_APAGADO, True)
        else:
            dica = ("ENTER abre a fase no editor" if self.editar_fases else
                    "Fase vale pontos, mas as moedas dela nao vao pro cofre")
            j.texto(dica, j.fonte_p, cx, 112, COR_APAGADO, True)


# ------------------------------------------------------------- multiplayer
class TelaMultiplayer(MenuLista):
    titulo = "MULTIPLAYER"
    topo = 150
    max_visiveis = 8
    passo = 44

    def __init__(self, jogo):
        super().__init__(jogo)
        from rede.descoberta import Buscador
        self.buscador = Buscador()
        self.salas = []
        self.minutos = 10
        self.lista_fases = fases.listar()
        self.indice_fase = 0
        self.ip = ""
        self.largura = 620

    def opcoes(self):
        ops = [("livre", "HOSPEDAR PLACAR LIVRE"),
               ("desafio", f"HOSPEDAR DESAFIO:  < {self.minutos} min >")]
        if self.lista_fases:
            f = self.lista_fases[self.indice_fase]
            ops.append(("desafio_fase", f"DESAFIO NA FASE:  < {f.nome} >"))
        for ip, porta, info in self.salas:
            modo = "desafio" if info.get("modo") == "desafio" else "livre"
            ops.append((("sala", ip, porta),
                        f"ENTRAR: {info.get('sala', '?')} ({modo}, {info.get('jogadores', 0)} jog.)"))
        ops.append(("ip", f"ENTRAR POR IP: {self.ip}"))
        ops.append(("voltar", "VOLTAR"))
        return ops

    def cor(self, chave):
        return cfg.COR_MOEDA if isinstance(chave, tuple) else None

    def ajustar(self, chave, direcao):
        if chave == "desafio":
            self.minutos = max(2, min(60, self.minutos + direcao * (1 if self.minutos < 5 else 5)))
        elif chave == "desafio_fase" and self.lista_fases:
            self.indice_fase = (self.indice_fase + direcao) % len(self.lista_fases)
        sons.tocar("clique")

    def acionar(self, chave):
        j = self.jogo
        erro = None
        if chave == "livre":
            erro = j.hospedar("livre")
        elif chave == "desafio":
            erro = j.hospedar("desafio", self.minutos)
        elif chave == "desafio_fase":
            erro = j.hospedar("desafio", self.minutos, self.lista_fases[self.indice_fase])
        elif isinstance(chave, tuple):
            j.entrar_na_sala(chave[1], chave[2])
        elif chave == "ip":
            self.editar("ip", CampoTexto(self.ip, 15, "0123456789."))
        else:
            self.voltar()
        if erro:
            self.avisar(erro, 4)

    def campo_ok(self, chave, texto):
        self.ip = texto.strip()
        if self.ip:
            self.jogo.entrar_na_sala(self.ip)

    def atualizar(self, dt):
        super().atualizar(dt)
        self.salas = self.buscador.salas()

    def voltar(self):
        self.jogo.ir(self.jogo.MENU)

    def fechar(self):
        self.buscador.fechar()

    def desenhar_fundo(self, tela):
        j = self.jogo
        cx = cfg.LARGURA // 2
        j.texto("Cada um joga a sua partida; o ranking e de todos da rede.",
                j.fonte_p, cx, 100, COR_APAGADO, True)
        if self.buscador.erro:
            j.texto(self.buscador.erro, j.fonte_p, cx, cfg.ALTURA - 24, COR_ALERTA, True)
        elif not self.salas:
            j.texto("Procurando salas na rede...  (o desafio usa o tempo escolhido com as setas)",
                    j.fonte_p, cx, cfg.ALTURA - 24, COR_APAGADO, True)


# -------------------------------------------------------------------- sala
class TelaSala(MenuLista):
    topo = 470
    largura = 260
    max_visiveis = 2

    def opcoes(self):
        return [("jogar", "JOGAR"), ("sair", "SAIR DA SALA")]

    def rect(self, i):
        r = pygame.Rect(0, 0, self.largura, self.altura)
        r.center = (cfg.LARGURA // 2 + (i * 2 - 1) * 150, self.topo)
        return r

    def evento(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.mover(1, 2)
            return
        super().evento(ev)

    def cor(self, chave):
        if chave == "jogar" and not self.pode_jogar():
            return COR_APAGADO
        return None

    def pode_jogar(self):
        c = self.jogo.cliente
        if c is None or not c.recebido:
            return False
        return c.restante() is None or c.restante() > 0

    def acionar(self, chave):
        j = self.jogo
        if chave == "sair":
            self.voltar()
        elif self.pode_jogar():
            j.jogar_na_sala()
        else:
            self.avisar("Ainda conectando..." if not j.cliente.recebido else "O desafio acabou")

    def voltar(self):
        self.jogo.sair_da_sala()

    def desenhar_fundo(self, tela):
        j = self.jogo
        c = j.cliente
        cx = cfg.LARGURA // 2
        if c is None:
            return
        titulo = c.sala or "Conectando..."
        j.texto(titulo, j.fonte_g, cx, 46, cfg.COR_ZUMBI, True)
        if c.modo == "desafio":
            resto = c.restante() or 0
            alvo = f"fase \"{c.fase['nome']}\"" if c.fase else f"semente {c.seed}"
            linha = f"DESAFIO no mesmo mapa ({alvo})  -  falta {int(resto) // 60}:{int(resto) % 60:02d}"
            if resto <= 0:
                linha = "DESAFIO ENCERRADO - ranking final"
        else:
            linha = "PLACAR LIVRE - vale a sua melhor partida no modo infinito"
        j.texto(linha, j.fonte_p, cx, 90, cfg.COR_MOEDA, True)
        if j.servidor is not None:
            j.texto(f"Voce e o anfitriao: IP {j.servidor.ip}  (sair fecha a sala)",
                    j.fonte_p, cx, 114, COR_APAGADO, True)

        # tabela
        x0, y = 150, 142
        colunas = ((x0, "#"), (x0 + 50, "JOGADOR"), (x0 + 380, "PONTOS"),
                   (x0 + 500, "METROS"), (x0 + 610, "HORDA"))
        for x, nome in colunas:
            j.texto(nome, j.fonte_p, x, y, cfg.COR_ZUMBI)
        pygame.draw.line(tela, COR_BORDA, (x0, y + 26), (x0 + 670, y + 26), 2)
        for i, l in enumerate(c.linhas[:10]):
            yy = y + 34 + i * 27
            eu = l["nome"] == c.nome
            cor = cfg.COR_MOEDA if eu else cfg.COR_TEXTO
            nome = l["nome"] + ("  (voce)" if eu else "")
            if l.get("jogando"):
                nome += f"  - jogando: {l.get('agora', 0)} pts"
            valores = (f"{i + 1}o", nome, str(l["pontos"]), str(l["metros"]), str(l["horda_max"]))
            for (x, _), v in zip(colunas, valores):
                j.texto(v, j.fonte_p, x, yy, cfg.COR_ZUMBI if l.get("jogando") and x == x0 + 50 and not eu else cor)
        if not c.linhas and c.recebido:
            j.texto("Ninguem jogou ainda. Seja o primeiro!", j.fonte_p, cx, y + 60, COR_APAGADO, True)
        if c.erro:
            j.texto(c.erro, j.fonte_p, cx, 432, COR_ALERTA, True)
        elif c.aviso:
            j.texto(c.aviso[0], j.fonte_p, cx, 432, cfg.COR_MOEDA, True)
        j.texto("ENTER escolhe  -  ESC sai da sala", j.fonte_p, cx, cfg.ALTURA - 20, COR_APAGADO, True)
