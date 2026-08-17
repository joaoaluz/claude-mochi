// claude-mochi — case paramétrico
// -----------------------------------------------------------------------------
// v0: ponto de partida. TODAS as medidas de componente abaixo precisam ser
// conferidas com paquímetro no SEU display e na SUA placa antes de imprimir.
//
// Como gerar os STLs (linha de comando):
//   openscad -D 'part="front"' -o front.stl mochi.scad
//   openscad -D 'part="back"'  -o back.stl  mochi.scad
//
// Ou abra no OpenSCAD e mude a variável `part` no topo.
// -----------------------------------------------------------------------------

part = "all";   // "all" | "front" | "back" | "preview"

$fn = 64;

// ---------------------------------------------------------------- display ---
// ST7789 1.54" 240x240, módulo de 7 pinos. CONFIRA COM PAQUÍMETRO.
scr_pcb_w      = 31.5;  // largura da placa do display
scr_pcb_h      = 39.0;  // altura da placa do display
scr_pcb_t      = 1.7;   // espessura da placa (sem componentes)
scr_active     = 27.7;  // lado da área ativa (quadrada)
scr_active_dy  = -3.0;  // deslocamento vertical da área ativa vs centro da placa
scr_fit        = 0.35;  // folga por lado no encaixe da placa

// ------------------------------------------------------------------ placa ---
// Wemos D1 mini: 34.2 x 25.6 | NodeMCU v3: 58 x 31 | NodeMCU v2: 49 x 26
brd_l          = 34.2;
brd_w          = 25.6;
brd_t          = 1.4;
brd_fit        = 0.4;

// Recorte do conector USB (micro-USB na maioria dos ESP8266).
usb_w          = 9.0;
usb_h          = 4.0;
usb_z          = 12.0;  // altura do centro do conector a partir da base

// ------------------------------------------------------------------ corpo ---
wall           = 2.2;   // espessura de parede
body_w         = 78;    // largura total
body_d         = 62;    // profundidade total
body_h         = 70;    // altura total
r_bot          = 17;    // raio das esferas da base
r_mid          = 19;    // raio da "barriga"
r_top          = 21;    // raio da cúpula
top_scale      = 0.36;  // quão estreito é o topo (fração da largura)

face_y         = 23.0;  // plano do rosto: face plana em y = -face_y
split_y        = 6.0;   // plano de separação frente/tampa (y = +split_y)
lip_h          = 3.0;   // altura do lábio de encaixe da tampa
lip_fit        = 0.30;  // folga do lábio
lip_t          = 1.4;   // espessura radial do lábio
lip_weld       = 0.8;   // quanto o lábio invade a metade frontal, em y e em
                        // raio. Sem isso ele encosta na casca só por uma face
                        // coincidente e sai como um anel solto no STL.

// Bossas de parafuso M2 (para inserto ou parafuso auto-atarraxante).
boss_r         = 3.2;
boss_hole      = 1.7;   // 1.7 p/ auto-atarraxante M2; 3.2 p/ inserto térmico M2
boss_dx        = 26;    // distância horizontal entre bossas (a partir do centro)
boss_dz        = 0;     // altura das bossas relativa ao centro do rosto

face_cz        = body_h * 0.60;  // centro do rosto (altura do display)

// =============================================================================
// Geometria do corpo
// =============================================================================
// O corpo é o casco convexo (hull) de 12 esferas em 3 "andares". Como o
// resultado é um hull de esferas, dá para obter o offset interno EXATO só
// reduzindo o raio de cada esfera em `wall` — sem minkowski (que é lentíssimo).

lobes = [
  // [ meia-largura x, meia-profundidade y, z do centro, raio ]
  [ body_w/2 - r_bot, body_d/2 - r_bot, r_bot * 0.72,          r_bot ],
  [ body_w/2 - r_mid, body_d/2 - r_mid, body_h * 0.44,         r_mid ],
  [ body_w * top_scale - r_top, body_d * top_scale - r_top,
                                        body_h - r_top,        r_top ]
];

module body_solid(grow = 0) {
  hull()
    for (l = lobes)
      for (sx = [-1, 1])
        for (sy = [-1, 1])
          translate([sx * max(l[0], 0.01), sy * max(l[1], 0.01), l[2]])
            sphere(r = l[3] + grow);
}

// Corpo com a base achatada e o rosto plano na frente (-Y).
module body_shaped(grow = 0) {
  difference() {
    body_solid(grow);
    translate([0, 0, -100]) cube([400, 400, 200], center = true);              // base
    translate([0, -200 - (face_y + grow), 0]) cube([400, 400, 400], center = true); // rosto
  }
}

module body_shell() {
  difference() {
    body_shaped(0);
    body_shaped(-wall);
  }
}

// =============================================================================
// Recortes e detalhes
// =============================================================================

