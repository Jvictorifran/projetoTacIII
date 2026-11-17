# Zumbi Tsunami 2D

Projeto de Topicos Avancados em Computacao 3 - runner infinito em pygame-ce
inspirado no Zombie Tsunami.

## Como rodar

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python main.py
```

## Controles

| Tecla | Acao |
|-------|------|
| `ESPACO` / `W` / `seta cima` / clique | pular (a horda inteira pula junto) |
| soltar a tecla cedo | pulo mais baixo |
| `M` | liga/desliga os efeitos sonoros |
| `ESC` | durante a partida volta pra tela inicial; nela, sai do jogo |

Na tela inicial: setas (ou o mouse) escolhem entre **Jogar**, **Loja**,
**Efeitos sonoros** e **Sair**; `ENTER`, `ESPACO` ou clique confirmam. Na
loja e igual, e `ESC` volta.

Quando a horda acaba, o placar final fica 3 s na tela (`FIM_ESPERA`) e o jogo
volta sozinho pra tela inicial, que mostra o resultado da ultima partida.
Qualquer tecla de pulo adianta a volta.

## Mecanicas implementadas

- **Horda**: comeca com 1 zumbi e todos pulam juntos; a formacao se aperta
  conforme cresce, ate 80 zumbis.
- **Sprites animados**: a horda comeca com um zumbi "de nascenca" e cresce
  com a versao zumbi (esverdeada) de cada pessoa mordida. Ciclo de corrida de
  8 quadros e poses fixas de subida e queda no ar.
- **Contagio**: encostar num humano converte ele em zumbi (+1 na horda). Sao
  8 pessoas sorteadas: garoto, garota, exploradores, ninjas, cavaleiro e ate
  o Papai Noel.
- **Caixas de poder**: uma a cada 100 m (`CAIXA_DISTANCIA`), a primeira logo
  no comeco. Cada uma mostra na tampa o icone do poder que carrega. Encostar
  ativa na hora (veja abaixo).
- **Cenarios e tuneis**: a cada 250 m (`FUNDO_TROCA_M`) ha um tunel; a horda
  entra por um cenario e sai no seguinte - cidade, deserto, floresta e neve,
  em roda. A cor do chao acompanha o cenario. O trecho do tunel e reto, sem
  buraco nem carro, com uma fileira de moedas, e o teto dele limita o voo.
- **Obstaculos**: carros com 1 a 4 de vida; cada zumbi que bate morre e tira
  1 de vida do carro. Sem zumbis = fim de jogo.
- **Buracos e plataformas**: cenario gerado proceduralmente em 3 alturas, com
  buracos dimensionados pelo alcance do pulo na velocidade atual. O buraco e
  um vao de verdade: o fundo aparece por ele, so com uma sombra leve
  (`BURACO_SOMBRA`). Quem cai nele da de cara na parede da plataforma
  seguinte e escorrega por ela, em vez de atravessar o chao; quem chega ate
  24 px abaixo da beirada (`FOLGA_BEIRADA`) ainda sobe nela.
- **Tela inicial**: jogar, loja, ligar/desligar os efeitos sonoros e sair.
- **Loja**: as moedas de cada partida vao pro cofre e compram melhorias
  (veja abaixo). Cofre, compras, recorde e opcao de som ficam em
  `progresso.json` (fora do git).
- **Efeitos sonoros**: pulo, moeda, mordida (humano convertido), batida no
  carro, baque na parede do buraco, explosao, poder e fim de jogo.
- **Humanos**: passeiam devagar e so entram em panico quando a horda chega
  perto; fogem correndo e tentam pular os buracos.
- **Moedas**: espalhadas nas plataformas e em arcos por cima dos buracos.
- **Dificuldade**: a velocidade sobe com o tempo (330 -> 700 px/s) e as
  plataformas escalam junto.
- **Pulo com sensacao boa**: coyote time, buffer de entrada e pulo variavel.
- **Pontuacao**: metros + moedas x5, com recorde da sessao.

## Loja

| Item | Preco | O que faz |
|------|-------|-----------|
| **Horda inicial** | 100 / 250 / 500 / 900 | +1 zumbi no comeco da partida por nivel |
| **Poder duradouro** | 150 / 350 / 700 | +15% de duracao em todos os poderes por nivel |
| **Segunda chance** | 120 cada (ate 3 guardadas) | perdeu a horda? ela volta voando com 3 zumbis. Gasta 1 por partida |
| **Cabeca de abobora** | 200 | libera o monstro pra horda |
| **Dinossauro** | 350 | idem |
| **Robo** | 500 | idem |

Com monstros liberados, cada mordido tem 40% de chance (`MONSTRO_CHANCE`) de
virar um deles em vez da versao zumbi de si mesmo. O catalogo fica em `ITENS`,
em `jogo/loja.py`; pra zerar o progresso, apague `progresso.json`.

## Poderes

Cada caixa carrega um dos quatro poderes. Pegar uma caixa com outro poder
rodando troca na hora. O HUD mostra o icone e uma barra do tempo que falta,
que pisca no fim.

| Poder | Duracao | O que faz |
|-------|---------|-----------|
| **Gigante** | 9 s | a horda vira um zumbi so, enorme: atropela os carros em vez de morrer neles e alcanca humanos de mais longe |
| **Dragao** | 7.5 s | a horda vira um dragao e voa: sem gravidade, segurar o pulo sobe e soltar desce. Passa por cima de buracos e queima carros |
| **Balao** | 9 s | cada zumbi ganha um balao colorido: gravidade em 55% e um pulo extra no ar - feito pra varrer os arcos de moedas |
| **Ima** | 11 s | um ima flutua sobre o lider: moedas num raio de 320 px perseguem ele e valem em dobro |

No gigante e no dragao a transformacao e so no desenho: por baixo, cada zumbi
continua existindo, com o seu hitbox, e pode se perder sozinho. O bicho cresce
com o tamanho da horda (`GIGANTAO_ALTURA`, `DRAGAO_ALTURA`).

O voo do dragao nunca termina em cima de um buraco: quando o tempo zera a
horda desce e so deixa de ser dragao depois que tem chao embaixo dos pes. E ha um
teto (`cfg.TETO`) pra horda nenhuma sumir pela parte de cima da tela.

## Estrutura

```
main.py              ponto de entrada
jogo/config.py       constantes de fisica, cores, sprites e balanceamento
jogo/poderes.py      catalogo dos poderes (nome, duracao, cor, dica)
jogo/recursos.py     carga das folhas de sprite (fatia, corta, escala, cacheia)
jogo/sons.py         carga e toque dos efeitos sonoros (liga/desliga)
jogo/loja.py         catalogo, regras de compra e tela da loja
jogo/progresso.py    moedas, compras, recorde e som guardados em progresso.json
jogo/entidades.py    Corpo, Box, Zumbi, Humano, Obstaculo, Moeda
jogo/cenario.py      fundos em paralaxe, tunel de troca e paleta do chao
jogo/mundo.py        geracao procedural das plataformas, obstaculos e itens
jogo/jogo.py         loop principal, estados, poderes, colisoes e HUD
ferramentas/         importador dos sprites, geradores dos fundos (SVG), da
                     caixa/baloes/ima (PNG) e dos efeitos sonoros (WAV)
