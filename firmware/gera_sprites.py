#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desenha o clawd que anda sobre a barra e escreve os sprites no .ino.

Fonte unica: as poses nascem aqui, e daqui saem tanto o header em C do
firmware quanto o desenho de docs/tela/gera_svg.py (que importa este modulo).
No .ino os arrays vivem entre os marcadores >>> / <<< SPRITES GERADOS: o
script troca so aquele trecho, o resto do sketch fica intocado.
Mexeu na pose, rode:

    python firmware/gera_sprites.py

Duas camadas por quadro, nao uma:

    CORPO  a silhueta inteira, pintada na cor escura
    OLHOS  so o branco dos olhos, pintado por cima

A pupila e o buraco no branco — o corpo aparece por baixo. Assim dois
bitmaps de 1 bit dao tres cores sem tabela de paleta nenhuma.
"""

import pathlib

W, H = 32, 30          # caixa do sprite (32 = 4 bytes cheios por linha)
CHAO = H - 1           # linha onde o pe encosta


# ----------------------------------------------------------- primitivas ----

def vazio():
    return [[" "] * W for _ in range(H)]


def ret(g, x, y, w, h, ch="#"):
    for j in range(int(y), int(y + h)):
        for i in range(int(x), int(x + w)):
            if 0 <= i < W and 0 <= j < H:
                g[j][i] = ch


# --------------------------------------------------------- o claude mochi ---
# Corpo de bloco arredondado, olhos quadrados, quatro perninhas e dois
# toquinhos de braco. E so isso — o bicho da referencia nao tem pelo, nao tem
# pupila, nao tem boca. Tentar enfeitar em 24 px so suja a silhueta.
CORPO_X, CORPO_W = 3, 26      # corpo cols 3..28; sobram 3 px para os bracos
CORPO_Y, CORPO_H = 3, 20      # linhas 3..22 — proporcao ~1,3:1 da referencia

OLHO_X = (8, 19)              # coluna inicial de cada olho
OLHO_Y, OLHO_L = 8, 5         # linha e lado do quadrado

BRACO_Y, BRACO_H = 10, 5      # toquinhos laterais
BRACO_W = 3

# Perna curta: na referencia ela e ~35% da altura do corpo. Botei 9 px de
# perna contra 14 de corpo na primeira tentativa e virou aranha.
PERNA_X = (5, 11, 17, 23)     # coluna inicial de cada uma das quatro pernas
PERNA_W = 4
PERNA_TOPO = 21               # entra no corpo; o corpo cobre a emenda
PERNA_CURTA = 2               # quanto a perna erguida encolhe


def corpo(g, sobe=0):
    y = CORPO_Y - sobe
    ret(g, CORPO_X, y, CORPO_W, CORPO_H)
    # cantos arredondados: um pixel fora em cada quina
    for cx in (CORPO_X, CORPO_X + CORPO_W - 1):
        for cy in (y, y + CORPO_H - 1):
            g[cy][cx] = " "


def olhos(g, sobe=0):
    for x in OLHO_X:
        ret(g, x, OLHO_Y - sobe, OLHO_L, OLHO_L, "o")


def bracos(g, sobe=0, direito_erguido=False):
    y = BRACO_Y - sobe
    ret(g, CORPO_X - BRACO_W, y, BRACO_W, BRACO_H)          # esquerdo, sempre
    if direito_erguido:
        # Pose 3 da referencia. Precisa passar ACIMA do topo do corpo: colado
        # na lateral ele so engorda a silhueta e ninguem le como braco.
        ret(g, CORPO_X + CORPO_W - 1, 0, BRACO_W, y + BRACO_H)
    else:
        ret(g, CORPO_X + CORPO_W, y, BRACO_W, BRACO_H)


def pernas(g, curtas=(), sobe=0):
    """As quatro pernas. As de indice em `curtas` ficam erguidas do chao."""
    for i, x in enumerate(PERNA_X):
        fim = CHAO - (PERNA_CURTA if i in curtas else 0)
        topo = PERNA_TOPO - sobe
        ret(g, x, topo, PERNA_W, fim - topo + 1)


def monta(curtas=(), sobe=0, acena=False):
    g = vazio()
    pernas(g, curtas, sobe)          # atras
    corpo(g, sobe)                   # por cima, cobrindo a emenda
    bracos(g, sobe, acena)
    olhos(g, sobe)
    return g


# Caminhada de duas poses: alterna quais pernas estao no chao. Com quatro
# perninhas isso ja basta — nao precisa deslocar o corpo, o que exigiria
# apagar uma caixa maior a cada quadro.
def pose_anda(par_a):
    return monta(curtas=(1, 3) if par_a else (0, 2), sobe=0 if par_a else 1)


def pose_acena():
    return monta(curtas=(), sobe=0, acena=True)


POSES = [("ANDA_A", pose_anda(True)),
         ("ANDA_B", pose_anda(False)),
         ("ACENA", pose_acena())]


# --------------------------------------------------------------- saida -----

def bits(g, alvo):
    """1 bit por pixel, MSB primeiro, linhas alinhadas em byte (drawBitmap)."""
    linha_bytes = (W + 7) // 8
    saida = []
    for y in range(H):
        b = bytearray(linha_bytes)
        for x in range(W):
            if g[y][x] in alvo:
                b[x // 8] |= 0x80 >> (x % 8)
        saida.extend(b)
    return saida


def arr_c(nome, dados):
    linhas = [f"static const uint8_t {nome}[] PROGMEM = {{"]
    for i in range(0, len(dados), 12):
        linhas.append("  " + " ".join(f"0x{b:02X}," for b in dados[i:i+12]))
    linhas.append("};")
    return "\n".join(linhas)


ABRE = "// >>> SPRITES GERADOS"
FECHA = "// <<< SPRITES GERADOS"


def sprites_c():
    """Os arrays em C, sem os marcadores nem o cabecalho de comentario."""
    partes = [f"static const int16_t CLAWD_W = {W};",
              f"static const int16_t CLAWD_H = {H};",
              ""]
    for nome, g in POSES:
        partes.append(f"// ---- {nome} " + "-" * (56 - len(nome)))
        for l in g:
            partes.append("// " + "".join(l).replace(" ", "."))
        partes.append(arr_c(f"CLAWD_{nome}_CORPO", bits(g, "#o")))
        partes.append(arr_c(f"CLAWD_{nome}_OLHOS", bits(g, "o")))
        partes.append("")
    # tabelas para o firmware indexar por quadro
    corpos = ", ".join(f"CLAWD_{n}_CORPO" for n, _ in POSES)
    olhos_ = ", ".join(f"CLAWD_{n}_OLHOS" for n, _ in POSES)
    partes += [f"static const uint8_t *const CLAWD_CORPO[] = {{{corpos}}};",
               f"static const uint8_t *const CLAWD_OLHOS[] = {{{olhos_}}};",
               "static const uint8_t CLAWD_ANDA_A = 0, CLAWD_ANDA_B = 1, CLAWD_ACENA = 2;",
               ""]
    return "\n".join(partes).strip("\n")


def escreve_no_ino(ino):
    """Troca so o bloco entre os marcadores. Erra alto se eles sumirem."""
    texto = pathlib.Path(ino).read_text(encoding="utf-8")
    i, f = texto.find(ABRE), texto.find(FECHA)
    if i < 0 or f < i:
        raise SystemExit(f"marcadores {ABRE} / {FECHA} nao achados em {ino}")
    # o cabecalho de comentario logo apos ABRE fica; o resto e regerado
    corpo = texto.index("\n", i) + 1
    while texto[corpo:].startswith("//"):
        corpo = texto.index("\n", corpo) + 1
    pathlib.Path(ino).write_text(
        texto[:corpo] + sprites_c() + "\n" + texto[f:], encoding="utf-8")


if __name__ == "__main__":
    for nome, g in POSES:
        print(f"-- {nome} --")
        for y, l in enumerate(g):
            marca = " <- chao" if y == CHAO else ""
            print(f"{y:2} |" + "".join(l).replace(" ", ".") + "|" + marca)
        print()
    destino = pathlib.Path(__file__).parent / "claude_mochi" / "claude_mochi.ino"
    escreve_no_ino(destino)
    print(f"{destino} atualizado")
