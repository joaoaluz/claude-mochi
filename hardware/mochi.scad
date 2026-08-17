// ---------------------------------------------------------------
//  claude-mochi — carcaca imprimivel do assistente de mesa
// ---------------------------------------------------------------
//  Duas pecas, ambas impressas sem suporte:
//    "casca" — corpo do mochi, oco, com os pilares dos parafusos
//    "base"  — placa do fundo, com os espacadores da PCB
//
//  Exemplos:
//    openscad -o casca.stl -D 'part="casca"' hardware/mochi.scad
//    openscad -o pico.stl  -D 'part="chapa"' -D 'board_name="pico"' \
//             hardware/mochi.scad
//    make stl        # gera tudo em hardware/stl/
//
//  Todas as medidas em milimetros.
// ---------------------------------------------------------------

include <boards.scad>

/* [Peca] */
// "casca", "base", "chapa" (as duas deitadas para imprimir) ou "montado"
part = "chapa";

/* [Placa] */
board_name = "pi_zero";     // "pi_zero" ou "pico"
board_rot  = -1;            // graus (0/90/180/270); -1 = padrao da placa
board_clear = 1.5;          // folga lateral ao redor da PCB
// Aberturas a abrir na parede; [] = padrao da placa.
// Ex.: -D 'open_ports=["usb-pwr","usb-data","microsd"]'
open_ports = [];

/* [Corpo] */
body_w   = 0;               // largura externa  (0 = padrao da placa)
body_d   = 0;               // profundidade externa
body_h   = 0;               // altura externa
corner_f = 0.24;            // raio dos cantos = corner_f * menor lado
s_bottom = 0.88;            // largura relativa na base (0.8 = mais "gota")
t_fillet = 0.24;            // fracao da altura do arredondamento inferior
t_dome   = 0.42;            // fracao da altura onde comeca a cupula
wall     = 2.4;             // espessura da parede

/* [Montagem] */
base_t      = 3.0;          // espessura da placa do fundo
standoff_h  = 5.0;          // altura dos espacadores sob a PCB
post_r      = 3.6;          // raio dos pilares de parafuso
post_h      = 13.0;         // altura dos pilares
post_embed  = 1.2;          // quanto o pilar entra na parede (funde as pecas)
screw_pilot = 2.5;          // furo-guia no pilar (M3 auto-atarraxante)
screw_free  = 3.4;          // passagem do parafuso na base
screw_head  = 6.6;          // diametro do escareado
plate_gap   = 0.5;          // recuo da base em relacao ao corpo

/* [Detalhes] */
face       = true;          // rostinho gravado na frente
face_depth = 1.0;
vents      = true;          // grelha frontal + rasgos na base
feet       = true;          // rebaixos para pes de borracha

/* [Qualidade] */
layers_n = 72;              // fatias usadas para gerar a curva do corpo
$fs = 0.6;
$fa = 5;

// =================================================================
//  Valores derivados
// =================================================================
assert(board_size(board_name) != undef,
       str("Placa desconhecida: ", board_name, " (use pi_zero ou pico)"));

BS   = board_size(board_name);          // [comp, larg, esp]
BL   = BS[0];
BW   = BS[1];
BT   = BS[2];
BROT = board_rot < 0 ? board_rot_default(board_name) : board_rot;

SHELL = board_shell(board_name);
W = body_w > 0 ? body_w : SHELL[0];
D = body_d > 0 ? body_d : SHELL[1];
H = body_h > 0 ? body_h : SHELL[2];
RC = corner_f * min(W, D);

// Cavidade interna
WI  = W - 2 * wall;
DI  = D - 2 * wall;
HI  = H - wall;
RCI = RC - wall;

// Seccao interna no nivel do fundo (onde a placa precisa caber)
WIB = WI * s_bottom;
DIB = DI * s_bottom;
RIB = RCI * s_bottom;

// Placa do fundo
PW = W * s_bottom - plate_gap;
PD = D * s_bottom - plate_gap;
PR = RC * s_bottom - plate_gap / 2;

PCB_Z = standoff_h;                     // face inferior da PCB
TOP_Z = standoff_h + BT;                // face superior da PCB

