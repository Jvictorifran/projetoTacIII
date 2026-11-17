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
| `R` | reiniciar apos morrer |
| `ESC` | sair |

## Mecanicas implementadas

- **Horda**: comeca com 1 zumbi e todos pulam juntos; a formacao se aperta
  conforme cresce, ate 80 zumbis.
- **Sprites animados**: 5 tipos de zumbi sorteados por entidade (garoto,
  policial, mumia, frankenstein, garota), com ciclo de corrida de 5 quadros e
  poses fixas de subida e queda no ar.
- **Contagio**: encostar num humano converte ele em zumbi (+1 na horda). Os
  humanos tem 4 aparencias sorteadas, no mesmo traco dos zumbis: sao as
  mesmas folhas com pele de gente, pupila e uma peca de roupa trocada.
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
  buracos dimensionados pelo alcance do pulo na velocidade atual.
- **Humanos**: passeiam devagar e so entram em panico quando a horda chega
  perto; fogem correndo e tentam pular os buracos.
- **Moedas**: espalhadas nas plataformas e em arcos por cima dos buracos.
- **Dificuldade**: a velocidade sobe com o tempo (330 -> 700 px/s) e as
  plataformas escalam junto.
- **Pulo com sensacao boa**: coyote time, buffer de entrada e pulo variavel.
- **Pontuacao**: metros + moedas x5, com recorde da sessao.

## Poderes

Cada caixa carrega um dos quatro poderes. Pegar uma caixa com outro poder
rodando troca na hora. O HUD mostra o icone e uma barra do tempo que falta,
que pisca no fim.

| Poder | Duracao | O que faz |
|-------|---------|-----------|
| **Gigante** | 9 s | os zumbis crescem 1.75x, atropelam os carros em vez de morrer neles e alcancam humanos de mais longe |
| **Dragao** | 7.5 s | a horda voa: sem gravidade, segurar o pulo sobe e soltar desce. Passa por cima de buracos e queima carros |
| **Balao** | 9 s | gravidade em 55% e um pulo extra no ar - feito pra varrer os arcos de moedas |
| **Ima** | 11 s | moedas num raio de 320 px perseguem o lider e valem em dobro |

O voo do dragao nunca termina em cima de um buraco: quando o tempo zera a
horda desce e so perde as asas depois que tem chao embaixo dos pes. E ha um
teto (`cfg.TETO`) pra horda nenhuma sumir pela parte de cima da tela.

## Estrutura

```
main.py              ponto de entrada
jogo/config.py       constantes de fisica, cores, sprites e balanceamento
jogo/poderes.py      catalogo dos poderes (nome, duracao, cor, dica)
jogo/recursos.py     carga das folhas de sprite (fatia, corta, escala, cacheia)
jogo/entidades.py    Corpo, Box, Zumbi, Humano, Obstaculo, Moeda
jogo/cenario.py      fundos em paralaxe, tunel de troca e paleta do chao
jogo/mundo.py        geracao procedural das plataformas, obstaculos e itens
jogo/jogo.py         loop principal, estados, poderes, colisoes e HUD
ferramentas/         geradores dos humanos, dos icones (PNG) e dos fundos (SVG)
assets/image/        folhas de sprite e icones
assets/fundos/       fundos em SVG, tres camadas por cenario
```

## Sprites

`assets/image/zombie*.png` e `human*.png` sao folhas de 1280x256: 5 quadros de
corrida lado a lado, todos virados pra direita (a horda so corre pra frente).
`poder_*.png`, `caixa.png` e `asas.png` sao imagens avulsas.

`jogo/recursos.py` faz o preparo uma vez so, na abertura da janela:

1. fatia a folha em quadros quadrados;
2. corta o vazio usando **a uniao** das caixas dos 5 quadros — um corte por
   quadro mudaria a ancora e faria a animacao tremer;
3. escala pra `ZUMBI_SPRITE_A` e gera uma copia por linha da formacao, menor
   (`ESCALA_LINHA`) e mais escura (`SOMBRA_LINHA`) quanto mais atras.

Como as 5 linhas ja saem prontas do cache, desenhar 80 zumbis custa so 80
blits (~3 ms por quadro). O hitbox continua sendo `ZUMBI_L x ZUMBI_A`: o
sprite e maior que ele de proposito, entao mexer na escala nao mexe no
balanceamento. O mesmo vale pros humanos. Sem a pasta `assets/image`, o jogo
volta sozinho pras formas geometricas.

As asas do dragao sao **um par so** desenhado atras da horda inteira, nao uma
por zumbi: com 80 deles o espaco entre um e outro e menor que a propria asa e
o resultado virava uma mancha roxa.

### Gerando os humanos

As folhas `human*.png` saem das folhas de zumbi: a pele esverdeada vira pele
de gente (mantendo luz e sombra do desenho), os olhos brancos ganham pupila e
uma peca de roupa ou o cabelo troca de cor. Tons de pele e trocas ficam em
`HUMANOS`, dentro do script:

```bash
./venv/bin/python ferramentas/gerar_humanos.py
```

### Gerando os icones de poder

Os icones de poder, a caixa e as asas sao desenhados por codigo (vetorial,
numa tela 4x maior e reduzida no fim):

```bash
./venv/bin/python ferramentas/gerar_sprites.py
```

Da pra mexer nas funcoes `_icone_*` e rodar de novo: os PNG em `assets/image/`
sao regravados.

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
- efeitos sonoros e trilha
- predios pra escalar
- salvar recorde em arquivo e tela de melhores pontuacoes
