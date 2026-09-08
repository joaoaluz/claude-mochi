#!/usr/bin/env python3
"""Gera docs/esquema/esquema-mochi.svg — o mapa das ligacoes na protoboard.

As ligacoes sao as mesmas de docs/PROTOBOARD.md, e os numeros de GPIO saem dos
#define de firmware/claude_mochi/claude_mochi.ino. Mudou um pino? Ajuste a
tabela LIGACOES aqui e rode de novo:

    python3 docs/esquema/gera_svg.py
"""

# ------------------------------------------------------------ ligacoes -----
# (pino do display, pino do ESP, gpio, cor do fio, observacao)
# Fonte: docs/PROTOBOARD.md secao 2 + os #define do .ino
LIGACOES = [
    ("SCL", "D5",  "GPIO14", "#e8b93a", "SPI por hardware — pino fixo"),
    ("SDA", "D7",  "GPIO13", "#4a90d9", "SPI por hardware — pino fixo"),
    ("RES", "D2",  "GPIO4",  "#e8e4dc", "TFT_RST no .ino"),
    ("DC",  "D1",  "GPIO5",  "#4caf6d", "TFT_DC no .ino"),
    ("CS",  "D8",  "GPIO15", "#a97bd4", "so se o modulo tiver CS"),
    ("VCC", "3V3", "trilha +", "#d93b3b", "NUNCA 5 V / VIN"),
    ("BLK", "3V3", "trilha +", "#d97757", "backlight sempre aceso"),
    ("GND", "GND", "trilha −", "#8b857c", ""),
]

V_POS = "#d93b3b"   # trilha +
V_NEG = "#8b857c"   # trilha −

# ---------------------------------------------------------------- svg ------
BG, FG, DIM, ACC = "#14110f", "#f4f1ea", "#8b857c", "#d97757"
PANEL, EDGE = "#1c1815", "#3a342e"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
SANS = "ui-sans-serif, system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"

out = []
add = out.append

W, H = 1180, 1560
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

# ---------------------------------------------------------------- header ---
add(f'<text x="60" y="72" fill="{FG}" font-size="34" font-weight="700">'
    f'claude-mochi — ligacoes na protoboard</text>')
add(f'<text x="60" y="102" fill="{DIM}" font-size="15">'
    f'ESP8266 + ST7789 240×240 · 7 fios (8 com CS) · sem PCB, sem solda no '
    f'circuito · espelha docs/PROTOBOARD.md</text>')
add(f'<line x1="60" y1="124" x2="{W-60}" y2="124" stroke="#2b2722" stroke-width="1"/>')


def title(x, y, num, text, note):
    add(f'<text x="{x}" y="{y}" fill="{ACC}" font-family="{MONO}" font-size="13" '
        f'letter-spacing="2">{num}</text>')
    add(f'<text x="{x}" y="{y+26}" fill="{FG}" font-size="21" '
        f'font-weight="600">{text}</text>')
    add(f'<text x="{x}" y="{y+48}" fill="{DIM}" font-size="14">{note}</text>')


# --------------------------------------------------------- 1. o desenho ---
title(60, 168, "01", "Quem vai em quem",
      "os dois lados sao 3,3 V — nao entra resistor em lugar nenhum")

ESP_X, ESP_Y, ESP_W, ESP_H = 130, 248, 250, 372
DSP_X, DSP_Y, DSP_W, DSP_H = 790, 248, 260, 372
RAIL_POS_Y, RAIL_NEG_Y = 672, 704
RAIL_X0, RAIL_X1 = 130, 1050

# --- placa ESP ---
add(f'<rect x="{ESP_X}" y="{ESP_Y}" width="{ESP_W}" height="{ESP_H}" rx="10" '
    f'fill="{PANEL}" stroke="{EDGE}" stroke-width="2"/>')
add(f'<text x="{ESP_X+ESP_W/2}" y="{ESP_Y+34}" text-anchor="middle" fill="{FG}" '
    f'font-size="16" font-weight="600">ESP8266</text>')
add(f'<text x="{ESP_X+ESP_W/2}" y="{ESP_Y+56}" text-anchor="middle" fill="{DIM}" '
    f'font-size="12.5">NodeMCU ou Wemos D1 mini</text>')
add(f'<text x="{ESP_X+ESP_W/2}" y="{ESP_Y+78}" text-anchor="middle" fill="{DIM}" '
    f'font-family="{MONO}" font-size="12">espetado na protoboard</text>')
# conector USB, so pra dar orientacao
add(f'<rect x="{ESP_X+ESP_W/2-26}" y="{ESP_Y+ESP_H-34}" width="52" height="22" rx="4" '
    f'fill="#2a2521" stroke="{EDGE}" stroke-width="1.5"/>')
