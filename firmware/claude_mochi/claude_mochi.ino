// claude-mochi — olhos que indicam o consumo de tokens do Claude Code.
// Por padrao os olhos E a barra seguem o LIMITE DE 5 HORAS (a cota).
// Troque em OLHOS_METRICA / BARRA_METRICA.
//
// Placa   : ESP8266 (NodeMCU / Wemos D1 mini / ESP-12)
// Display : ST7789 1.54" 240x240 SPI (modulo de 7 pinos, com CS)
//
// DOIS MODOS DE LIGACAO (escolha um abaixo em LINK_SERIAL / LINK_WIFI):
//
//   Serial (padrao, recomendado)
//     O PC manda linhas pela USB: "ctx=42 win=63 state=busy\n".
//     Nao precisa de rede nenhuma. Funciona em Wi-Fi corporativo,
//     em rede de visitante, ou totalmente offline. A pilha Wi-Fi nem
//     sobe, entao sobra RAM para o display.
//     Do lado do PC quem fala com a porta e host/mochi-serial.py.
//
//   Wi-Fi
//     O ESP entra na sua rede como cliente e expoe um endpoint HTTP.
//     So use se o PC e o mochi estiverem na MESMA rede e o roteador
//     nao tiver isolamento de cliente (a maioria das redes de empresa
//     tem, e ai isso nao funciona).
//
// Protocolo serial: uma linha por atualizacao, pares chave=valor
// separados por espaco, terminada em \n. Chaves aceitas: ctx, win, state.

#define LINK_SERIAL 1
#define LINK_WIFI   0

#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>

// ESP8266WiFi.h entra nos DOIS modos: no modo serial o setup() ainda chama
// WiFi.mode(WIFI_OFF) / forceSleepBegin() para desligar o radio.
#include <ESP8266WiFi.h>

#if LINK_WIFI
  #include <ESP8266WebServer.h>
  #include <ESP8266mDNS.h>
  // So no modo Wi-Fi. Crie config.h ao lado deste arquivo com:
  //     #pragma once
  //     #define WIFI_SSID     "sua-rede-wifi"
  //     #define WIFI_PASSWORD "sua-senha"
  //     #define MDNS_NAME     "mochi"   // http://mochi.local
  // Fica fora do sketch de proposito: config.h esta no .gitignore, entao a
  // senha nao vai para o repositorio junto com o firmware.
  #include "config.h"
  ESP8266WebServer server(80);
#endif

// ---------------------------------------------------------------- pinagem ---
// Labels D* sao do NodeMCU / Wemos D1 mini. SCK e MOSI sao fixos no HW SPI.
//
// TFT_CS: os modulos ST7789 240x240 vem em duas variantes.
//   8 pinos -> tem CS: deixe D8 como esta e ligue o fio.
//   7 pinos -> NAO tem CS (fica em GND internamente): troque para -1
//              e nao ligue fio nenhum. Um pino livre de brinde.
// As duas funcionam: o display e o unico dispositivo no barramento SPI.
#define TFT_CS   D8   // GPIO15 — use -1 se o seu modulo nao tiver pino CS
#define TFT_DC   D1   // GPIO5
#define TFT_RST  D2   // GPIO4
// SCK  -> D5 (GPIO14)
// MOSI -> D7 (GPIO13)

// Backlight. O jeito mais simples e ligar BLK direto no 3V3 e deixar
// USE_BLK_PIN em 0 — um fio a menos e nada para dar errado. Coloque 1 se
// quiser controlar o brilho por software (ai ligue BLK no pino abaixo).
#define USE_BLK_PIN 0
#define TFT_BLK  D6   // GPIO12 (so usado se USE_BLK_PIN for 1)

// Animacao de boot: varre o contexto de 0 a 100% e volta, logo ao ligar.
// Serve para validar display e fiacao na protoboard SEM depender do PC.
#define BOOT_DEMO 1

Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);