CREDITOS.md          de onde vem cada sprite e a licenca de cada um
assets/image/        folhas de sprite e icones
assets/fundos/       fundos em SVG, tres camadas por cenario
```

## Sprites

Os personagens vem de pacotes prontos, todos de uso livre - a lista e as
licencas estao em [CREDITOS.md](CREDITOS.md). Em `assets/image/`:

| Arquivo | O que e |
|---------|---------|
| `zombie_<nome>.png` | zumbi de nascenca, ou a versao zumbi do `human_<nome>` |
| `human_<nome>.png` | pessoa da rua |
| `monstro_<nome>.png` | monstro que a loja libera pra horda |
| `poder_<nome>.png`, `loja_<nome>.png` | icones dos poderes e da loja |
| `dragao.png` | 4 quadros do dragao do poder |
| `baloes.png` | um balao de cada cor |
| `caixa.png`, `ima.png` | imagens avulsas |

Cada folha de personagem e uma tira de quadros quadrados (8 de 160 px), todos
virados pra direita (a horda so corre pra frente). Qualquer quantidade de
quadros serve. Pra por um personagem novo basta salvar a folha com o prefixo
certo: um `human_x.png` com um `zombie_x.png` de mesmo nome ja vira par.

`jogo/recursos.py` faz o preparo uma vez so, na abertura da janela:

1. fatia a folha em quadros quadrados;
2. corta o vazio usando **a uniao** das caixas dos quadros — um corte por
   quadro mudaria a ancora e faria a animacao tremer;
3. escala pra `ZUMBI_SPRITE_A` e gera uma copia por linha da formacao, menor
   (`ESCALA_LINHA`) e mais escura (`SOMBRA_LINHA`) quanto mais atras.

Como as 5 linhas da formacao ja saem prontas do cache, desenhar 80 zumbis custa so 80
blits (~3 ms por quadro). O hitbox continua sendo `ZUMBI_L x ZUMBI_A`: o
sprite e maior que ele de proposito, entao mexer na escala nao mexe no
balanceamento. O mesmo vale pros humanos. Sem a pasta `assets/image`, o jogo
volta sozinho pras formas geometricas.

### Importando os personagens

Os pacotes trazem cada animacao como PNG soltos. O importador junta os
quadros de corrida numa folha, e gera a versao zumbi de cada pessoa (menos
cor e um banho de verde, em `zumbificar`):

```bash
./venv/bin/python ferramentas/importar_sprites.py /pasta/com/os/pacotes
```

A pasta deve ter cada zip do GameArt2D descompactado numa subpasta com o nome
do zip (a tabela `PACOTES`, no script, diz qual pasta vira qual personagem).
Sem o argumento, so os icones sao refeitos, a partir dos SVG em
`ferramentas/icones/`.

### Caixa, baloes e ima

Desenhados por codigo (vetorial, numa tela 4x maior e reduzida no fim):

```bash
./venv/bin/python ferramentas/gerar_sprites.py
```

## Fundos

Cada cenario sao tres arquivos em `assets/fundos/`:

| Arquivo | Tamanho | Papel |
|---------|---------|-------|
| `<nome>_ceu.svg` | 960x540 | ceu, opaco e parado |
| `<nome>_longe.svg` | 1920x540 | camada distante, acompanha 10% da camera |
| `<nome>_perto.svg` | 1920x540 | camada proxima, acompanha 35% da camera |

As duas camadas que rolam se repetem na horizontal, entao a borda esquerda
casa com a direita. O pygame rasteriza o SVG uma vez so, na abertura do jogo.

O tunel sao mais dois arquivos de 800x540: `tunel_fundo.svg` (o interior,
desenhado atras da horda) e `tunel_frente.svg` (a rocha e o arco de pedra,
por cima dela). Na divisa, cada lado da tela e pintado com o seu cenario e a
rocha do tunel cobre a emenda - por isso a troca nao precisa de fundido.

Os SVG sao escritos por codigo; pra mudar a arte, edite e rode de novo:

```bash
./venv/bin/python ferramentas/gerar_fundos.py
```

Pra usar uma imagem pronta (SVG ou PNG), salve em `assets/fundos/` com o mesmo
padrao de nome e acrescente o cenario em `TEMAS`, em `jogo/cenario.py`, junto
com as cores do chao. So o `_ceu` e obrigatorio; qualquer altura serve, a
imagem e ajustada pra 540 px. A ordem de `TEMAS` e a ordem em que os cenarios
aparecem. Sem a pasta `assets/fundos`, o jogo volta pro fundo de formas.

## Sons

Os efeitos ficam em `assets/sons/*.wav` e sao sintetizados por codigo, so com
a biblioteca padrao do Python (ondas simples + ruido + envelope, mono, 16
bits, 22050 Hz):

```bash
./venv/bin/python ferramentas/gerar_sons.py
```

Cada som e uma funcao em `SONS`, dentro do script. Pra usar um som pronto,
basta trocar o WAV de mesmo nome. Volumes e o intervalo minimo entre dois
toques do mesmo efeito ficam em `jogo/sons.py`. Sem placa de som ou sem a
pasta `assets/sons`, o jogo roda mudo.

## Regras de geracao (balanceamento)

O alcance do pulo e `velocidade * tempo_no_ar`. A partir dele:

- largura da plataforma: 1.6 a 3.0 x alcance
- buraco subindo de nivel: 0.10 a 0.22 x alcance
- buraco descendo: 0.25 a 0.45 x alcance
- buraco no mesmo nivel: 0.30 a 0.55 x alcance
- obstaculos so entram a partir de 2600 px (comeco seguro), longe da borda de
  pouso (0.85 x alcance) e da borda de saida (1.15 x alcance)
- caixas numa grade fixa: a primeira em 900 px e depois uma a cada 5000 px.
  Se o ponto cai num buraco ou perto de um carro, a caixa anda ate o primeiro
  lugar livre (a 90 px da borda e 130 px do carro), sem deslocar as seguintes

## Proximos passos

- sprites de carros e moedas (ainda desenhados com formas)
- trilha sonora
- mais monstros na loja (lobisomem, vampiro): falta achar arte livre no
  mesmo traco
- predios pra escalar
- tela de melhores pontuacoes
