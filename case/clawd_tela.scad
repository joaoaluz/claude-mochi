// claude-mochi — Clawd com janela de display
// -----------------------------------------------------------------------------
// Base: as duas malhas do SEU projeto clawd_mochi.3mf (Bambu Studio), extraidas
// para models/upstream/3mf-corpo.stl e 3mf-chapa.stl. As duas ja vem centradas
// na origem, exatamente como o fatiador as tem.
//
// Origem da geometria: clawd-mochi de yousifamanuel — CC BY-NC-SA 4.0.
//
// O que este arquivo acrescenta ao modelo original:
//   1. janela para a area ativa do display, com chanfro de 45 graus
//   2. alargamento da cavidade em -Y, porque a placa do display nao cabia
//   3. moldura interna que segura a PCB contra a chapa, com saia a 45 graus
//      para imprimir SEM suporte nessa regiao
//
// So o DISPLAY vai dentro. O ESP8266 fica fora; os fios saem pelo fundo, que
// ja e aberto no modelo original.
//
// Gerar:
//   openscad -o chapa.stl -D 'part="chapa"' case/clawd_tela.scad
//   openscad -o corpo.stl -D 'part="corpo"' case/clawd_tela.scad
// -----------------------------------------------------------------------------

part = "montado";   // "chapa" | "corpo" | "montado" | "corte"

CORPO_STL = "../models/upstream/3mf-corpo.stl";
CHAPA_STL = "../models/upstream/3mf-chapa.stl";

$fn = 48;

// ------------------------------------------------------------------ escala ---
// Do seu 3mf: XY em 100%, e o corpo achatado em Z (38 -> 28 mm). O valor de Z
// e o m22 da matriz do objeto no arquivo. Como aqui a escala e assada na malha,
// no fatiador o objeto entra com escala 1 em Z.
escala_xy = 1.0;
escala_z  = 0.736842105;   // 28 / 38

// ----------------------------------------------------------------- display ---
// ⚠ MEDIDAS ESTIMADAS para um ST7789 1,54" 240x240 de 7 pinos.
// CONFIRA COM PAQUIMETRO antes de imprimir. O modulo entra deitado: o lado de
// 39 mm corre no eixo X.
pcb_x        = 39.0;   // lado maior da placa do display
pcb_y        = 31.5;   // lado menor
pcb_t        = 1.7;    // espessura da placa, sem componentes
ativa        = 27.7;   // lado da area ativa (quadrada)
ativa_dx     = -3.0;   // desvio da area ativa vs centro da placa, no eixo X
pcb_folga    = 0.30;   // folga por lado no encaixe da PCB
janela_folga = 0.40;   // quanto a janela abre alem da area ativa, por lado
chanfro      = 0.8;    // chanfro a 45 graus na borda externa da janela

// ------------------------------------------- contorno medido das malhas ------
// Levantado por amostragem sobre as malhas do 3mf; nao mexa sem remedir.
larg     = 63.94;   // X das duas pecas
prof     = 48.62;   // Y das duas pecas
corpo_h  = 38.00;   // altura do corpo na malha, ANTES de escala_z
chapa_h  =  2.00;

cav_x0   = -24.25;  cav_x1 = 24.25;   // cavidade passante, em X
cav_y0   = -10.75;  cav_y1 = 21.50;   // em Y  (parede -Y tem 13,56 mm; +Y so 2,81)

boca_cy  = -7.62;   boca_l = 9.00;  boca_a = 3.25;   // furo da boca, na chapa
olho_dx  = 29.25;   olho_cy = 5.50; olho_l = 3.50;   // os dois furinhos das orelhas

// ------------------------------------------------------------------ extras ---
// A cavidade tem 32,25 mm em Y e a placa do display tem 31,5: sobram 0,375 mm
// por lado. Aperta, mas alargar em -Y NAO e de graca: em Y -10,75..-12,5 existe
// uma faixa macica que fecha o fundo da cavidade e de onde saem as quatro
// perninhas. Cortar a faixa inteira solta as perninhas do corpo (foi o que deu
// "Volumes: 3" na primeira tentativa). Por isso o alargamento e opcional e so
// vale para os primeiros milimetros a partir do topo, onde a PCB realmente esta.
alargar    = 0.0;    // 0 = cavidade original. >0 come a faixa do fundo.
alargar_z  = 3.0;    // profundidade do alargamento, medida a partir do topo