// ------------------------------------------------------------------ cores ---
static const uint16_t C_FACE   = 0xFB26;  // laranja forte, o "rosto" do mochi (#FF6633)
// Matiz do clay da Anthropic (#D97757, H 15) mas com saturacao 100%. O clay
// puro tem so 63% de saturacao e sai lavado num painel retroiluminado.
// Outras opcoes do mesmo matiz: 0xFAE3 (#FF5E1A, mais forte),
// 0xFB63 (#FF6E1A, mais amarelado), 0xDBAA (#D97757, o clay original).
static const uint16_t C_EYE    = 0x18E3;  // quase preto
static const uint16_t C_OK     = 0x2E88;  // verde
static const uint16_t C_WARN   = 0xFCA0;  // ambar
static const uint16_t C_HOT    = 0xE0A3;  // vermelho
static const uint16_t C_SHINE  = 0xFFFF;  // brilho do olho
static const uint16_t C_TRACK  = 0x8A44;  // trilho da barra, laranja escuro (#8A4A22)
static const uint16_t C_SLEEP  = 0xD69A;  // olhos "dormindo" (sem dados)

// --------------------------------------------------------------- geometria ---
static const int16_t SCR       = 240;
static const int16_t EYE_CX_L  = 72;
static const int16_t EYE_CX_R  = 168;
static const int16_t EYE_CY    = 104;
static const int16_t EYE_RX    = 36;   // meia-largura do olho
static const int16_t EYE_RY    = 42;   // meia-altura maxima do olho
// A area que drawEye limpa e (EYE_RX+4)*2 por (EYE_RY+4)*2. Com os valores
// acima isso ocupa x 32..112 e 128..208, e y 58..150 — sem invadir a borda
// nem a barra (y 206). Se aumentar mais, confira essas contas antes.
// "?" do modo ask: fonte embutida 6x8, tamanho 6 -> 36x48 px. Precisa caber
// na faixa livre ACIMA dos olhos (y 0..58 — o comentario logo abaixo explica
// por que essa faixa e livre); tamanho 8 (64px) estourava e ficava sendo
// mordido pelo fillRect do drawEye toda vez que os olhos redesenhavam.
static const int16_t ASK_X     = 194;
static const int16_t ASK_Y     = 2;
static const int16_t ASK_W     = 36;
static const int16_t ASK_H     = 48;
static const int16_t BAR_Y     = 206;
static const int16_t BAR_H     = 10;
static const int16_t BAR_X     = 34;
static const int16_t BAR_W     = SCR - 2 * BAR_X;

// Sem noticias do PC por este tempo -> o mochi "cochila".
static const unsigned long IDLE_TIMEOUT_MS = 30000;

// ------------------------------------------------------------------ estado ---
struct State {
  int   ctx       = 0;       // % da janela de contexto usada
  int   win       = 0;       // % do limite de 5h usado
  char  mode[12]  = "idle";  // idle | busy | compact | ask
  bool  backlight = true;
  unsigned long lastPing = 0;
  bool  everPinged = false;
} st;

// -------------------------------------------------- o que a tela esta medindo ---
// Cada elemento escolhe sua metrica, de forma independente:
//   1 -> limite de 5 horas (st.win)
//   0 -> janela de contexto (st.ctx)
//
// Padrao: os DOIS na cota de 5h. Olhos e barra concordam sempre na cor, e a
// barra da o numero exato que a abertura da palpebra so sugere. A janela de
// contexto deixa de aparecer na tela — o firmware ainda aceita "ctx=" no
// protocolo, so nao desenha nada com ele.
//
// A cota e a metrica que interessa: ela responde "vou bater no limite hoje?".
// O contexto responde outra coisa, "o chat esta ficando grande?", e para isso
// o proprio Claude Code ja avisa quando o /compact chega.
//
// O preco: a cota anda devagar e, no Claude Desktop, so se atualiza quando um
// relatorio do /usage e colado no chat. Entao o mochi passa longos periodos
// parado — e o esperado, nao e defeito. Quem quiser um bicho mais agitado bota
// OLHOS_METRICA em 0 e ganha o contexto nos olhos, que anda o tempo todo.
#define OLHOS_METRICA 1
#define BARRA_METRICA 1

