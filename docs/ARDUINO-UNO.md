# Arduino Uno — dá para usar?

**Resumo: dá, mas é um downgrade em todos os eixos contra um ESP8266.** Este
documento existe porque a pergunta aparece sempre. Se você tem um NodeMCU ou
Wemos D1 mini na gaveta, use ele e ignore esta página.

Os números abaixo são de uma compilação real (`arduino:avr:uno`, core 1.8.6,
Adafruit GFX 1.11.9 + ST7789 1.10.3), não estimativa.

## O que não é problema

```
Sketch uses 17332 bytes (53%) of program storage space. Maximum is 32256 bytes.
Global variables use 623 bytes (30%) of dynamic memory, leaving 1425 bytes.
```

Cabe com folga. O medo comum — "240×240 não cabe em 2 KB de RAM" — não se
aplica: um framebuffer seriam 115 KB, mas o `Adafruit_ST7789` desenha direto no
display e nunca aloca isso. `sqrtf`, `strtok` e `millis()` existem no AVR.

O reset por DTR ao abrir a porta serial também acontece no Uno, então a razão de
existir do `host/mochi-serial.py` (abrir a porta uma vez só) continua valendo
igual.

## O que é problema

**1. Lógica de 5 V — o bloqueio de verdade.** O Uno chuta 5 V nos pinos e o
ST7789 é 3,3 V. Ligar direto degrada e eventualmente mata o display. São **5
linhas** a converter: SCK, MOSI, DC, CS e RST. (MISO não é usado — o firmware
nunca lê do display.)

**2. O rail de 3V3 do Uno R3 entrega só ~50 mA.** O ST7789 com backlight puxa
20–40 mA. Funciona, mas fica no limite, e é justamente o backlight ligado no
3V3 — como o guia da protoboard recomenda — que consome.

**3. Velocidade.** O AVR trava o SPI em `F_CPU/2` = 8 MHz contra os 40 MHz do
ESP8266, e roda a 16 MHz contra 80. Cada frame redesenha ~37 KB de pixels (as
duas caixas dos olhos), o que dá algo em torno de 45–60 ms por frame:
**~16–20 fps em vez dos 60** que o `delay(16)` do loop mira. A animação roda,
só que perceptivelmente mais dura. A animação de boot passa de ~1 s para ~3 s.

**4. Sem modo Wi-Fi.** O bloco `LINK_WIFI` deixa de existir. No modo serial,
que é o padrão, isso não muda nada.

## Convertendo 5 V → 3,3 V

Três saídas, da melhor para a mais improvisada.

### Opção A — módulo conversor de nível (recomendado)

Um módulo bidirecional de 8 canais com **TXS0108E**, ou de 4 canais com
**TXB0104**. É a solução limpa: alimenta com 5 V de um lado, 3,3 V do outro, e
passa as 5 linhas sem pensar. Barato e fácil de achar.

> ⚠️ Evite os módulos de 4 canais baseados em **MOSFET + resistor de pull-up**
> (os verdinhos de I²C). Eles são feitos para barramento aberto-dreno em
> centenas de kHz e não seguram SPI a 8 MHz.

### Opção B — CI buffer 74HC4050 / CD4050B

Um hex buffer (6 canais, cobre as 5 linhas com uma sobrando) **alimentado com
3,3 V**. As entradas dele toleram sinal acima do VDD, que é exatamente o truque
que queremos. Unidirecional 5 V → 3,3 V, que é tudo de que precisamos aqui.

### Opção C — divisores resistivos (sem comprar nada)

Se você já tem resistores, funciona. Um divisor por linha:

```
  pino do Uno (5 V) ──┬── R1 (1 kΩ) ──┬── pino do display (3,3 V)
                      │               │
                                      R2 (2 kΩ)
                                      │
                                     GND
```

`5 V × 2k/(1k+2k) = 3,33 V`. Não tem 2 kΩ? Dois de 1 kΩ em série resolvem.
1,8 kΩ + 3,3 kΩ também serve (`3,23 V`).

São **cinco** divisores, ou seja 10 resistores — é o que torna esta opção
chata na protoboard. A impedância de saída fica em ~667 Ω, o que a 8 MHz ainda
é tranquilo com jumpers curtos; se a imagem sair com ruído, encurte os fios ou
baixe o SPI para 4 MHz.

## Ligação

| Display ST7789 | Uno | Passa por conversor? |
|---|---|---|
| SCK / CLK | 13 | **sim** |
| SDA / MOSI | 11 | **sim** |
| DC | 9 | **sim** |
| CS | 10 | **sim** |
| RST | 8 | **sim** |
| BLK | 3V3 (ou pino 6) | não |
| VCC | 3V3 | não |
| GND | GND | não |

Se o 3V3 do Uno não der conta do display, alimente-o por um regulador
AMS1117-3.3 a partir do 5 V — **e junte os GNDs**.

## Ajustes no firmware

O `.ino` mira ESP8266: os labels `D8`/`D1`/`D2` não existem no AVR,
`analogWrite` é de 8 bits em vez de 10, e o `WiFi.forceSleepBegin()` não existe.
Troque o bloco de pinagem por:

```cpp
#define TFT_CS   10
#define TFT_DC   9
#define TFT_RST  8
#define TFT_BLK  6
#define BLK_MAX  255          // no ESP8266 seria 1023
```

E no `setup()`, apague as três linhas de desligar o rádio
(`WiFi.mode(WIFI_OFF)` e as duas seguintes) e baixe o SPI:

```cpp
tft.setSPISpeed(8000000);     // teto do AVR: F_CPU/2
```

Onde houver `analogWrite(TFT_BLK, 1023)`, use `BLK_MAX` — `1023` num AVR estoura
os 8 bits e o backlight se comporta de forma errada.
