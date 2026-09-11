#!/usr/bin/env python3
import pathlib
import sys

"""Gera docs/tela/tela-mochi.svg — o mapa do que aparece no display.

As constantes e a matematica sao copiadas de
firmware/claude_mochi/claude_mochi.ino, inclusive o truncamento inteiro, para
o desenho bater pixel a pixel com o que o ST7789 mostra. Mudou o firmware?
Ajuste o bloco abaixo (ele espelha o .ino um por um) e rode de novo:

    python3 docs/tela/gera_svg.py
"""

# O clawd vem do MESMO desenho que o firmware usa. Importar em vez de copiar
# e o unico jeito de nao ter duas versoes do bicho divergindo em silencio.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "firmware"))
import gera_sprites as clawd            # noqa: E402

# ----------------------------------------------------------- firmware ------
SCR      = 240
EYE_CX_L = 72
EYE_CX_R = 168
EYE_CY   = 104
EYE_RX   = 36
EYE_RY   = 42
BAR_X    = 34
BAR_Y    = 206
BAR_H    = 10
BAR_W    = SCR - 2 * BAR_X

# o clawd que anda sobre a barra enquanto state=busy (poses em gera_sprites.py)
WK_W    = clawd.W
WK_H    = clawd.H
WK_FEET = BAR_Y - 1
WK_X0   = BAR_X
WK_X1   = BAR_X + BAR_W - WK_W
WK_STEP = 4

C_FACE  = 0xFB26
C_EYE   = 0x18E3
C_OK    = 0x2E88
C_WARN  = 0xFCA0
C_HOT   = 0xE0A3
C_SHINE = 0xFFFF
C_TRACK = 0x8A44
C_SLEEP = 0xD69A


def rgb(c565: int) -> str:
    """RGB565 -> #rrggbb, do mesmo jeito que o painel expande."""
    r, g, b = c565 >> 11, (c565 >> 5) & 0x3F, c565 & 0x1F
    r = (r << 3) | (r >> 2)
    g = (g << 2) | (g >> 4)
    b = (b << 3) | (b >> 2)
    return f"#{r:02x}{g:02x}{b:02x}"


def mix(a: int, b: int, t: float) -> int:
    """mix() do firmware — inclusive o (int) que trunca em direcao a zero."""
    t = max(0.0, min(1.0, t))
    ar, ag, ab = a >> 11, (a >> 5) & 0x3F, a & 0x1F
    br, bg, bb = b >> 11, (b >> 5) & 0x3F, b & 0x1F
    r = ar + int((br - ar) * t)
    g = ag + int((bg - ag) * t)
    bl = ab + int((bb - ab) * t)
    return (r << 11) | (g << 5) | bl


def level_color(pct: int) -> int:
    if pct <= 60:
        return mix(C_OK, C_WARN, pct / 60.0)
    return mix(C_WARN, C_HOT, (pct - 60) / 40.0)


def eye_h(ctx: int) -> int:
    """Altura do olho: 0% = arregalado, 100% = quase fechado."""
    return int(EYE_RY * (1.0 - 0.72 * (ctx / 100.0)))


# --------------------------------------------------------------- svg -------
FACE, EYE, TRACK, SLEEP = rgb(C_FACE), rgb(C_EYE), rgb(C_TRACK), rgb(C_SLEEP)
BG, FG, DIM, ACC = "#14110f", "#f4f1ea", "#8b857c", "#d97757"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
SANS = "ui-sans-serif, system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"

out = []
add = out.append


def eye(cx, cy, ry, iris, *, crossed=False, asleep=False, dx=0, dy=0):
    """Um olho, seguindo drawEye() do firmware."""
    cx, cy = cx + dx, cy + dy
    if asleep:
        add(f'<rect x="{cx-EYE_RX+4}" y="{cy-2}" width="{(EYE_RX-4)*2}" '
            f'height="5" rx="2" fill="{SLEEP}"/>')
        return
    if crossed:
        r = 28
        for x1, y1, x2, y2 in ((cx-r, cy-r, cx+r, cy+r), (cx-r, cy+r, cx+r, cy-r)):
            add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{EYE}" '
                f'stroke-width="5" stroke-linecap="round"/>')
        return
    if ry < 3:
        add(f'<rect x="{cx-EYE_RX}" y="{cy-2}" width="{EYE_RX*2}" height="5" '
            f'rx="2" fill="{EYE}"/>')
        return
    add(f'<ellipse cx="{cx}" cy="{cy}" rx="{EYE_RX}" ry="{ry}" fill="{EYE}"/>')
    iry = int(ry * 0.55)
    if iry >= 2:
        add(f'<ellipse cx="{cx}" cy="{cy}" rx="{int(EYE_RX*0.55)}" ry="{iry}" '
            f'fill="{rgb(iris)}"/>')
    if ry > EYE_RY * 0.45:
        add(f'<circle cx="{cx-EYE_RX//3}" cy="{cy-ry//2}" r="5" fill="#ffffff"/>')