#if OLHOS_METRICA
  #define VAL_OLHOS (st.win)
#else
  #define VAL_OLHOS (st.ctx)
#endif

#if BARRA_METRICA
  #define VAL_BARRA (st.win)
#else
  #define VAL_BARRA (st.ctx)
#endif

static float  openNow    = 1.0f;   // abertura atual da palpebra (animada)
static float  openTarget = 1.0f;
static bool   blinking   = false;
static unsigned long blinkUntil = 0;
static unsigned long nextBlink  = 0;
static int    lastDrawnOlhos = -1;
static int    lastDrawnBarra = -1;
static int    lastEyeH     = -1;
static bool   lastCrossed  = false;
static bool   lastAsleep   = false;
static bool   lastAsking   = false;

// ------------------------------------------------------------------- utils ---
static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

// Mistura duas cores RGB565 com fator t em [0,1].
static uint16_t mix(uint16_t a, uint16_t b, float t) {
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  int ar = (a >> 11) & 0x1F, ag = (a >> 5) & 0x3F, ab = a & 0x1F;
  int br = (b >> 11) & 0x1F, bg = (b >> 5) & 0x3F, bb = b & 0x1F;
  int r  = ar + (int)((br - ar) * t);
  int g  = ag + (int)((bg - ag) * t);
  int bl = ab + (int)((bb - ab) * t);
  return (uint16_t)((r << 11) | (g << 5) | bl);
}

// Verde -> ambar -> vermelho conforme a porcentagem.
static uint16_t levelColor(int pct) {
  if (pct <= 60) return mix(C_OK, C_WARN, pct / 60.0f);
  return mix(C_WARN, C_HOT, (pct - 60) / 40.0f);
}

static bool isAsleep() {
  return !st.everPinged || (millis() - st.lastPing > IDLE_TIMEOUT_MS);
}

// ------------------------------------------------------------------ desenho ---

// Elipse cheia. O Adafruit_GFX so tem circulo, entao desenhamos por linhas.
static void fillEllipse(int16_t cx, int16_t cy, int16_t rx, int16_t ry, uint16_t color) {
  if (rx <= 0 || ry <= 0) return;
  for (int16_t dy = -ry; dy <= ry; dy++) {
    float k = 1.0f - (float)(dy * dy) / (float)(ry * ry);
    if (k < 0) k = 0;
    int16_t dx = (int16_t)(rx * sqrtf(k));
    if (dx > 0) tft.drawFastHLine(cx - dx, cy + dy, dx * 2, color);
  }
}

// Olho "tonto": um X, para a metrica dos olhos estourando ou compactacao.
static void drawCrossEye(int16_t cx, int16_t cy, uint16_t color) {
  const int16_t r = 28;
  for (int16_t o = -2; o <= 2; o++) {
    tft.drawLine(cx - r, cy - r + o, cx + r, cy + r + o, color);
    tft.drawLine(cx - r, cy + r + o, cx + r, cy - r + o, color);
  }
}

static void drawEye(int16_t cx, int16_t cy, int16_t ry, uint16_t iris,
                    bool crossed, bool asleep) {
  // Limpa apenas a area do olho (evita redesenhar a tela toda = sem flicker).
  tft.fillRect(cx - EYE_RX - 4, cy - EYE_RY - 4,
               (EYE_RX + 4) * 2, (EYE_RY + 4) * 2, C_FACE);

  if (asleep) {
    // Sem dados do PC: olhos fechados, tracinho suave.
    tft.fillRoundRect(cx - EYE_RX + 4, cy - 2, (EYE_RX - 4) * 2, 5, 2, C_SLEEP);
    return;
  }

  if (crossed) { drawCrossEye(cx, cy, C_EYE); return; }

  if (ry < 3) {
    tft.fillRoundRect(cx - EYE_RX, cy - 2, EYE_RX * 2, 5, 2, C_EYE);
    return;
  }

  fillEllipse(cx, cy, EYE_RX, ry, C_EYE);

  // Iris colorida pelo nivel, proporcional a abertura.
  int16_t irx = EYE_RX * 0.55f;
  int16_t iry = ry * 0.55f;
  if (iry >= 2) fillEllipse(cx, cy, irx, iry, iris);

  if (ry > EYE_RY * 0.45f) {
    tft.fillCircle(cx - EYE_RX / 3, cy - ry / 2, 5, C_SHINE);
  }
}

