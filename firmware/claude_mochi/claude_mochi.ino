// claude-mochi — olhos que indicam o consumo de tokens do Claude Code.
//
// Placa   : ESP8266 (NodeMCU / Wemos D1 mini / ESP-12)
// Display : ST7789 1.54" 240x240 SPI (modulo de 7 pinos, com CS)
//
// O ESP entra na sua rede Wi-Fi como cliente (nao cria hotspot) e expoe:
//   GET /              -> pagina de status
//   GET /state         -> JSON com o estado atual
//   GET /tokens?ctx=42&win=63&state=busy
//   GET /backlight?on=0|1
//
// O script host/statusline-mochi.sh chama /tokens a cada mensagem do Claude Code.

#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>

#include "config.h"

// ---------------------------------------------------------------- pinagem ---
// Labels D* sao do NodeMCU / Wemos D1 mini. SCK e MOSI sao fixos no HW SPI.
#define TFT_CS   D8   // GPIO15
#define TFT_DC   D1   // GPIO5
#define TFT_RST  D2   // GPIO4
#define TFT_BLK  D6   // GPIO12 (backlight via PWM; ou ligue VCC do BLK em 3V3)
// SCK  -> D5 (GPIO14)
// MOSI -> D7 (GPIO13)

Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);
ESP8266WebServer server(80);

// ------------------------------------------------------------------ cores ---
static const uint16_t C_FACE   = 0xF71C;  // creme, o "rosto" do mochi
static const uint16_t C_EYE    = 0x18E3;  // quase preto
static const uint16_t C_OK     = 0x2E88;  // verde
static const uint16_t C_WARN   = 0xFCA0;  // ambar
static const uint16_t C_HOT    = 0xE0A3;  // vermelho
static const uint16_t C_SHINE  = 0xFFFF;  // brilho do olho
static const uint16_t C_TRACK  = 0xE71C;  // trilho da barra

// --------------------------------------------------------------- geometria ---
static const int16_t SCR       = 240;
static const int16_t EYE_CX_L  = 78;
static const int16_t EYE_CX_R  = 162;
static const int16_t EYE_CY    = 104;
static const int16_t EYE_RX    = 30;   // meia-largura do olho
static const int16_t EYE_RY    = 34;   // meia-altura maxima do olho
static const int16_t BAR_Y     = 206;
static const int16_t BAR_H     = 10;
static const int16_t BAR_X     = 34;
static const int16_t BAR_W     = SCR - 2 * BAR_X;

// ------------------------------------------------------------------ estado ---
struct State {
  int   ctx      = 0;      // % da janela de contexto usada
  int   win      = 0;      // % do limite de 5h usado
  char  mode[12] = "idle";  // idle | busy | compact
  bool  backlight = true;
  unsigned long lastPing = 0;
} st;

static float  openNow   = 1.0f;   // abertura atual da palpebra (animada)
static float  openTarget = 1.0f;
static bool   blinking  = false;
static unsigned long blinkUntil = 0;
static unsigned long nextBlink  = 0;
static int    lastDrawnCtx = -1;
static int    lastDrawnWin = -1;
static int    lastEyeH     = -1;
static bool   lastCrossed  = false;

// ------------------------------------------------------------------- utils ---
static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

// Mistura duas cores RGB565 com fator t em [0,1].
static uint16_t mix(uint16_t a, uint16_t b, float t) {
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  int ar = (a >> 11) & 0x1F, ag = (a >> 5) & 0x3F, ab = a & 0x1F;
  int br = (b >> 11) & 0x1F, bg = (b >> 5) & 0x3F, bb = b & 0x1F;
  int r = ar + (int)((br - ar) * t);
  int g = ag + (int)((bg - ag) * t);
  int bl = ab + (int)((bb - ab) * t);
  return (uint16_t)((r << 11) | (g << 5) | bl);
}