def walker(x, pose=0, sobe=0):
    """Uma pose do clawd, pixel a pixel, como o drawBitmap() do firmware faz.

    Emite corridas horizontais em vez de um <rect> por pixel — mesma imagem,
    um decimo do arquivo.
    """
    g = clawd.POSES[pose][1]
    y0 = WK_FEET - WK_H + 1 - sobe
    for j, linha in enumerate(g):
        i = 0
        while i < WK_W:
            ch = linha[i]
            if ch == " ":
                i += 1
                continue
            k = i
            while k < WK_W and linha[k] == ch:
                k += 1
            cor = "#ffffff" if ch == "o" else EYE
            add(f'<rect x="{x+i}" y="{y0+j}" width="{k-i}" height="1" fill="{cor}"/>')
            i = k


def brow(cx, angle_up):
    """Sobrancelha reta — drawLine grosso, barato no GFX."""
    dy = 9 if angle_up else -9
    add(f'<line x1="{cx-24}" y1="{EYE_CY-46-dy}" x2="{cx+24}" y2="{EYE_CY-46+dy}" '
        f'stroke="{EYE}" stroke-width="6" stroke-linecap="round"/>')


def happy_eye(cx):
    """Olho feliz ^ ^ : duas retas."""
    add(f'<path d="M {cx-26} {EYE_CY+8} L {cx} {EYE_CY-14} L {cx+26} {EYE_CY+8}" '
        f'fill="none" stroke="{EYE}" stroke-width="7" stroke-linecap="round" '
        f'stroke-linejoin="round"/>')


def bar(pct):
    add(f'<rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" height="{BAR_H}" '
        f'rx="{BAR_H//2}" fill="{TRACK}"/>')
    w = BAR_W * max(0, min(100, pct)) // 100
    if w >= BAR_H:
        add(f'<rect x="{BAR_X}" y="{BAR_Y}" width="{w}" height="{BAR_H}" '
            f'rx="{BAR_H//2}" fill="{rgb(level_color(pct))}"/>')
    elif w > 0:
        add(f'<rect x="{BAR_X}" y="{BAR_Y}" width="{w}" height="{BAR_H}" '
            f'fill="{rgb(level_color(pct))}"/>')


def screen(x, y, scale, body, caption, sub, *, accent=False):
    """Uma tela 240x240 desenhada em escala, com legenda embaixo."""
    s = SCR * scale
    add(f'<g transform="translate({x},{y}) scale({scale})">')
    add(f'<rect x="-6" y="-6" width="{SCR+12}" height="{SCR+12}" rx="14" '
        f'fill="#000" stroke="{ACC if accent else "#3a342e"}" stroke-width="2"/>')
    add(f'<rect width="{SCR}" height="{SCR}" fill="{FACE}"/>')
    body()
    add('</g>')
    add(f'<text x="{x + s/2}" y="{y + s + 30}" text-anchor="middle" fill="{FG}" '
        f'font-family="{SANS}" font-size="15" font-weight="600">{caption}</text>')
    for i, line in enumerate(sub):
        add(f'<text x="{x + s/2}" y="{y + s + 50 + i*17}" text-anchor="middle" '
            f'fill="{DIM}" font-family="{MONO}" font-size="12.5">{line}</text>')


def title(x, y, num, text, note):
    add(f'<text x="{x}" y="{y}" fill="{ACC}" font-family="{MONO}" font-size="13" '
        f'letter-spacing="2">{num}</text>')
    add(f'<text x="{x}" y="{y+26}" fill="{FG}" font-family="{SANS}" font-size="21" '
        f'font-weight="600">{text}</text>')
    add(f'<text x="{x}" y="{y+48}" fill="{DIM}" font-family="{SANS}" '
        f'font-size="14">{note}</text>')


def wrap(text, width):
    """Quebra em palavras, sem cortar no meio."""
    linhas, atual = [], ""
    for p in text.split():
        if len(atual) + len(p) + 1 > width:
            linhas.append(atual)
            atual = p
        else:
            atual = f"{atual} {p}".strip()
    if atual:
        linhas.append(atual)
    return linhas