// Barra inferior = limite de 5 horas.
static void drawBar(int pct) {
  tft.fillRoundRect(BAR_X, BAR_Y, BAR_W, BAR_H, BAR_H / 2, C_TRACK);
  int w = (BAR_W * clampi(pct, 0, 100)) / 100;
  if (w >= BAR_H) {
    tft.fillRoundRect(BAR_X, BAR_Y, w, BAR_H, BAR_H / 2, levelColor(pct));
  } else if (w > 0) {
    tft.fillRect(BAR_X, BAR_Y, w, BAR_H, levelColor(pct));
  }
}

// >>> SPRITES GERADOS — NAO EDITE A MAO.
// Saem de firmware/gera_sprites.py, onde as poses sao desenhadas em
// ASCII. Mexeu numa pose? Rode o script: ele reescreve so este bloco,
// entre os marcadores >>> e <<<, e nao toca em mais nada do sketch.
static const int16_t CLAWD_W = 32;
static const int16_t CLAWD_H = 30;

// ---- ANDA_A --------------------------------------------------
// ................................
// ................................
// ................................
// ....########################....
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...#####ooooo######ooooo#####...
// ...#####ooooo######ooooo#####...
// ########ooooo######ooooo########
// ########ooooo######ooooo########
// ########ooooo######ooooo########
// ################################
// ################################
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ....########################....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####........####...........
// .....####........####...........
static const uint8_t CLAWD_ANDA_A_CORPO[] PROGMEM = {
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x0F, 0xFF, 0xFF, 0xF0, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0x1F, 0xFF, 0xFF, 0xF8, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
  0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
  0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0x1F, 0xFF, 0xFF, 0xF8, 0x0F, 0xFF, 0xFF, 0xF0, 0x07, 0x9E, 0x79, 0xE0,
  0x07, 0x9E, 0x79, 0xE0, 0x07, 0x9E, 0x79, 0xE0, 0x07, 0x9E, 0x79, 0xE0,
  0x07, 0x9E, 0x79, 0xE0, 0x07, 0x80, 0x78, 0x00, 0x07, 0x80, 0x78, 0x00,
};
static const uint8_t CLAWD_ANDA_A_OLHOS[] PROGMEM = {
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xF8, 0x1F, 0x00,
  0x00, 0xF8, 0x1F, 0x00, 0x00, 0xF8, 0x1F, 0x00, 0x00, 0xF8, 0x1F, 0x00,
  0x00, 0xF8, 0x1F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
};

// ---- ANDA_B --------------------------------------------------
// ................................
// ................................
// ....########################....
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...#####ooooo######ooooo#####...
// ...#####ooooo######ooooo#####...
// ########ooooo######ooooo########
// ########ooooo######ooooo########
// ########ooooo######ooooo########
// ################################
// ################################
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ....########################....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// ...........####........####.....
// ...........####........####.....
static const uint8_t CLAWD_ANDA_B_CORPO[] PROGMEM = {
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0F, 0xFF, 0xFF, 0xF0,
  0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
  0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x1F, 0xFF, 0xFF, 0xF8,
  0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0x0F, 0xFF, 0xFF, 0xF0, 0x07, 0x9E, 0x79, 0xE0, 0x07, 0x9E, 0x79, 0xE0,
  0x07, 0x9E, 0x79, 0xE0, 0x07, 0x9E, 0x79, 0xE0, 0x07, 0x9E, 0x79, 0xE0,
  0x07, 0x9E, 0x79, 0xE0, 0x00, 0x1E, 0x01, 0xE0, 0x00, 0x1E, 0x01, 0xE0,
};
static const uint8_t CLAWD_ANDA_B_OLHOS[] PROGMEM = {
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0xF8, 0x1F, 0x00, 0x00, 0xF8, 0x1F, 0x00,
  0x00, 0xF8, 0x1F, 0x00, 0x00, 0xF8, 0x1F, 0x00, 0x00, 0xF8, 0x1F, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
};