// Verde -> ambar -> vermelho conforme a porcentagem.
static uint16_t levelColor(int pct) {
  if (pct <= 60) return mix(C_OK, C_WARN, pct / 60.0f);
  return mix(C_WARN, C_HOT, (pct - 60) / 40.0f);
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

// Olho "tonto": um X, para contexto quase estourado ou compactacao.
static void drawCrossEye(int16_t cx, int16_t cy, uint16_t color) {
  const int16_t r = 22;
  for (int16_t o = -2; o <= 2; o++) {
    tft.drawLine(cx - r, cy - r + o, cx + r, cy + r + o, color);
    tft.drawLine(cx - r, cy + r + o, cx + r, cy - r + o, color);
  }
}

static void drawEye(int16_t cx, int16_t cy, int16_t ry, uint16_t iris, bool crossed) {
  // Limpa apenas a area do olho (evita redesenhar a tela toda = sem flicker).
  tft.fillRect(cx - EYE_RX - 4, cy - EYE_RY - 4,
               (EYE_RX + 4) * 2, (EYE_RY + 4) * 2, C_FACE);

  if (crossed) { drawCrossEye(cx, cy, C_EYE); return; }

  if (ry < 3) {
    // Olho fechado: um traco.
    tft.fillRoundRect(cx - EYE_RX, cy - 2, EYE_RX * 2, 5, 2, C_EYE);
    return;
  }

  fillEllipse(cx, cy, EYE_RX, ry, C_EYE);

  // Iris colorida pelo nivel, proporcional a abertura.
  int16_t irx = EYE_RX * 0.55f;
  int16_t iry = ry * 0.55f;
  if (iry >= 2) fillEllipse(cx, cy, irx, iry, iris);

  // Brilho.
  if (ry > EYE_RY * 0.45f) {
    tft.fillCircle(cx - EYE_RX / 3, cy - ry / 2, 4, C_SHINE);
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

static void redrawAll() {
  tft.fillScreen(C_FACE);
  lastDrawnCtx = -1;
  lastDrawnWin = -1;
  lastEyeH = -1;
}

// ------------------------------------------------------------------ web ---

static void handleTokens() {
  if (server.hasArg("ctx")) st.ctx = clampi(server.arg("ctx").toInt(), 0, 100);
  if (server.hasArg("win")) st.win = clampi(server.arg("win").toInt(), 0, 100);
  if (server.hasArg("state")) {
    strncpy(st.mode, server.arg("state").c_str(), sizeof(st.mode) - 1);
    st.mode[sizeof(st.mode) - 1] = '\0';
  }
  st.lastPing = millis();
  server.send(200, "text/plain", "ok");
}

static void handleState() {
  char buf[160];
  snprintf(buf, sizeof(buf),
           "{\"ctx\":%d,\"win\":%d,\"mode\":\"%s\",\"backlight\":%s,\"uptime_s\":%lu}",
           st.ctx, st.win, st.mode, st.backlight ? "true" : "false", millis() / 1000);
  server.send(200, "application/json", buf);
}

static void handleBacklight() {
  st.backlight = server.arg("on") != "0";
  analogWrite(TFT_BLK, st.backlight ? 1023 : 0);
  server.send(200, "text/plain", "ok");
}

static void handleRoot() {
  char buf[420];
  snprintf(buf, sizeof(buf),
           "<!doctype html><meta name=viewport content='width=device-width'>"
           "<body style='font-family:system-ui;background:#14110f;color:#f4f1ea;padding:24px'>"
           "<h2>claude-mochi</h2><p>contexto: <b>%d%%</b><br>limite 5h: <b>%d%%</b><br>"
           "modo: <b>%s</b><br>ip: %s</p>"
           "<p><a style='color:#d97757' href='/backlight?on=0'>apagar</a> &middot; "
           "<a style='color:#d97757' href='/backlight?on=1'>acender</a></p></body>",
           st.ctx, st.win, st.mode, WiFi.localIP().toString().c_str());
  server.send(200, "text/html", buf);
}

// ------------------------------------------------------------------ setup ---

void setup() {
  Serial.begin(115200);

  pinMode(TFT_BLK, OUTPUT);
  analogWrite(TFT_BLK, 1023);

  tft.init(240, 240);
  tft.setSPISpeed(40000000);  // se a imagem sair com ruido, baixe para 20000000
  tft.setRotation(2);         // ajuste 0..3 conforme a orientacao do seu modulo
  tft.fillScreen(C_FACE);

  // Tela de boot: mostra o IP para voce achar o mochi na rede.
  tft.setTextColor(C_EYE);
  tft.setTextSize(2);
  tft.setCursor(20, 100);
  tft.print("conectando");

  WiFi.mode(WIFI_STA);
  WiFi.hostname(MDNS_NAME);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 80 && WiFi.status() != WL_CONNECTED; i++) {
    delay(250);
    Serial.print('.');
  }

  tft.fillScreen(C_FACE);
  tft.setCursor(10, 90);
  tft.setTextSize(1);
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println(WiFi.localIP());
    tft.print("http://");
    tft.print(MDNS_NAME);
    tft.println(".local");
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

  redrawAll();
  nextBlink = millis() + 3000;
}

// ------------------------------------------------------------------- loop ---

void loop() {
  server.handleClient();
  MDNS.update();

  const unsigned long now = millis();

  // Piscar: mais rapido enquanto o Claude esta trabalhando.
  const bool busy = (strcmp(st.mode, "busy") == 0);
  if (!blinking && now >= nextBlink) {
    blinking = true;
    blinkUntil = now + 110;
  }
  if (blinking && now >= blinkUntil) {
    blinking = false;
    nextBlink = now + (busy ? random(900, 2000) : random(2800, 6000));
  }

  // Alvo de abertura: 0% de contexto = arregalado, 100% = quase fechado.
  openTarget = 1.0f - 0.72f * (st.ctx / 100.0f);
  if (blinking) openTarget = 0.0f;

  // Suavizacao exponencial para a animacao nao ficar dura.
  openNow += (openTarget - openNow) * 0.28f;

  const bool crossed = (st.ctx >= 95) || (strcmp(st.mode, "compact") == 0);
  const int16_t eyeH = (int16_t)(EYE_RY * openNow);
  const uint16_t iris = levelColor(st.ctx);

  if (eyeH != lastEyeH || crossed != lastCrossed || st.ctx != lastDrawnCtx) {
    drawEye(EYE_CX_L, EYE_CY, eyeH, iris, crossed);
    drawEye(EYE_CX_R, EYE_CY, eyeH, iris, crossed);
    lastEyeH = eyeH;
    lastCrossed = crossed;
    lastDrawnCtx = st.ctx;
  }

  if (st.win != lastDrawnWin) {
    drawBar(st.win);
    lastDrawnWin = st.win;
  }

  delay(16);  // ~60 fps
}