moldura    = true;   // moldura interna que segura a PCB contra a chapa
moldura_t  = 2.0;    // espessura da moldura
tapar_boca = true;   // a boca cai dentro da janela; sem tapar vira rebarba

// --------------------------------------------------------------- derivados ---
corpo_hz = corpo_h * escala_z;          // altura real do corpo depois de achatado
corpo_z0 = -corpo_hz / 2;               // a malha e centrada em Z
corpo_z1 =  corpo_hz / 2;

cav_l  = (cav_x1 - cav_x0) * escala_xy;                 // cavidade em X
cav_p  = (cav_y1 - (cav_y0 - alargar)) * escala_xy;     // em Y, com o alargamento
cav_cx = (cav_x0 + cav_x1) / 2 * escala_xy;
cav_cy = ((cav_y0 - alargar) + cav_y1) / 2 * escala_xy;

pcb_lx = pcb_x + 2 * pcb_folga;
pcb_ly = pcb_y + 2 * pcb_folga;

// A moldura fica ATRAS da PCB e a empurra contra a chapa. A abertura dela e a
// mesma da janela: menor que a placa (senao a placa passa direto por dentro) e
// nao menor que a area ativa (senao apareceria tapando a borda da tela).
mold_l = ativa + 2*janela_folga;
mold_p = ativa + 2*janela_folga;

// quanto de borda da PCB a moldura pega, dos quatro lados
pega_xm = (pcb_x/2) - (mold_l/2 - ativa_dx);
pega_xp = (pcb_x/2) - (mold_l/2 + ativa_dx);
pega_ym = (pcb_y - mold_p) / 2;

// saia a 45 graus embaixo da moldura, para nao precisar de suporte
recuo    = max((cav_l + 1.2 - mold_l) / 2, (cav_p + 1.2 - mold_p) / 2);
mold_z1  = corpo_z1 - pcb_t;             // topo da moldura
mold_z0  = mold_z1 - moldura_t;          // base da parte reta
saia_z0  = mold_z0 - recuo;              // onde a saia comeca

// ------------------------------------------------------------- verificacoes --
assert(pcb_lx <= cav_l,
       str("A placa nao entra no eixo X: precisa de ", pcb_lx,
           " mm e a cavidade tem ", cav_l, " mm. Aumente 'escala_xy'."));
assert(pcb_ly <= cav_p,
       str("A placa nao entra no eixo Y: precisa de ", pcb_ly,
           " mm e a cavidade tem ", cav_p,
           " mm. Aumente 'alargar' (a parede -Y tem 13,56 mm) ou 'escala_xy'."));
assert(cav_y0 - alargar > -prof/2 + 3.0,
       str("'alargar' = ", alargar,
           " deixaria a parede -Y com menos de 3 mm. Reduza."));
assert(saia_z0 > corpo_z0 + 1.0,
       "A moldura com a saia de 45 graus nao cabe na altura do corpo. Reduza 'moldura_t' ou aumente 'escala_z'.");
assert(ativa + 2*janela_folga < pcb_y,
       "A janela ficou maior que a placa — reveja 'ativa' e 'janela_folga'.");
assert(min(pega_xm, pega_xp, pega_ym) >= 1.0,
       str("A moldura so pegaria ", min(pega_xm, pega_xp, pega_ym),
           " mm de borda da PCB (minimo 1,0). Reduza 'janela_folga' ou reveja ",
           "'ativa_dx'."));

jan_cx = cav_cx + ativa_dx;
jan_cy = cav_cy;

// ------------------------------------------------------------------ pecas ----
module corpo_bruto() { scale([escala_xy, escala_xy, escala_z]) import(CORPO_STL, convexity = 10); }
module chapa_bruta() { scale([escala_xy, escala_xy, 1])        import(CHAPA_STL, convexity = 10); }

