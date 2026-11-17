"""Cenarios de fundo: tres camadas em paralaxe que trocam conforme a distancia.

O mundo e dividido em trechos de `cfg.TRECHO_CENARIO` px e cada trecho tem o
seu cenario. Na divisa entre dois trechos fica um tunel: a horda entra por um
cenario e sai no outro. A emenda dos dois fundos fica escondida atras da rocha
do tunel, entao a troca nao precisa de fundido nenhum.

Cada cenario traz tambem a paleta do chao, pra plataforma nao destoar do fundo.
"""

import pygame

from jogo import config as cfg
from jogo import recursos

# a ordem daqui e a ordem em que os cenarios aparecem na corrida; `nome` e o
# prefixo dos arquivos em assets/fundos (<nome>_ceu, <nome>_longe, <nome>_perto)
TEMAS = (
    {"nome": "cidade", "chao": cfg.COR_CHAO, "lado": cfg.COR_CHAO_LADO,
     "topo": cfg.COR_CHAO_TOPO, "abismo": cfg.COR_ABISMO},
    {"nome": "deserto", "chao": (116, 74, 76), "lado": (84, 50, 60),
     "topo": (222, 164, 96), "abismo": (30, 14, 26)},
    {"nome": "floresta", "chao": (38, 62, 62), "lado": (24, 42, 44),
     "topo": (98, 152, 92), "abismo": (5, 13, 16)},
    {"nome": "neve", "chao": (78, 100, 140), "lado": (54, 72, 108),
     "topo": (232, 242, 252), "abismo": (8, 16, 34)},
)

# piso de concreto dentro do tunel: a cor do chao troca nas duas bocas, onde
# o arco de pedra esconde o corte, e nao no meio do caminho
PALETA_TUNEL = {"chao": (52, 48, 60), "lado": (36, 33, 43),
                "topo": (104, 98, 114), "abismo": (10, 8, 14)}

COR_TUNEL_FUNDO = (26, 22, 34)      # usadas so se faltar a arte do tunel
COR_TUNEL_ROCHA = (58, 52, 70)


def tunel_perto(x):
    """Centro do tunel mais proximo de x, ou None antes do primeiro."""
    k = round(x / cfg.TRECHO_CENARIO)
    return k * cfg.TRECHO_CENARIO if k >= 1 else None


class Cenario:
    def __init__(self):
        # so entra na roda o cenario que tem arte no disco
        self.temas = [t for t in TEMAS if recursos.fundo(t["nome"]) is not None]

    def _tema_em(self, x):
        """Cenario do trecho em que o ponto x do mundo cai."""
        temas = self.temas or TEMAS[:1]
        return temas[int(max(0.0, x) // cfg.TRECHO_CENARIO) % len(temas)]

    def paleta_em(self, x):
        """Cores do chao no ponto x do mundo."""
        centro = tunel_perto(x)
        if centro is not None and abs(x - centro) < cfg.TUNEL_LARGURA / 2:
            return PALETA_TUNEL
        return self._tema_em(x)

    # -------------------------------------------------------------- fundo
    def desenhar(self, tela, camera_x):
        """Pinta o fundo. Devolve False se nao houver arte carregada."""
        if not self.temas:
            return False
        divisa = tunel_perto(camera_x + cfg.LARGURA / 2)
        corte = round(divisa - camera_x) if divisa is not None else -1
        if not 0 < corte < cfg.LARGURA:
            self._pintar(tela, self._tema_em(camera_x + cfg.LARGURA / 2), camera_x)
            return True
        # divisa na tela: cada lado com o seu cenario (o tunel cobre a emenda)
        antes = tela.get_clip()
        tela.set_clip(pygame.Rect(0, 0, corte, cfg.ALTURA))
        self._pintar(tela, self._tema_em(divisa - 1), camera_x)
        tela.set_clip(pygame.Rect(corte, 0, cfg.LARGURA - corte, cfg.ALTURA))
        self._pintar(tela, self._tema_em(divisa + 1), camera_x)
        tela.set_clip(antes)
        return True

    @staticmethod
    def _pintar(destino, tema, camera_x):
        ceu, *camadas = recursos.fundo(tema["nome"])
        destino.blit(ceu, (0, 0))
        for camada, fator in zip(camadas, cfg.FUNDO_PARALAXE):
            if camada is None:
                continue
            larg = camada.get_width()
            x = -int(camera_x * fator) % larg - larg     # sempre <= 0
            while x < cfg.LARGURA:
                if x + larg > 0:
                    destino.blit(camada, (x, 0))
                x += larg

    # -------------------------------------------------------------- tunel
    def desenhar_tunel(self, tela, camera_x, frente):
        """Uma das duas camadas do tunel que estiver na tela.

        O interior (`frente=False`) vai atras da horda; a rocha com o arco
        (`frente=True`) vai por cima dela.
        """
        centro = tunel_perto(camera_x + cfg.LARGURA / 2)
        if centro is None:
            return
        arte = recursos.tunel()
        if arte is not None:
            camada = arte[1 if frente else 0]
            x = round(centro - camera_x - camada.get_width() / 2)
            if -camada.get_width() < x < cfg.LARGURA:
                tela.blit(camada, (x, 0))
            return
        # reserva sem arte: um bloco de rocha com o vao escuro embaixo
        x = round(centro - camera_x - cfg.TUNEL_LARGURA / 2)
        if frente:
            pygame.draw.rect(tela, COR_TUNEL_ROCHA, (x, 0, cfg.TUNEL_LARGURA, cfg.TUNEL_TETO))
        else:
            pygame.draw.rect(tela, COR_TUNEL_FUNDO,
                             (x, 0, cfg.TUNEL_LARGURA, cfg.CHAO_Y))