add(f'<text x="{ESP_X+ESP_W/2}" y="{ESP_Y+ESP_H-18}" text-anchor="middle" '
    f'fill="{DIM}" font-family="{MONO}" font-size="10">USB</text>')

# --- modulo do display ---
add(f'<rect x="{DSP_X}" y="{DSP_Y}" width="{DSP_W}" height="{DSP_H}" rx="10" '
    f'fill="{PANEL}" stroke="{EDGE}" stroke-width="2"/>')
add(f'<rect x="{DSP_X+70}" y="{DSP_Y+58}" width="170" height="170" rx="6" '
    f'fill="#000" stroke="{EDGE}" stroke-width="1.5"/>')
# rostinho, so pra lembrar que este e o lado que aparece
for cx in (DSP_X+70+56, DSP_X+70+114):
    add(f'<ellipse cx="{cx}" cy="{DSP_Y+58+74}" rx="21" ry="24" fill="#f4f1ea"/>')
    add(f'<ellipse cx="{cx}" cy="{DSP_Y+58+74}" rx="11" ry="13" fill="#2e8b57"/>')
add(f'<rect x="{DSP_X+70+24}" y="{DSP_Y+58+146}" width="122" height="7" rx="3" '
    f'fill="#2e8b57"/>')
add(f'<text x="{DSP_X+DSP_W/2+35}" y="{DSP_Y+34}" text-anchor="middle" fill="{FG}" '
    f'font-size="16" font-weight="600">ST7789 240×240</text>')
add(f'<text x="{DSP_X+DSP_W/2+35}" y="{DSP_Y+DSP_H-16}" text-anchor="middle" '
    f'fill="{ACC}" font-family="{MONO}" font-size="11.5">este vai dentro do mochi</text>')

# --- trilhas de alimentacao da protoboard ---
for y, cor, rot, txt in ((RAIL_POS_Y, V_POS, "+", "trilha + da protoboard  ·  3,3 V"),
                         (RAIL_NEG_Y, V_NEG, "−", "trilha − da protoboard  ·  GND")):
    add(f'<line x1="{RAIL_X0}" y1="{y}" x2="{RAIL_X1}" y2="{y}" stroke="{cor}" '
        f'stroke-width="3.5" stroke-linecap="round"/>')
    add(f'<text x="{RAIL_X0-14}" y="{y+5}" text-anchor="end" fill="{cor}" '
        f'font-family="{MONO}" font-size="16" font-weight="700">{rot}</text>')
    add(f'<text x="{RAIL_X1+12}" y="{y+5}" fill="{DIM}" font-family="{MONO}" '
        f'font-size="11.5">{txt}</text>')


def pino(x, y, nome, cor, *, lado):
    """Um pino: quadradinho colorido + nome. lado 'esq' = texto a esquerda."""
    add(f'<rect x="{x-6}" y="{y-6}" width="12" height="12" rx="2.5" fill="{cor}"/>')
    tx = x - 16 if lado == "esq" else x + 16
    anc = "end" if lado == "esq" else "start"
    add(f'<text x="{tx}" y="{y+5}" text-anchor="{anc}" fill="{FG}" '
        f'font-family="{MONO}" font-size="13.5">{nome}</text>')


def fio(x1, y1, x2, y2, cor, *, tracejado=False):
    """Fio jumper: curva suave de um pino ao outro."""
    dx = max(60, abs(x2 - x1) * 0.45)
    tr = ' stroke-dasharray="7 6"' if tracejado else ""
    add(f'<path d="M {x1} {y1} C {x1+dx} {y1}, {x2-dx} {y2}, {x2} {y2}" fill="none" '
        f'stroke="{cor}" stroke-width="3"{tr} stroke-linecap="round"/>')


# pinos de sinal: os 5 primeiros da tabela
sinais = LIGACOES[:5]
y0, passo = ESP_Y + 96, 34
for i, (dsp, esp, gpio, cor, _obs) in enumerate(sinais):
    ye = y0 + i * passo
    yd = ESP_Y + 66 + i * passo
    pino(ESP_X + ESP_W, ye, esp, cor, lado="esq")
    pino(DSP_X, yd, dsp, cor, lado="dir")
    fio(ESP_X + ESP_W + 6, ye, DSP_X - 6, yd, cor, tracejado=(dsp == "CS"))
    meio = (ESP_X + ESP_W + DSP_X) / 2
    add(f'<text x="{meio}" y="{(ye+yd)/2 - 8}" text-anchor="middle" fill="{DIM}" '
        f'font-family="{MONO}" font-size="11">{gpio}</text>')

# alimentacao: ESP -> trilhas, trilhas -> display
esp_3v3_y = y0 + 5 * passo + 14
esp_gnd_y = esp_3v3_y + passo
pino(ESP_X + ESP_W, esp_3v3_y, "3V3", V_POS, lado="esq")
pino(ESP_X + ESP_W, esp_gnd_y, "GND", V_NEG, lado="esq")
fio(ESP_X + ESP_W + 6, esp_3v3_y, ESP_X + 300, RAIL_POS_Y, V_POS)
fio(ESP_X + ESP_W + 6, esp_gnd_y, ESP_X + 340, RAIL_NEG_Y, V_NEG)

