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
- **Contagio**: encostar num humano converte ele em zumbi (+1 na horda).
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

## Estrutura

```
main.py              ponto de entrada
jogo/config.py       constantes de fisica, cores e balanceamento
jogo/entidades.py    Corpo, Zumbi, Humano, Obstaculo, Moeda
jogo/mundo.py        geracao procedural do cenario e desenho do fundo
jogo/jogo.py         loop principal, estados, colisoes e HUD
```

## Regras de geracao (balanceamento)

O alcance do pulo e `velocidade * tempo_no_ar`. A partir dele:

- largura da plataforma: 1.6 a 3.0 x alcance
- buraco subindo de nivel: 0.10 a 0.22 x alcance
- buraco descendo: 0.25 a 0.45 x alcance
- buraco no mesmo nivel: 0.30 a 0.55 x alcance
- obstaculos so entram a partir de 2600 px (comeco seguro), longe da borda de
  pouso (0.85 x alcance) e da borda de saida (1.15 x alcance)

## Proximos passos

- sprites e sons no lugar das formas geometricas
- power-ups (zumbi gigante, dragao, balao) e predios pra escalar
- salvar recorde em arquivo e tela de melhores pontuacoes
