"""O que fica guardado entre uma abertura do jogo e outra.

Um JSON so, `progresso.json`, na raiz do projeto: moedas no cofre, o que foi
comprado na loja, o recorde e as configuracoes (som, volume, tela cheia e nome
do jogador no placar da LAN, musica). Arquivo ausente ou estragado
vira progresso zerado, sem derrubar o jogo.
"""

import json
import os

CAMINHO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "progresso.json"
)

PADRAO = {"moedas": 0, "recorde": 0, "som": True, "itens": {},
          "volume": 80, "musica": True, "tela_cheia": False, "nome": "Jogador"}

dados = dict(PADRAO, itens={})


def carregar():
    try:
        with open(CAMINHO, encoding="utf-8") as arq:
            lido = json.load(arq)
    except (OSError, ValueError):
        return
    if not isinstance(lido, dict):
        return
    for chave, padrao in PADRAO.items():
        valor = lido.get(chave, padrao)
        if type(valor) is type(padrao):
            dados[chave] = valor
    dados["itens"] = {str(k): int(v) for k, v in dados["itens"].items()
                      if isinstance(v, int) and v > 0}
    dados["moedas"] = max(0, dados["moedas"])
    dados["volume"] = max(0, min(100, dados["volume"]))
    dados["nome"] = dados["nome"].strip()[:16] or PADRAO["nome"]


def zerar():
    """Apaga moedas, compras e recorde. Som, volume, tela e nome ficam."""
    dados["moedas"], dados["recorde"], dados["itens"] = 0, 0, {}
    salvar()


def salvar():
    try:
        with open(CAMINHO, "w", encoding="utf-8") as arq:
            json.dump(dados, arq, indent=2)
    except OSError:
        pass                # disco so de leitura: joga sem guardar


def nivel(item):
    """Quantas vezes o item foi comprado (ou quantos ha em estoque)."""
    return dados["itens"].get(item, 0)


def definir_nivel(item, valor):
    if valor > 0:
        dados["itens"][item] = valor
    else:
        dados["itens"].pop(item, None)