dsp_pw = [(d, c) for d, _e, _g, c, _o in LIGACOES[5:]]
yd_base = ESP_Y + 66 + 5 * passo + 14
for i, (dsp, cor) in enumerate(dsp_pw):
    yd = yd_base + i * passo
    pino(DSP_X, yd, dsp, cor, lado="dir")
    rail = RAIL_NEG_Y if dsp == "GND" else RAIL_POS_Y
    x_saida = DSP_X - 120 - i * 46
    add(f'<path d="M {x_saida} {rail} C {x_saida+70} {rail}, {DSP_X-80} {yd}, '
        f'{DSP_X-6} {yd}" fill="none" stroke="{cor}" stroke-width="3" '
        f'stroke-linecap="round"/>')
    add(f'<circle cx="{x_saida}" cy="{rail}" r="4.5" fill="{cor}"/>')

add(f'<text x="{ESP_X}" y="{RAIL_NEG_Y+46}" fill="{DIM}" font-size="13">'
    f'VCC e BLK saem os dois da trilha +. Sem CS, sao 7 fios.</text>')

# ------------------------------------------------------------ 2. tabela ---
title(60, 800, "02", "A tabela, fio por fio",
      "confira a linha VCC duas vezes antes de energizar")

TY = 906
add(f'<line x1="60" y1="{TY-22}" x2="{W-60}" y2="{TY-22}" stroke="#2b2722"/>')
for x, t in ((84, "DISPLAY"), (250, "ESP8266"), (400, "GPIO"), (560, "OBSERVACAO")):
    add(f'<text x="{x}" y="{TY-32}" fill="{DIM}" font-family="{MONO}" '
        f'font-size="11.5" letter-spacing="1.5">{t}</text>')

for i, (dsp, esp, gpio, cor, obs) in enumerate(LIGACOES):
    y = TY + i * 30
    if i % 2 == 0:
        add(f'<rect x="60" y="{y-19}" width="{W-120}" height="30" fill="#1a1714"/>')
    add(f'<rect x="64" y="{y-11}" width="10" height="14" rx="2" fill="{cor}"/>')
    add(f'<text x="84" y="{y}" fill="{FG}" font-family="{MONO}" font-size="14">{dsp}</text>')
    add(f'<text x="250" y="{y}" fill="{FG}" font-family="{MONO}" font-size="14">{esp}</text>')
    add(f'<text x="400" y="{y}" fill="{DIM}" font-family="{MONO}" font-size="13">{gpio}</text>')
    add(f'<text x="560" y="{y}" fill="{DIM}" font-size="13">{obs}</text>')

# ------------------------------------------------------------- 3. notas ---
NY = TY + len(LIGACOES) * 30 + 44
title(60, NY, "03", "Tres coisas que queimam ou enganam", "")

notas = [
    ("VCC so em 3V3", "5 V ou VIN queima o display. Os dois lados sao 3,3 V."),
    ("A ordem dos pinos varia",
     "Cada modulo ST7789 imprime os pinos numa ordem. Va pelo NOME na serigrafia, "
     "nunca pela posicao deste desenho."),
    ("Sem CS no seu modulo?",
     "Deixe o fio roxo de fora e troque no .ino: #define TFT_CS -1"),
    ("Fio curto",
     "O SPI roda a 40 MHz. Jumper longo vira listra na tela — se acontecer, "
     "baixe setSPISpeed para 20000000."),
]
y = NY + 44
for t, c in notas:
    add(f'<circle cx="68" cy="{y-5}" r="3.5" fill="{ACC}"/>')
    add(f'<text x="86" y="{y}" fill="{FG}" font-size="14.5" font-weight="600">{t}</text>')
    linhas, atual = [], ""
    for p in c.split():
        if len(atual) + len(p) + 1 > 96:
            linhas.append(atual)
            atual = p
        else:
            atual = f"{atual} {p}".strip()
    linhas.append(atual)
    for j, ln in enumerate(linhas):
        add(f'<text x="86" y="{y+21+j*19}" fill="{DIM}" font-size="13.5">{ln}</text>')
    y += 21 + len(linhas) * 19 + 14

add(f'<text x="60" y="{H-30}" fill="#5c564e" font-family="{MONO}" font-size="11">'
    f'gerado por docs/esquema/gera_svg.py — nao edite o SVG a mao</text>')
add('</svg>')

import pathlib
destino = pathlib.Path(__file__).with_name("esquema-mochi.svg")
destino.write_text("\n".join(out), encoding="utf-8")
print(f"{destino} — {len(out)} elementos")
