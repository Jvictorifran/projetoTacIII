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
TETO = 60                   # a horda nunca sobe alem disso, mesmo com poder
PX_POR_METRO = 50           # escala do placar de distancia
FOLGA_BEIRADA = 24          # pe ate isso abaixo da beirada ainda sobe nela
BURACO_SOMBRA = 105         # opacidade (0-255) da sombra no fundo do buraco
BURACO_SOMBRA_LADO = 22     # largura da sombra que cada parede joga no vao

# --- Cenarios de fundo ---
FUNDO_TROCA_M = 250         # a cada quantos metros tem um tunel e o cenario muda
TRECHO_CENARIO = FUNDO_TROCA_M * PX_POR_METRO   # o mesmo, em px
FUNDO_PARALAXE = (0.10, 0.35)   # quanto as camadas longe/perto acompanham a camera

# --- Tunel entre dois cenarios ---
TUNEL_LARGURA = 720         # largura do vao (igual a da arte em assets/fundos)
TUNEL_TETO = 215            # y do teto do vao: cabe o pulo normal inteiro
TUNEL_RAMPA = 260           # distancia em que o teto desce ate a boca do tunel
TUNEL_MARGEM = 320          # chao reto e sem carro antes e depois do tunel

# --- Horda ---
X_LIDER = 260               # posicao do lider na tela
ZUMBI_L = 24
ZUMBI_A = 34
LARG_FORMACAO = 5           # zumbis por coluna antes de recuar
MAX_ZUMBIS = 80

# --- Sprites da horda ---
ZUMBI_SPRITE_A = 46         # altura desenhada (o hitbox continua ZUMBI_A)
ZUMBI_FPS_ANIM = 15         # quadros por segundo do ciclo de corrida
QUADRO_SUBINDO = 3          # pernas recolhidas
QUADRO_CAINDO = 0           # pernas abertas, pronto pra pousar
SOMBRA_LINHA = 0.06         # quanto cada linha de tras escurece
ESCALA_LINHA = 0.05         # quanto cada linha de tras encolhe
RECUO_LINHA = 9             # quanto cada linha de tras sobe na tela

# --- Sprites dos humanos ---
HUMANO_SPRITE_A = 44        # altura desenhada (o hitbox continua HUMANO_A)
HUMANO_FPS_ANIM = 13        # ciclo de corrida
HUMANO_FPS_PASSEIO = 6      # antes do panico o humano so caminha

# --- Caixas de poder ---
CAIXA_SPRITE = 58           # tamanho desenhado do caixote
CAIXA_DISTANCIA = 5000      # px entre uma caixa e a proxima (100 m)
CAIXA_MARGEM = 90           # distancia minima da borda da plataforma
CAIXA_FOLGA = 130           # distancia minima de um obstaculo
CAIXA_FLUTUA = 6            # amplitude do sobe-e-desce
CAIXA_PRIMEIRA_X = 900      # a primeira caixa vem cedo, pra ensinar o poder

# --- Poderes ---
ICONE_HUD = 34              # tamanho do icone do poder no HUD
ICONE_LOJA = 44             # tamanho do icone de cada item da loja
MONSTRO_CHANCE = 0.4        # chance do mordido virar um monstro comprado na loja
CHANCE_ZUMBIS = 3           # com quantos zumbis a segunda chance devolve a horda
CHANCE_VOO = 3.5            # segundos de voo na volta, pra nao renascer num buraco
GIGANTE_ALCANCE = 20        # folga extra do hitbox enquanto gigante
DRAGAO_SUBIDA = -300.0      # px/s segurando o pulo
DRAGAO_DESCIDA = 180.0      # px/s soltando
DRAGAO_TETO = 110           # altura maxima do voo
DRAGAO_FPS_ASAS = 9
DRAGAO_ALTURA = (120, 190)  # altura do dragao: horda pequena -> horda cheia
GIGANTAO_ALTURA = (120, 200)    # altura do zumbi gigante: idem
BALAO_GRAVIDADE = 0.55      # multiplicador da gravidade
BALAO_PULO = 0.72           # pulo mais fraco: com a queda lenta ele ja sobe muito
BALAO_PULOS_EXTRA = 1       # pulos disponiveis no ar
BALAO_SPRITE_A = 34         # balao desenhado acima do zumbi
BALAO_FIO = 16              # comprimento do barbante
IMA_RAIO = 320.0            # de quao longe a moeda e puxada
IMA_VELOCIDADE = 8.0        # quao rapido ela chega
IMA_MULTIPLICADOR = 2       # moeda vale em dobro
IMA_SPRITE_A = 40           # ima que flutua em cima do lider
IMA_ONDAS = 3               # aneis de atracao saindo dele
FIM_ESPERA = 3.0            # segundos do placar final antes de voltar ao menu
FIM_TRAVA = 0.6             # nesse comeco o placar ignora tecla (pulo atrasado)

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
COR_BARRA_PODER = (250, 226, 120)
COR_FOGO = (250, 176, 60)
