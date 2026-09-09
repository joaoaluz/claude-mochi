#!/usr/bin/env python3
"""Gera docs/tela/tela-mochi.svg — o mapa do que aparece no display.

As constantes e a matematica sao copiadas de
firmware/claude_mochi/claude_mochi.ino (branch claude-mochi-token-eyes),
inclusive o truncamento inteiro, para o desenho bater pixel a pixel com o
que o ST7789 mostra. Mudou o firmware? Ajuste aqui e rode de novo:

    python3 docs/tela/gera_svg.py
"""

# ----------------------------------------------------------- firmware ------
SCR      = 240
EYE_CX_L = 78
EYE_CX_R = 162
EYE_CY   = 104
EYE_RX   = 30
EYE_RY   = 34
BAR_X    = 34
BAR_Y    = 206
BAR_H    = 10
BAR_W    = SCR - 2 * BAR_X

C_FACE  = 0xF71C
C_EYE   = 0x18E3
C_OK    = 0x2E88
C_WARN  = 0xFCA0
C_HOT   = 0xE0A3
C_SHINE = 0xFFFF
C_TRACK = 0xE71C
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
        r = 22
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
        add(f'<circle cx="{cx-EYE_RX//3}" cy="{cy-ry//2}" r="4" fill="#ffffff"/>')


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


W, H = 1180, 1740
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
title(60, 168, "01", "Consumo de contexto → abertura do olho",
      "openTarget = 1 − 0,72 × ctx/100 · a íris vai de verde a vermelho · a barra de baixo é o limite de 5 h")

SC, GAP, TOP = 0.80, 24, 248
for i, (ctx, win) in enumerate([(0, 8), (30, 28), (60, 45), (85, 63), (96, 88)]):
    x = 60 + i * (SCR * SC + GAP)
    ry, iris = eye_h(ctx), level_color(ctx)
    crossed = ctx >= 95

    def body(ry=ry, iris=iris, crossed=crossed, win=win):
        eye(EYE_CX_L, EYE_CY, ry, iris, crossed=crossed)
        eye(EYE_CX_R, EYE_CY, ry, iris, crossed=crossed)
        bar(win)

    sub = [f"olho {ry}px de {EYE_RY}", f"íris {rgb(iris)}", f"barra 5h {win}%"]
    if crossed:
        sub = ["ctx ≥ 95 → X_X", "olho vira cruz", f"barra 5h {win}%"]
    screen(x, TOP, SC, body, f"ctx {ctx}%", sub, accent=crossed)

# ------------------------------------------------------ 2. estados extras ---
title(60, 566, "02", "Estados que não vêm do contexto",
      "piscar é local (mais rápido quando state=busy) · dormir é a ausência de notícias do PC por 30 s")

TOP2 = 646
specials = [
    ("piscando", ["openTarget = 0 por 110 ms", "state=busy → 0,9–2,0 s", "state=idle → 2,8–6,0 s"],
     lambda: (eye(EYE_CX_L, EYE_CY, 0, C_OK), eye(EYE_CX_R, EYE_CY, 0, C_OK), bar(28))),
    ("dormindo", ["sem ping há 30 s", "traço cinza #d6d2d6", "volta sozinho ao 1º ping"],
     lambda: (eye(EYE_CX_L, EYE_CY, 0, C_OK, asleep=True),
              eye(EYE_CX_R, EYE_CY, 0, C_OK, asleep=True), bar(0))),
    ("compactando", ["state=compact", "mesmo X_X do ctx ≥ 95", "PreCompact → PostCompact"],
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
        ("olho aberto", f"{EYE_RY} px em ctx 0% → {eye_h(100)} px em ctx 100%"),
        ("centro dos olhos", f"({EYE_CX_L},{EYE_CY}) e ({EYE_CX_R},{EYE_CY}), rx {EYE_RX}"),
        ("barra 5 h", f"x {BAR_X} y {BAR_Y} · {BAR_W}×{BAR_H} px"),
        ("fundo", f"{FACE} — o rosto do mochi")]):
    add(f'<text x="{lx}" y="{ly+126+i*22}" fill="{DIM}" font-family="{MONO}" '
        f'font-size="12.5">{k.ljust(17).replace(" ", "&#160;")}{v}</text>')

# ------------------------------------------------------- 3. expressoes -----
title(60, 975, "03", "Proposta: expressões vindas dos hooks",
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
    screen(60 + col * (SCR * SC3 + GAP3), 1050 + row * 266, SC3, body, cap,
           [hook], accent=True)

# ------------------------------------------------- painel lateral ----------
px, py = 716, 1044
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