// ---- ACENA ---------------------------------------------------
// ............................###.
// ............................###.
// ............................###.
// ....###########################.
// ...############################.
// ...############################.
// ...############################.
// ...############################.
// ...#####ooooo######ooooo#######.
// ...#####ooooo######ooooo#######.
// ########ooooo######ooooo#######.
// ########ooooo######ooooo#######.
// ########ooooo######ooooo#######.
// ###############################.
// ###############################.
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ...##########################...
// ....########################....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
// .....####..####..####..####.....
static const uint8_t CLAWD_ACENA_CORPO[] PROGMEM = {
  0x00, 0x00, 0x00, 0x0E, 0x00, 0x00, 0x00, 0x0E, 0x00, 0x00, 0x00, 0x0E,
  0x0F, 0xFF, 0xFF, 0xFE, 0x1F, 0xFF, 0xFF, 0xFE, 0x1F, 0xFF, 0xFF, 0xFE,
  0x1F, 0xFF, 0xFF, 0xFE, 0x1F, 0xFF, 0xFF, 0xFE, 0x1F, 0xFF, 0xFF, 0xFE,
  0x1F, 0xFF, 0xFF, 0xFE, 0xFF, 0xFF, 0xFF, 0xFE, 0xFF, 0xFF, 0xFF, 0xFE,
  0xFF, 0xFF, 0xFF, 0xFE, 0xFF, 0xFF, 0xFF, 0xFE, 0xFF, 0xFF, 0xFF, 0xFE,
  0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8, 0x1F, 0xFF, 0xFF, 0xF8,
  0x1F, 0xFF, 0xFF, 0xF8, 0x0F, 0xFF, 0xFF, 0xF0, 0x07, 0x9E, 0x79, 0xE0,
  0x07, 0x9E, 0x79, 0xE0, 0x07, 0x9E, 0x79, 0xE0, 0x07, 0x9E, 0x79, 0xE0,
  0x07, 0x9E, 0x79, 0xE0, 0x07, 0x9E, 0x79, 0xE0, 0x07, 0x9E, 0x79, 0xE0,
};
static const uint8_t CLAWD_ACENA_OLHOS[] PROGMEM = {
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xF8, 0x1F, 0x00,
  0x00, 0xF8, 0x1F, 0x00, 0x00, 0xF8, 0x1F, 0x00, 0x00, 0xF8, 0x1F, 0x00,
  0x00, 0xF8, 0x1F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
};

static const uint8_t *const CLAWD_CORPO[] = {CLAWD_ANDA_A_CORPO, CLAWD_ANDA_B_CORPO, CLAWD_ACENA_CORPO};
static const uint8_t *const CLAWD_OLHOS[] = {CLAWD_ANDA_A_OLHOS, CLAWD_ANDA_B_OLHOS, CLAWD_ACENA_OLHOS};
static const uint8_t CLAWD_ANDA_A = 0, CLAWD_ANDA_B = 1, CLAWD_ACENA = 2;
// <<< SPRITES GERADOS

// -------------------------------------------- o clawd que anda sobre a barra ---
// Sinal de "esta trabalhando". Entrou no lugar do piscar acelerado: piscar mais
// rapido nao se le como trabalho, se le como nervosismo — e pior, mistura o
// canal dos olhos (que e a cota) com o canal do modo. Agora cada um diz uma
// coisa so: olhos = quanto ja gastou, clawd andando = esta rodando agora.
//
// Quem anda e o proprio claude-mochi em miniatura: corpo de bloco arredondado,
// dois olhos quadrados, quatro perninhas e dois toquinhos de braco.
//
// As poses vem do bloco de sprites logo acima, gerado por
// firmware/gera_sprites.py. Nao mexa nele na mao.
//
// Dois bitmaps por pose, nao um: CORPO pinta a silhueta inteira de escuro e
// OLHOS pinta os olhos por cima. Duas cores sem bitmap colorido e sem paleta.
//
// O sobe-e-desce da caminhada esta DENTRO dos sprites (a pose ANDA_B ja vem um
// pixel mais alta), nao no firmware. Assim a caixa a apagar e sempre a mesma.
static const int16_t WK_FEET = BAR_Y - 1;               // o pe toca a barra
static const int16_t WK_X0   = BAR_X;
static const int16_t WK_X1   = BAR_X + BAR_W - CLAWD_W;
static const int16_t WK_STEP = 4;
static const unsigned long WK_MS = 80;                  // ~12 passos/s
static const uint8_t WK_ACENOS = 10;                    // ticks acenando na ponta