def para(x, y, titulo, corpo, width=54, size=13.5):
    add(f'<text x="{x}" y="{y}" fill="{FG}" font-size="14.5" font-weight="600">'
        f'{titulo}</text>')
    for i, ln in enumerate(wrap(corpo, width)):
        add(f'<text x="{x}" y="{y+22+i*19}" fill="{DIM}" font-size="{size}">{ln}</text>')
    return y + 22 + len(wrap(corpo, width)) * 19


W, H = 1180, 2135
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

# ---------------------------------------------------------------- header ---
add(f'<text x="60" y="72" fill="{FG}" font-size="34" font-weight="700">'
    f'claude-mochi — o que aparece na tela</text>')
add(f'<text x="60" y="102" fill="{DIM}" font-size="15">'
    f'ST7789 240×240 · desenhos em escala 1:1 com as constantes de '
    f'firmware/claude_mochi/claude_mochi.ino</text>')
add(f'<line x1="60" y1="124" x2="{W-60}" y2="124" stroke="#2b2722" stroke-width="1"/>')

# ------------------------------------------------- 1. rampa de contexto ---
title(60, 168, "01", "Consumo → abertura do olho",
      "openTarget = 1 − 0,72 × valor/100 · a íris vai de verde a vermelho · olho e barra escolhem a métrica em OLHOS_METRICA / BARRA_METRICA")

SC, GAP, TOP = 0.80, 24, 248
for i, ctx in enumerate([0, 30, 60, 85, 96]):
    x = 60 + i * (SCR * SC + GAP)
    ry, iris = eye_h(ctx), level_color(ctx)
    crossed = ctx >= 95

    def body(ry=ry, iris=iris, crossed=crossed, ctx=ctx):
        eye(EYE_CX_L, EYE_CY, ry, iris, crossed=crossed)
        eye(EYE_CX_R, EYE_CY, ry, iris, crossed=crossed)
        bar(ctx)

    sub = [f"olho {ry}px de {EYE_RY}", f"íris {rgb(iris)}", f"barra {ctx}%"]
    if crossed:
        sub = ["valor ≥ 95 → X_X", "olho vira cruz", f"barra {ctx}%"]
    screen(x, TOP, SC, body, f"{ctx}%", sub, accent=crossed)

# ------------------------------------------------------ 2. estados extras ---
title(60, 566, "02", "Estados que não vêm do número",
      "piscar é local e num ritmo só — quem diz «trabalhando» é o clawd da seção 03 · dormir é a ausência de notícias do PC por 30 s")

TOP2 = 646
specials = [
    ("piscando", ["openTarget = 0 por 110 ms", "volta em 2,8–6,0 s", "independe de state"],
     lambda: (eye(EYE_CX_L, EYE_CY, 0, C_OK), eye(EYE_CX_R, EYE_CY, 0, C_OK), bar(28))),
    ("dormindo", ["sem ping há 30 s", "traço cinza #d6d2d6", "volta sozinho ao 1º ping"],
     lambda: (eye(EYE_CX_L, EYE_CY, 0, C_OK, asleep=True),
              eye(EYE_CX_R, EYE_CY, 0, C_OK, asleep=True), bar(0))),
    ("compactando", ["state=compact", "mesmo X_X do valor ≥ 95", "PreCompact → PostCompact"],
     lambda: (eye(EYE_CX_L, EYE_CY, 0, C_HOT, crossed=True),
              eye(EYE_CX_R, EYE_CY, 0, C_HOT, crossed=True), bar(63))),
]
for i, (cap, sub, body) in enumerate(specials):
    screen(60 + i * (SCR * SC + GAP), TOP2, SC, body, cap, sub)

# rampa de cor, ao lado
lx, ly = 60 + 3 * (SCR * SC + GAP) + 16, TOP2 + 8
add(f'<text x="{lx}" y="{ly+4}" fill="{FG}" font-size="15" font-weight="600">'
    f'Rampa de cor da íris</text>')
add(f'<text x="{lx}" y="{ly+26}" fill="{DIM}" font-size="13">'
    f'levelColor(): verde até 60%, âmbar, vermelho a 100%</text>')
for i in range(101):
    add(f'<rect x="{lx + i*2.4}" y="{ly+42}" width="2.5" height="26" '
        f'fill="{rgb(level_color(i))}"/>')
for pct in (0, 30, 60, 85, 100):
    add(f'<text x="{lx + pct*2.4}" y="{ly+86}" fill="{DIM}" font-family="{MONO}" '
        f'font-size="12">{pct}</text>')