// Janela do display: rasgo passante da área ativa + rebaixo para a placa.
module screen_cutouts() {
  // Rasgo passante (área ativa), com leve chanfro para a luz não "vinhetar".
  translate([0, -face_y - 1, face_cz + scr_active_dy])
    rotate([90, 0, 0])
      linear_extrude(height = wall + 3, center = false, scale = 0.94)
        square([scr_active + 1.0, scr_active + 1.0], center = true);

  // Rebaixo para a placa do display, por dentro.
  translate([0, -face_y + wall/2, face_cz])
    cube([scr_pcb_w + 2*scr_fit, wall + 2.2, scr_pcb_h + 2*scr_fit], center = true);
}

// Recorte do USB, no fundo da tampa traseira.
module usb_cutout() {
  translate([0, body_d/2, usb_z])
    rotate([90, 0, 0])
      linear_extrude(height = 30, center = true)
        offset(r = 1)
          square([usb_w - 2, usb_h - 2], center = true);
}

// Furos de ventilação discretos na base (o backlight esquenta um pouco).
module vents() {
  for (i = [-2 : 2])
    translate([i * 7, 0, -1])
      cylinder(r = 1.6, h = 8);
}

// Bossas de parafuso para prender o display, atrás do rosto.
module screen_bosses() {
  for (sx = [-1, 1])
    translate([sx * boss_dx/2, -face_y + wall, face_cz + boss_dz])
      rotate([-90, 0, 0])
        difference() {
          cylinder(r = boss_r, h = 5);
          translate([0, 0, -0.5]) cylinder(r = boss_hole/2, h = 6.5);
        }
}

// Duas abas onde as bordas da placa do ESP encostam (a fita dupla face vai
// aqui). Cada aba nasce na parede lateral e avança 3 mm por baixo da placa.
// Um trilho solto no meio da cavidade — sem tocar parede nenhuma — sairia
// como peça separada no STL.
module board_shelf() {
  shelf_w = brd_w + 2 * brd_fit;   // largura ocupada pela placa
  intersection() {
    body_shaped(-wall + lip_weld);        // morde a parede dos dois lados
    difference() {
      translate([0, split_y - 6, 14]) cube([2 * body_w, 3, 2], center = true);
      translate([0, split_y - 6, 14]) cube([shelf_w - 6, 5, 4], center = true);
    }
  }
}

// Lábio de encaixe. São duas faixas em y, e a diferença entre elas é o que
// mantém a peça inteira:
//   y > split_y  entra na tampa, rebaixado lip_fit para deslizar;
//   y < split_y  invade a metade frontal e morde a parede por lip_weld.
module lip() {
  // trecho que entra na tampa
  intersection() {
    difference() {
      body_shaped(-wall - lip_fit);
      body_shaped(-wall - lip_fit - lip_t);
    }
    translate([0, split_y + lip_h/2, 200])
      cube([400, lip_h, 400], center = true);
  }
  // trecho de solda, já dentro da metade frontal
  intersection() {
    difference() {
      body_shaped(-wall + lip_weld);
      body_shaped(-wall - lip_fit - lip_t);
    }
    translate([0, split_y - lip_weld/2, 200])
      cube([400, lip_weld, 400], center = true);
  }
}

// Bolsa da tampa que recebe o lábio. Tira só a faixa interna: a parede
// externa da tampa continua descendo até o plano de corte, senão a caixa
// montada fica com um vinco aberto de lip_h em toda a volta.
module lip_pocket() {
  intersection() {
    difference() {
      body_shaped(-wall);
      body_shaped(-wall - lip_fit - lip_t - 0.2);
    }
    translate([0, split_y + lip_h/2, 200])
      cube([400, lip_h + 0.4, 400], center = true);
  }
}

// =============================================================================
// Partes
// =============================================================================

module front_part() {
  difference() {
    union() {
      // Casca da frente: tudo com y < split_y.
      intersection() {
        body_shell();
        translate([0, split_y - 200, 200]) cube([400, 400, 400], center = true);
      }
      screen_bosses();
      board_shelf();
      lip();
    }
    screen_cutouts();
    vents();
  }
}

module back_part() {
  difference() {
    intersection() {
      body_shell();
      translate([0, split_y + 200, 200]) cube([400, 400, 400], center = true);
    }
    usb_cutout();
    vents();
    lip_pocket();
  }
}

// =============================================================================
// Saída
// =============================================================================

if (part == "front") {
  // Deitado com o rosto para baixo: janela sem suporte, melhor acabamento.
  rotate([-90, 0, 0]) translate([0, face_y, 0]) front_part();
} else if (part == "back") {
  rotate([90, 0, 0]) back_part();
} else if (part == "preview") {
  color("Cornsilk", 0.9) front_part();
  color("Peru",     0.9) back_part();
} else {
  translate([-body_w * 0.62, 0, 0]) rotate([-90, 0, 0]) translate([0, face_y, 0]) front_part();
  translate([ body_w * 0.62, 0, 0]) rotate([ 90, 0, 0]) back_part();
}