static int16_t       wkX     = -1;          // -1 = nao esta na tela
static int8_t        wkDir   = 1;
static uint16_t      wkPasso = 0;
static uint8_t       wkAcena = 0;
static unsigned long wkNext  = 0;

// A caixa vai de WK_FEET-CLAWD_H+1 a WK_FEET (184..205 com BAR_Y=206): nao
// encosta na barra (206) nem na area dos olhos (que termina em 150).
// Mexeu em BAR_Y ou no tamanho do sprite? Refaca esta conta.
static void eraseWalker(int16_t x) {
  if (x < 0) return;
  tft.fillRect(x, WK_FEET - CLAWD_H + 1, CLAWD_W, CLAWD_H, C_FACE);
}

static void drawWalker(int16_t x, uint8_t pose) {
  const int16_t y = WK_FEET - CLAWD_H + 1;
  tft.drawBitmap(x, y, CLAWD_CORPO[pose], CLAWD_W, CLAWD_H, C_EYE);
  tft.drawBitmap(x, y, CLAWD_OLHOS[pose], CLAWD_W, CLAWD_H, C_SHINE);
}

#if BOOT_DEMO
// Varre 0 -> 100 -> 0% de contexto ao ligar. Se isto animar, display e
// fiacao estao corretos; nada disso depende do PC ou da rede.
static void bootDemo() {
  for (int step = 0; step <= 200; step += 4) {
    const int      pct  = (step <= 100) ? step : (200 - step);
    const float    open = 1.0f - 0.72f * (pct / 100.0f);
    const int16_t  h    = (int16_t)(EYE_RY * open);
    const uint16_t iris = levelColor(pct);
    drawEye(EYE_CX_L, EYE_CY, h, iris, false, false);
    drawEye(EYE_CX_R, EYE_CY, h, iris, false, false);
    drawBar(pct);
    delay(10);
  }
  // Termina no estado "cochilando", esperando o PC.
  drawEye(EYE_CX_L, EYE_CY, 0, C_EYE, false, true);
  drawEye(EYE_CX_R, EYE_CY, 0, C_EYE, false, true);
  drawBar(0);
}
#endif

// =============================================================== ligacao ====

// Aplica um par "chave=valor".
static void applyKV(char *kv) {
  char *eq = strchr(kv, '=');
  if (!eq) return;
  *eq = '\0';
  const char *k = kv;
  const char *v = eq + 1;
  if      (!strcmp(k, "ctx"))   st.ctx = clampi(atoi(v), 0, 100);
  else if (!strcmp(k, "win"))   st.win = clampi(atoi(v), 0, 100);
  else if (!strcmp(k, "state")) {
    strncpy(st.mode, v, sizeof(st.mode) - 1);
    st.mode[sizeof(st.mode) - 1] = '\0';
  }
}

// Aplica uma linha inteira: "ctx=42 win=63 state=busy".
static void applyLine(char *line) {
  for (char *tok = strtok(line, " \t"); tok; tok = strtok(NULL, " \t")) applyKV(tok);
  st.lastPing = millis();
  st.everPinged = true;
}

#if LINK_SERIAL
static char    rxbuf[96];
static uint8_t rxlen = 0;

static void pollSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (rxlen) {
        rxbuf[rxlen] = '\0';
        applyLine(rxbuf);
        rxlen = 0;
        Serial.println("ok");   // eco para a ponte saber que estamos vivos
      }
    } else if (rxlen < sizeof(rxbuf) - 1) {
      rxbuf[rxlen++] = c;
    } else {
      rxlen = 0;               // linha absurda: descarta
    }
  }
}
#endif