// Pilares dos parafusos: nos quatro cantos arredondados, encostados na
// parede (o trecho inferior funde com ela, que e onde o parafuso puxa).
ARCX = WIB / 2 - RIB;                   // centro do arco do canto, no fundo
ARCY = DIB / 2 - RIB;
PRAD = RIB - post_r + post_embed;       // distancia radial do pilar ao arco

// Pegada da placa em coordenadas globais
FOOT = (BROT % 180 == 0) ? [BL, BW] : [BW, BL];

// =================================================================
//  Funcoes auxiliares
// =================================================================

// Perfil vertical do mochi: escala horizontal em funcao da altura (t = 0..1)
function mochi_s(t) =
    t <= 0        ? s_bottom :
    t <  t_fillet ? s_bottom + (1 - s_bottom) * sqrt(1 - pow(1 - t / t_fillet, 2)) :
    t <  t_dome   ? 1 :
    t >= 1        ? 0 :
                    sqrt(max(0, 1 - pow((t - t_dome) / (1 - t_dome), 2)));

// Coordenada local da placa -> coordenada global (placa centrada na carcaca)
function b2g(p) =
    let (a = BROT, x = p[0] - BL / 2, y = p[1] - BW / 2)
    [x * cos(a) - y * sin(a), x * sin(a) + y * cos(a)];

// Vetor local -> global (sem translacao)
function v2g(v) =
    let (a = BROT) [v[0] * cos(a) - v[1] * sin(a), v[0] * sin(a) + v[1] * cos(a)];

// Ponto dentro de um retangulo arredondado (com margem extra)?
function rr_inside(p, w, d, r, extra = 0) =
    let (dx = max(0, abs(p[0]) - (w / 2 - r)),
         dy = max(0, abs(p[1]) - (d / 2 - r)))
    sqrt(dx * dx + dy * dy) + extra <= r + 0.001;

// Distancia de um ponto ate um retangulo centrado na origem (0 = dentro)
function rect_dist(p, w, d) =
    let (dx = max(0, abs(p[0]) - w / 2), dy = max(0, abs(p[1]) - d / 2))
    sqrt(dx * dx + dy * dy);

function contains(list, v) = len([for (x = list) if (x == v) 1]) > 0;

// Aberturas de parede realmente abertas nesta impressao
OPEN = len(open_ports) > 0 ? open_ports : board_open_ports(board_name);

// Superficie frontal do corpo na altura z (usada para gravar o rosto)
function front_y(z) = -(D / 2) * mochi_s(z / H);

// --- posicao dos pilares -----------------------------------------
// Cada pilar corre pelo arco do seu canto e para na posicao que ficar
// mais longe da placa e de todas as aberturas abertas. Assim mudar de
// placa, girar a placa ou abrir outra porta nao cria colisao.

// Distancia, em planta, de um ponto ate o rasgo de uma porta
function port_dist(p, prt) =
    let (o  = b2g(prt[1]), n = v2g(prt[2]), t = [-n[1], n[0]],
         du = (p[0] - o[0]) * n[0] + (p[1] - o[1]) * n[1],
         dv = (p[0] - o[0]) * t[0] + (p[1] - o[1]) * t[1],
         eu = max(0, -4 - du),
         ev = max(0, abs(dv) - prt[3] / 2))
    sqrt(eu * eu + ev * ev);

function post_score(p) =
    min([rect_dist(p, FOOT[0] + 2 * board_clear, FOOT[1] + 2 * board_clear),
         for (prt = board_ports(board_name)) if (contains(OPEN, prt[0])) port_dist(p, prt)]);

function post_at(sx, sy, a) = [sx * (ARCX + PRAD * cos(a)), sy * (ARCY + PRAD * sin(a))];

function argmax(v, i = 1, b = 0) = i >= len(v) ? b : argmax(v, i + 1, v[i] > v[b] ? i : b);

PANGS = [for (i = [0 : 36]) i * 2.5];

POSTS = [for (sx = [-1, 1], sy = [-1, 1])
            let (best = argmax([for (a = PANGS) post_score(post_at(sx, sy, a))]))
            post_at(sx, sy, PANGS[best])];

