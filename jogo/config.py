"""Constantes de configuracao do jogo."""

LARGURA = 960
ALTURA = 540
FPS = 60
TITULO = "Zumbi Tsunami 2D"

# --- Fisica ---
GRAVIDADE = 2600.0          # px/s^2
VEL_PULO = -950.0           # px/s (negativo = para cima)
COYOTE = 0.10               # tolerancia pra pular logo apos sair da borda
PULO_CURTO = 0.45           # multiplicador ao soltar a tecla cedo

# --- Rolagem / dificuldade ---
VEL_INICIAL = 330.0         # px/s
VEL_MAXIMA = 700.0
ACELERACAO = 4.0            # px/s por segundo de jogo

# --- Mundo ---
CHAO_Y = 430                # altura do nivel base do chao
ALTURA_NIVEL = 110          # diferenca entre plataformas
NIVEIS = 3                  # quantidade de alturas possiveis
INICIO_SEGURO = 2600        # trecho inicial sem obstaculos

# --- Horda ---
X_LIDER = 260               # posicao do lider na tela
ZUMBI_L = 24
ZUMBI_A = 34
LARG_FORMACAO = 5           # zumbis por coluna antes de recuar
MAX_ZUMBIS = 80

# --- Entidades ---
HUMANO_L = 24
HUMANO_A = 34
CAIXA_L = 50
CAIXA_A = 50
VEL_HUMANO = 215.0          # correndo em panico
VEL_PASSEIO = 45.0          # antes de ver a horda
RAIO_PANICO = 340.0
OBSTACULO_L = 54
OBSTACULO_A = 52
MOEDA_R = 10

# --- Cores ---
COR_CEU_TOPO = (28, 22, 48)
COR_CEU_BASE = (86, 54, 84)
COR_LUA = (240, 236, 210)
COR_PREDIO_LONGE = (44, 36, 66)
COR_PREDIO_PERTO = (30, 24, 46)
COR_JANELA = (250, 214, 120)
COR_ABISMO = (12, 9, 18)
COR_CHAO = (58, 50, 74)
COR_CHAO_LADO = (40, 34, 52)
COR_CHAO_TOPO = (74, 118, 72)
COR_ZUMBI = (110, 190, 90)
COR_ZUMBI_ESCURO = (70, 140, 60)
COR_HUMANO = (232, 216, 200)
COR_HUMANO_ROUPA = (86, 132, 214)
COR_OBSTACULO = (200, 70, 70)
COR_OBSTACULO_ESCURO = (140, 44, 44)
COR_MOEDA = (250, 200, 60)
COR_TEXTO = (245, 245, 245)
COR_SOMBRA = (0, 0, 0)
COR_CAIXA = (211, 175, 55)