#if LINK_WIFI
static void handleTokens() {
  char line[96];
  snprintf(line, sizeof(line), "ctx=%s win=%s state=%s",
           server.hasArg("ctx")   ? server.arg("ctx").c_str()   : "",
           server.hasArg("win")   ? server.arg("win").c_str()   : "",
           server.hasArg("state") ? server.arg("state").c_str() : "");
  applyLine(line);
  server.send(200, "text/plain", "ok");
}

static void handleState() {
  char buf[176];
  snprintf(buf, sizeof(buf),
           "{\"ctx\":%d,\"win\":%d,\"mode\":\"%s\",\"backlight\":%s,\"uptime_s\":%lu}",
           st.ctx, st.win, st.mode, st.backlight ? "true" : "false", millis() / 1000);
  server.send(200, "application/json", buf);
}

static void handleBacklight() {
  st.backlight = server.arg("on") != "0";
#if USE_BLK_PIN
  analogWrite(TFT_BLK, st.backlight ? 1023 : 0);
#endif
  server.send(200, "text/plain", "ok");
}

static void handleRoot() {
  char buf[420];
  snprintf(buf, sizeof(buf),
           "<!doctype html><meta name=viewport content='width=device-width'>"
           "<body style='font-family:system-ui;background:#14110f;color:#f4f1ea;padding:24px'>"
           "<h2>claude-mochi</h2><p>contexto: <b>%d%%</b><br>limite 5h: <b>%d%%</b><br>"
           "modo: <b>%s</b><br>ip: %s</p></body>",
           st.ctx, st.win, st.mode, WiFi.localIP().toString().c_str());
  server.send(200, "text/html", buf);
}

static void startWifi() {
  tft.setTextColor(C_EYE);
  tft.setTextSize(2);
  tft.setCursor(20, 100);
  tft.print("conectando");

  WiFi.mode(WIFI_STA);
  WiFi.hostname(MDNS_NAME);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 80 && WiFi.status() != WL_CONNECTED; i++) delay(250);

  tft.fillScreen(C_FACE);
  tft.setTextSize(1);
  tft.setCursor(10, 90);
  if (WiFi.status() == WL_CONNECTED) {
    tft.print("http://"); tft.print(MDNS_NAME); tft.println(".local");
    tft.setCursor(10, 106);
    tft.print(WiFi.localIP());
    if (MDNS.begin(MDNS_NAME)) MDNS.addService("http", "tcp", 80);
  } else {
    tft.print("wifi falhou - confira config.h");
  }
  delay(2500);

  server.on("/", handleRoot);
  server.on("/tokens", handleTokens);
  server.on("/state", handleState);
  server.on("/backlight", handleBacklight);
  server.begin();
}
#endif

// ------------------------------------------------------------------ setup ---

void setup() {
  Serial.begin(115200);

#if USE_BLK_PIN
  pinMode(TFT_BLK, OUTPUT);
  analogWrite(TFT_BLK, 1023);
#endif

  tft.init(240, 240);
  tft.setSPISpeed(40000000);  // se a imagem sair com ruido, baixe para 20000000
  tft.setRotation(1);         // ajuste 0..3 conforme a orientacao do seu modulo
  tft.fillScreen(C_FACE);

#if BOOT_DEMO
  bootDemo();
#endif

#if LINK_WIFI
  startWifi();
#endif

#if LINK_SERIAL && !LINK_WIFI
  // Sem Wi-Fi: desliga o radio de vez. Economiza ~20 mA e libera RAM.
  WiFi.mode(WIFI_OFF);
  WiFi.forceSleepBegin();
  delay(1);
  Serial.println("mochi pronto");
#endif

  randomSeed(micros());
  nextBlink = millis() + 3000;
}

// ------------------------------------------------------------------- loop ---

