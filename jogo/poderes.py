"""Catalogo dos poderes que saem das caixas.

Cada poder e so um identificador e uma ficha: quem aplica o efeito e o loop
principal (`jogo.py`), porque todos mexem na horda inteira, nao num zumbi so.
"""

GIGANTE = "gigante"
DRAGAO = "dragao"
BALAO = "balao"
IMA = "ima"

TODOS = (GIGANTE, DRAGAO, BALAO, IMA)

FICHA = {
    GIGANTE: {
        "nome": "GIGANTE",
        "dica": "a horda atropela os carros",
        "duracao": 9.0,
        "cor": (120, 196, 96),
    },
    DRAGAO: {
        "nome": "DRAGAO",
        "dica": "segure pra subir - voa por cima de tudo",
        "duracao": 7.5,
        "cor": (96, 184, 104),
    },
    BALAO: {
        "nome": "BALAO",
        "dica": "pulo duplo e queda lenta",
        "duracao": 9.0,
        "cor": (228, 96, 104),
    },
    IMA: {
        "nome": "IMA",
        "dica": "puxa as moedas e elas valem em dobro",
        "duracao": 11.0,
        "cor": (232, 96, 96),
    },
}


def duracao(nome):
    return FICHA[nome]["duracao"]


def cor(nome):
    return FICHA[nome]["cor"]


def nome(chave):
    return FICHA[chave]["nome"]


def dica(chave):
    return FICHA[chave]["dica"]