// Alargamento da cavidade para -Y, so nos 'alargar_z' mm de cima. Assim a faixa
// macica do fundo e as perninhas continuam inteiras abaixo do corte.
module alargamento() {
    if (alargar > 0)
        translate([cav_cx, (cav_y0 - alargar/2) * escala_xy, corpo_z1 - alargar_z/2 + 0.01])
            cube([(cav_x1 - cav_x0) * escala_xy, alargar * escala_xy, alargar_z], center = true);
}

// janela quadrada com chanfro a 45 graus na face de fora (+Z)
module janela(h) {
    j = ativa + 2*janela_folga;
    union() {
        translate([0, 0, 0]) cube([j, j, h + 4], center = true);
        if (chanfro > 0)
            translate([0, 0, h/2 - chanfro])
                linear_extrude(height = chanfro + 0.01, scale = (j + 2*chanfro) / j)
                    square([j, j], center = true);
    }
}

module chapa() {
    difference() {
        union() {
            chapa_bruta();
            // A base da janela cai dentro da boca e deixaria uma fresta de
            // 0,37 mm. A tampa desce ate bem dentro do macico da chapa, senao
            // o chanfro descola a lasca e ela sai como solido solto no STL.
            // Altura exatamente igual a da chapa: sobrando em Z, vira degrau
            // na face de fora.
            if (tapar_boca)
                translate([0, (boca_cy - 2.25) * escala_xy, 0])
                    cube([(boca_l + 0.6) * escala_xy, (boca_a + 5.1) * escala_xy,
                          chapa_h], center = true);
        }
        translate([jan_cx, jan_cy, 0]) janela(chapa_h);
    }
}

// moldura: anel reto no topo + saia a 45 graus embaixo, tudo fundido na parede
module moldura_pcb() {
    difference() {
        union() {
            // parte reta
            translate([cav_cx, cav_cy, (mold_z0 + mold_z1)/2])
                cube([cav_l + 1.2, cav_p + 1.2, moldura_t], center = true);
            // saia: cresce de nada ate a moldura, a 45 graus
            hull() {
                translate([cav_cx, cav_cy, saia_z0 + 0.005])
                    cube([cav_l + 1.2, cav_p + 1.2, 0.01], center = true);
                translate([cav_cx, cav_cy, mold_z0])
                    cube([cav_l + 1.2, cav_p + 1.2, 0.01], center = true);
            }
        }
        // furo: reto no topo, abrindo a 45 graus para baixo
        union() {
            translate([jan_cx, jan_cy, (mold_z0 + mold_z1)/2 + 0.1])
                cube([mold_l, mold_p, moldura_t + 1], center = true);
            hull() {
                translate([jan_cx, jan_cy, mold_z0])
                    cube([mold_l, mold_p, 0.01], center = true);
                translate([cav_cx, cav_cy, saia_z0 - 0.01])
                    cube([cav_l + 1.4, cav_p + 1.4, 0.01], center = true);
            }
        }
    }
}

module corpo() {
    union() {
        difference() {
            corpo_bruto();
            alargamento();
        }
        if (moldura) moldura_pcb();
    }
}

// ------------------------------------------------------------------ saidas ---
if (part == "chapa") {
    chapa();

} else if (part == "corpo") {
    corpo();

} else if (part == "montado") {
    corpo();
    color("#d97757") translate([0, 0, corpo_z1 + chapa_h/2]) chapa();
    %translate([cav_cx, cav_cy, corpo_z1 - pcb_t/2]) cube([pcb_x, pcb_y, pcb_t], center = true);

} else if (part == "corte") {
    difference() {
        union() {
            corpo();
            translate([0, 0, corpo_z1 + chapa_h/2]) chapa();
        }
        translate([-larg, 0, -corpo_hz]) cube([larg*2, prof, corpo_hz*2 + 10]);
    }

} else {
    assert(false, str("part desconhecido: ", part));
}