void loop() {
#if LINK_SERIAL
  pollSerial();
#endif
#if LINK_WIFI
  server.handleClient();
  MDNS.update();
#endif

  const unsigned long now = millis();
  const bool asleep = isAsleep();

  // Piscar so para o bicho nao parecer morto. Quem diz "esta trabalhando" e o
  // clawd andando la embaixo, nao a frequencia da piscada.
  const bool busy = (strcmp(st.mode, "busy") == 0);
  if (!blinking && now >= nextBlink) {
    blinking = true;
    blinkUntil = now + 110;
  }
  if (blinking && now >= blinkUntil) {
    blinking = false;
    nextBlink = now + random(2800, 6000);
  }

  // Alvo de abertura: 0% = arregalado, 100% = quase fechado.
  openTarget = 1.0f - 0.72f * (VAL_OLHOS / 100.0f);
  if (blinking) openTarget = 0.0f;

  // Suavizacao exponencial para a animacao nao ficar dura.
  openNow += (openTarget - openNow) * 0.28f;

  // Olho de tonto: a metrica dos olhos estourando, ou uma compactacao em curso.
  const bool     crossed = (VAL_OLHOS >= 95) || (strcmp(st.mode, "compact") == 0);
  const int16_t  eyeH    = (int16_t)(EYE_RY * openNow);
  const uint16_t iris    = levelColor(VAL_OLHOS);

  if (eyeH != lastEyeH || crossed != lastCrossed ||
      VAL_OLHOS != lastDrawnOlhos || asleep != lastAsleep) {
    drawEye(EYE_CX_L, EYE_CY, eyeH, iris, crossed, asleep);
    drawEye(EYE_CX_R, EYE_CY, eyeH, iris, crossed, asleep);
    lastEyeH       = eyeH;
    lastCrossed    = crossed;
    lastDrawnOlhos = VAL_OLHOS;
    lastAsleep     = asleep;
  }

  // "?" no canto: o Claude parou e esta esperando uma resposta sua.
  // ponytail: so o "?", sem os olhos para cima da proposta do SVG — o
  // ponto de interrogacao ja se le de longe e nao mexe no drawEye.
  const bool asking = (strcmp(st.mode, "ask") == 0) && !asleep;
  if (asking != lastAsking) {
    if (asking) {
      tft.setTextColor(C_EYE);
      tft.setTextSize(6);
      tft.setCursor(ASK_X, ASK_Y);
      tft.print('?');
    } else {
      tft.fillRect(ASK_X, ASK_Y, ASK_W, ASK_H, C_FACE);
    }
    lastAsking = asking;
  }

  if (VAL_BARRA != lastDrawnBarra) {
    drawBar(VAL_BARRA);
    lastDrawnBarra = VAL_BARRA;
  }

  // Clawd andando na barra enquanto o Claude trabalha. Cochilando ele some: um
  // bicho andando sem ninguem do outro lado do cabo estaria mentindo.
  if (busy && !asleep) {
    if (now >= wkNext) {
      wkNext = now + WK_MS;
      eraseWalker(wkX);
      if (wkX < 0) {                       // entrando em cena
        wkX = WK_X0; wkDir = 1; wkPasso = 0; wkAcena = 0;
      } else if (wkAcena) {                // parado acenando na ponta
        if (--wkAcena == 0) wkDir = -wkDir;
      } else {
        wkX += wkDir * WK_STEP;
        wkPasso++;
        if      (wkX >= WK_X1) { wkX = WK_X1; wkAcena = WK_ACENOS; }
        else if (wkX <= WK_X0) { wkX = WK_X0; wkAcena = WK_ACENOS; }
      }
      // Troca de pose a cada DOIS passos: a 12 passos/s, alternar todo quadro
      // vira tremedeira em vez de caminhada.
      const uint8_t pose = wkAcena ? CLAWD_ACENA
                         : ((wkPasso >> 1) & 1 ? CLAWD_ANDA_B : CLAWD_ANDA_A);
      drawWalker(wkX, pose);
    }
  } else if (wkX >= 0) {
    eraseWalker(wkX);
    wkX = -1;
  }

  delay(16);  // ~60 fps
}