// =================================================================
//  Verificacoes de sanidade (falham a compilacao com uma mensagem util)
// =================================================================
CORNERS = [for (sx = [-1, 1], sy = [-1, 1])
              [sx * (FOOT[0] / 2 + board_clear), sy * (FOOT[1] / 2 + board_clear)]];

assert(RC <= min(W, D) / 2, "corner_f grande demais para o corpo");
assert(face_depth <= wall - 1.0, "face_depth deixaria a parede fina demais");

assert(len([for (c = CORNERS) if (!rr_inside(c, WIB, DIB, RIB)) 1]) == 0,
       str("A placa ", board_name, " nao cabe na abertura do fundo. ",
           "Aumente body_w/body_d ou s_bottom."));

assert(len([for (p = POSTS) if (post_score(p) < post_r + 0.4) 1]) == 0,
       str("Nao ha espaco para os pilares de parafuso com a placa ", board_name,
           " e as aberturas ", OPEN,
           ". Aumente body_w/body_d, reduza corner_f ou feche uma abertura."));

assert(post_embed < wall * s_bottom - 0.6,
       "post_embed furaria a parede externa; reduza post_embed ou aumente wall.");

assert(post_r * 2 + 1.5 < RIB * 2, "Cantos pequenos demais para os pilares.");

// =================================================================
//  Geometria basica
// =================================================================

// Retangulo arredondado centrado
module rrect(w, d, r) {
    rr = max(0.05, min(r, w / 2 - 0.05, d / 2 - 0.05));
    offset(r = rr) square([w - 2 * rr, d - 2 * rr], center = true);
}

// Corpo macico do mochi, apoiado em z = 0
module blob(w, d, h, r, n = layers_n) {
    for (i = [0 : n - 1]) {
        t0 = i / n;
        t1 = (i + 1) / n;
        s0 = max(mochi_s(t0), 0.02);
        s1 = max(mochi_s(t1), 0.02);
        hull() {
            translate([0, 0, h * t0]) linear_extrude(0.02) rrect(w * s0, d * s0, r * s0);
            translate([0, 0, h * t1]) linear_extrude(0.02) rrect(w * s1, d * s1, r * s1);
        }
    }
}

// Perfil de abertura com teto em 45 graus (imprime sem suporte)
module arch(w, h, r = 1.2) {
    rr = min(r, w / 2 - 0.05, h / 2 - 0.05);
    hull() {
        offset(r = rr) square([w - 2 * rr, h - 2 * rr], center = true);
        translate([0, h / 2 + w / 2 - rr]) circle(r = rr);
    }
}

// Prisma de corte partindo de "pos" e saindo na direcao "nrm"
module wall_cut(pos, nrm, w, h, z, len) {
    ang = atan2(nrm[1], nrm[0]);
    translate([pos[0] - nrm[0] * 4, pos[1] - nrm[1] * 4, z])
        rotate([0, 0, ang + 90])
            rotate([90, 0, 0])
                linear_extrude(len + 4)
                    arch(w, h);
}

// =================================================================
//  Casca (corpo)
// =================================================================
module posts() {
    for (p = POSTS)
        translate([p[0], p[1], 0])
            difference() {
                union() {
                    cylinder(r = post_r, h = post_h - 1);
                    translate([0, 0, post_h - 1])
                        cylinder(r1 = post_r, r2 = post_r - 1, h = 1);
                }
                translate([0, 0, -0.1])
                    cylinder(d = screw_pilot, h = post_h - 3);
                // chanfro de entrada do parafuso
                translate([0, 0, -0.1])
                    cylinder(d1 = screw_pilot + 1.6, d2 = screw_pilot, h = 0.9);
            }
}

module port_cuts() {
    for (p = board_ports(board_name))
        if (contains(OPEN, p[0])) {
            pos = b2g(p[1]);
            nrm = v2g(p[2]);
            wall_cut(pos, nrm, p[3], p[4], TOP_Z + p[5], max(W, D));
        }
}

module front_grille() {
    n = 5;
    for (i = [0 : n - 1]) {
        x = (i - (n - 1) / 2) * 5.2;
        wall_cut([x, -DI / 2], [0, -1], 2.4, 7, H * 0.13, D);
    }
}

