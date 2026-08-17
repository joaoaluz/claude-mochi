// ---------------------------------------------------------------
//  claude-mochi / boards.scad
//  Especificacoes das placas suportadas.
// ---------------------------------------------------------------
//  Sistema de coordenadas local da placa (visto de cima):
//    origem = canto inferior-esquerdo do PCB
//    X = comprimento, Y = largura, Z = 0 na face inferior do PCB
//
//  Para adicionar uma placa nova basta acrescentar uma linha em
//  cada funcao abaixo usando o mesmo nome.
// ---------------------------------------------------------------

// [comprimento, largura, espessura do PCB]
function board_size(n) =
    n == "pi_zero" ? [65, 30, 1.2] :
    n == "pico"    ? [51, 21, 1.0] : undef;

// Centros dos furos de fixacao, em coordenadas locais.
function board_holes(n) =
    n == "pi_zero" ? [[3.5, 3.5], [61.5, 3.5], [3.5, 26.5], [61.5, 26.5]] :
    n == "pico"    ? [[2.0, 4.8], [49.0, 4.8], [2.0, 16.2], [49.0, 16.2]] : undef;

// Furo-guia do parafuso auto-atarraxante que prende a placa.
// pi_zero = M2.5, pico = M2.
function board_pilot(n) =
    n == "pi_zero" ? 2.1 :
    n == "pico"    ? 1.7 : undef;

// Raio externo do espacador impresso sob a placa.
function board_standoff_r(n) =
    n == "pi_zero" ? 2.7 :
    n == "pico"    ? 2.3 : undef;

// Aberturas na parede. Cada porta e:
//   [rotulo, [x, y] na borda do PCB, normal local, largura, altura,
//    z do centro em relacao ao TOPO do PCB]
function board_ports(n) =
    n == "pi_zero" ? [
        ["usb-pwr",   [54.0,  0], [ 0, -1], 13, 9,  3.0],
        ["usb-data",  [41.4,  0], [ 0, -1], 13, 9,  3.0],
        ["mini-hdmi", [12.4,  0], [ 0, -1], 14, 8,  3.0],
        ["microsd",   [ 0.0, 15], [-1,  0], 16, 6, -2.0]
    ] :
    n == "pico" ? [
        ["usb",       [ 0.0, 10.5], [-1, 0], 13, 9, 3.0]
    ] : undef;

// Portas abertas por padrao.
function board_open_ports(n) =
    n == "pi_zero" ? ["usb-pwr", "microsd"] :
    n == "pico"    ? ["usb"] : undef;

// Rotacao padrao da placa dentro da carcaca, em graus.
// Escolhida para o cabo de alimentacao sair por tras (pi_zero)
// ou pela lateral esquerda (pico).
function board_rot_default(n) =
    n == "pi_zero" ? 180 :
    n == "pico"    ? 0 : undef;

// Dimensoes externas sugeridas do corpo [largura, profundidade, altura].
function board_shell(n) =
    n == "pi_zero" ? [94, 64, 68] :
    n == "pico"    ? [76, 52, 56] : undef;