for i, (k, v) in enumerate([
        ("olho aberto", f"{EYE_RY} px em 0% → {eye_h(100)} px em 100%"),
        ("centro dos olhos", f"({EYE_CX_L},{EYE_CY}) e ({EYE_CX_R},{EYE_CY}), rx {EYE_RX}"),
        ("barra", f"x {BAR_X} y {BAR_Y} · {BAR_W}×{BAR_H} px"),
        ("fundo", f"{FACE} — o rosto do mochi")]):
    add(f'<text x="{lx}" y="{ly+126+i*22}" fill="{DIM}" font-family="{MONO}" '
        f'font-size="12.5">{k.ljust(17).replace(" ", "&#160;")}{v}</text>')

# ------------------------------------------------------- 3. o clawd -------
title(60, 975, "03", "Trabalhando: o clawd anda na barra",
      "state=busy · um passo de 4 px a cada 80 ms, de ponta a ponta da barra · na ponta ele acena e volta · some quando o mochi cochila")


def cena_clawd():
    ry, iris = eye_h(63), level_color(63)
    eye(EYE_CX_L, EYE_CY, ry, iris)
    eye(EYE_CX_R, EYE_CY, ry, iris)
    bar(63)
    walker((WK_X0 + WK_X1) // 2, 0, sobe=1)


screen(60, 1050, 0.80, cena_clawd, "state=busy",
       ["passo de 4 px / 80 ms", f"sprite {WK_W}×{WK_H} px, x de {WK_X0} a {WK_X1}",
        "olhos seguem a cota, não o modo"])

# as poses ampliadas — e o zoom que mostra os tufos e a pupila
ZX, ZY, Z = 330, 1062, 5
add(f'<text x="{ZX}" y="{ZY-16}" fill="{FG}" font-size="15" font-weight="600">'
    f'As poses, {Z}×</text>')
for i, (nome, _) in enumerate(clawd.POSES):
    ox = ZX + i * (WK_W * Z + 20)
    add(f'<rect x="{ox-2}" y="{ZY-2}" width="{WK_W*Z+4}" height="{WK_H*Z+4}" '
        f'rx="6" fill="{FACE}" stroke="#3a342e"/>')
    add(f'<g transform="translate({ox},{ZY}) scale({Z}) '
        f'translate({-WK_X0},{-(WK_FEET-WK_H+1)})">')
    walker(WK_X0, i)
    add('</g>')
    # o topo da barra, para se ver que o pe encosta
    add(f'<rect x="{ox}" y="{ZY+WK_H*Z}" width="{WK_W*Z}" height="{Z}" '
        f'fill="{rgb(level_color(63))}"/>')
    add(f'<text x="{ox+WK_W*Z/2}" y="{ZY+WK_H*Z+30}" text-anchor="middle" fill="{DIM}" '
        f'font-family="{MONO}" font-size="12.5">{nome.lower()}</text>')

cy_ = 1050 + 8
cy_ = para(680, cy_ + 14, "Por que não piscar mais rápido",
           "piscada acelerada não se lê como trabalho, se lê como nervosismo — e "
           "mistura dois canais no mesmo lugar. Agora os olhos dizem só quanto da "
           "cota já foi, e o clawd diz só se está rodando agora.", width=52)
cy_ = para(680, cy_ + 24, "Duas camadas, três cores",
           "CORPO pinta a silhueta de escuro, OLHOS pinta só o branco por cima. "
           "A pupila é o buraco no branco, com o corpo aparecendo por baixo — três "
           "cores sem bitmap colorido e sem tabela de paleta.", width=52)
cy_ = para(680, cy_ + 24, "Custo no ESP8266",
           "uma fillRect de 24×27 para apagar e dois drawBitmap para desenhar, 12 "
           "vezes por segundo. A barra fica em y 206 e a caixa do sprite termina em "
           "205: um não encosta no outro, então nada precisa ser redesenhado.", width=52)
cy_ = para(680, cy_ + 24, "Cochilando ele some",
           "sem notícias do PC há 30 s o clawd sai da tela. Um bicho andando sem "
           "ninguém do outro lado do cabo estaria mentindo.", width=52)

# ------------------------------------------------------- 4. expressoes -----
title(60, 1370, "04", "Proposta: expressões vindas dos hooks",
      "o que ainda não existe no firmware — cada rosto usa só primitivas do Adafruit_GFX")

SC3, GAP3 = 0.75, 24
CY = EYE_CY


def dots(on=1):
    """Reticências de 'pensando'."""
    for i in range(3):
        add(f'<circle cx="{100 + i*20}" cy="170" r="6" '
            f'fill="{EYE if i <= on else TRACK}"/>')


def mouth(rx, ry):
    add(f'<ellipse cx="120" cy="170" rx="{rx}" ry="{ry}" fill="{EYE}"/>')


exprs = [
    ("perguntando", "Notification (permission_prompt)",
     lambda: (eye(EYE_CX_L, CY, 30, C_WARN, dy=-6), eye(EYE_CX_R, CY, 30, C_WARN, dy=-6),
              add(f'<text x="206" y="62" fill="{EYE}" font-family="{MONO}" '
                  f'font-size="52" font-weight="700" text-anchor="middle">?</text>'),
              bar(45))),
    ("trabalhando", "PreToolUse",
     lambda: (eye(EYE_CX_L, CY, 22, C_WARN), eye(EYE_CX_R, CY, 22, C_WARN),
              dots(1), bar(45))),
    ("procurando", "PreToolUse (Grep, Read)",
     lambda: (eye(EYE_CX_L, CY, 30, C_OK, dx=9), eye(EYE_CX_R, CY, 30, C_OK, dx=9),
              bar(45))),
    ("deu erro", "PostToolUseFailure, StopFailure",
     lambda: (brow(EYE_CX_L, True), brow(EYE_CX_R, False),
              eye(EYE_CX_L, CY, 26, C_HOT), eye(EYE_CX_R, CY, 26, C_HOT),
              mouth(16, 9), bar(45))),
    ("resolveu", "Stop, TaskCompleted",
     lambda: (happy_eye(EYE_CX_L), happy_eye(EYE_CX_R), mouth(20, 12), bar(45))),
    ("falando", "MessageDisplay",
     lambda: (eye(EYE_CX_L, CY, 30, C_OK), eye(EYE_CX_R, CY, 30, C_OK),
              mouth(14, 17), bar(45))),
]
for i, (cap, hook, body) in enumerate(exprs):
    col, row = i % 3, i // 3
    screen(60 + col * (SCR * SC3 + GAP3), 1445 + row * 266, SC3, body, cap,
           [hook], accent=True)

# ------------------------------------------------- painel lateral ----------
px, py = 716, 1439
add(f'<rect x="{px-22}" y="{py-34}" width="{W-px-38}" height="672" rx="14" '
    f'fill="#1b1714" stroke="#2b2722"/>')
add(f'<text x="{px}" y="{py}" fill="{FG}" font-size="15" font-weight="600">'
    f'Vocabulário de state a acrescentar</text>')
add(f'<text x="{px}" y="{py+22}" fill="{DIM}" font-family="{MONO}" font-size="12" '
    f'xml:space="preserve">valor   rosto          hook</text>')
vocab = [("ask", "perguntando", "Notification"),
         ("tool", "trabalhando", "PreToolUse"),
         ("find", "procurando", "PreToolUse"),
         ("error", "deu erro", "PostToolUseFailure"),
         ("done", "resolveu", "Stop"),
         ("talk", "falando", "MessageDisplay")]
for i, (k, face, hook) in enumerate(vocab):
    add(f'<text x="{px}" y="{py+44+i*20}" fill="{FG}" '
        f'font-family="{MONO}" font-size="12" xml:space="preserve">'
        f'<tspan fill="{ACC}">{k.ljust(8)}</tspan>{face.ljust(15)}'
        f'<tspan fill="{DIM}">{hook}</tspan></text>')

y = py + 190
y = para(px, y, "Como o dado chega",
         "a status line já recebe context_window.used_percentage e "
         "rate_limits.five_hour.used_percentage a cada mensagem do assistente; "
         "os hooks só acrescentam o campo state.", width=48)
y = para(px, y + 26, "Protocolo",
         "continua uma linha a 115200 bps — ctx=42 win=63 state=busy — só cresce "
         "o vocabulário aceito em applyKV().", width=48)
y = para(px, y + 26, "Custo no ESP8266",
         "cada rosto redesenha apenas a área dos olhos. Boca e sobrancelha são "
         "mais dois retângulos limpos por quadro: cabe folgado nos ~60 fps.", width=48)
y = para(px, y + 26, "Cuidado",
         "expressão que troca toda hora vira poluição visual. Vale segurar cada "
         "estado por ~800 ms antes de voltar ao rosto de contexto.", width=48)

add(f'<text x="60" y="{H-30}" fill="#5b554e" font-family="{MONO}" font-size="12">'
    f'gerado por docs/tela/gera_svg.py · projeto de fã, sem vínculo com a Anthropic</text>')
add('</svg>')

svg = "\n".join(out)
with open("docs/tela/tela-mochi.svg", "w", encoding="utf-8") as f:
    f.write(svg)
print(f"docs/tela/tela-mochi.svg — {len(svg)} bytes")