module face_cuts() {
    eye_r   = 3.4;
    eye_dx  = W * 0.145;
    eye_z   = H * 0.55;
    mouth_r = 2.2;
    mouth_z = H * 0.40;

    for (m = [-1, 1])
        translate([m * eye_dx, front_y(eye_z) + face_depth - eye_r, eye_z])
            sphere(r = eye_r);

    // boquinha oval
    translate([0, front_y(mouth_z) + face_depth - mouth_r, mouth_z])
        scale([1.7, 1, 0.9])
            sphere(r = mouth_r);
}

module casca() {
    difference() {
        union() {
            difference() {
                blob(W, D, H, RC);
                // cavidade
                blob(WI, DI, HI, RCI);
                // garante que o fundo fique aberto
                translate([0, 0, -2]) linear_extrude(2.2) rrect(WIB, DIB, RIB);
            }
            posts();
        }
        port_cuts();
        if (vents) front_grille();
        if (face) face_cuts();
    }
}

// =================================================================
//  Base (placa do fundo)
// =================================================================
module standoffs() {
    r = board_standoff_r(board_name);
    for (h = board_holes(board_name)) {
        p = b2g(h);
        translate([p[0], p[1], base_t - 0.01])
            difference() {
                cylinder(r = r, h = standoff_h + 0.01);
                translate([0, 0, standoff_h - 3.4])
                    cylinder(d = board_pilot(board_name), h = 3.6);
            }
    }
}

module base_vents() {
    // faixa livre entre os espacadores da placa
    hx   = min([for (h = board_holes(board_name)) abs(b2g(h)[0])]);
    xmax = hx - board_standoff_r(board_name) - 1.6;
    ylen = max(6, min(FOOT[1] - 8, 24));
    n    = max(2, floor(2 * xmax / 9));
    for (i = [0 : n - 1]) {
        x = (i - (n - 1) / 2) * (2 * xmax / n);
        translate([x, 0, -1])
            linear_extrude(base_t + 2)
                rrect(3, ylen, 1.5);
    }
}

module base() {
    difference() {
        union() {
            linear_extrude(base_t) rrect(PW, PD, PR);
            standoffs();
        }
        // parafusos que sobem para os pilares da casca
        for (p = POSTS) {
            translate([p[0], p[1], -0.1])
                cylinder(d = screw_free, h = base_t + 0.2);
            translate([p[0], p[1], -0.01])
                cylinder(d1 = screw_head, d2 = screw_free, h = (screw_head - screw_free) / 2);
        }
        if (vents) base_vents();
        // rebaixos para pes de borracha, longe dos parafusos dos cantos
        if (feet)
            for (sx = [-1, 1], sy = [-1, 1])
                translate([sx * PW * 0.28, sy * (PD / 2 - 7.5), -0.01])
                    cylinder(d = 9, h = 0.7);
    }
}

// =================================================================
//  Visualizacao
// =================================================================
module board_mock() {
    color("#2e7d32")
        translate([0, 0, PCB_Z])
            rotate([0, 0, BROT])
                translate([-BL / 2, -BW / 2, 0])
                    cube([BL, BW, BT]);
}

module montado(ghost = true) {
    translate([0, 0, base_t]) {
        if (ghost) %casca();
        else casca();
        board_mock();
    }
    base();
}

module chapa() {
    translate([-(W + 6) / 2, 0, 0]) casca();
    translate([ (PW + 6) / 2, 0, 0]) base();
}

// Meia-secao, so para conferir o interior na tela
module corte() {
    difference() {
        montado(ghost = false);
        translate([-W, 0, -base_t - 1]) cube([2 * W, D, 2 * H]);
    }
}

// =================================================================
if      (part == "casca")   casca();
else if (part == "base")    base();
else if (part == "chapa")   chapa();
else if (part == "montado") montado();
else if (part == "corte")   corte();
else assert(false, str("part invalido: ", part));

echo(str("corpo = ", W, " x ", D, " x ", H + base_t, " mm (com a base)"));
echo(str("abertura interna do fundo = ", WIB, " x ", DIB, " mm"));
