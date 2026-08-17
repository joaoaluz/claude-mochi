# claude-mochi

Um mochi de mesa cujos **olhos indicam o consumo de tokens do Claude Code**.

Quanto mais a janela de contexto enche, mais os olhos se fecham e mais quente
fica a cor da íris — verde → âmbar → vermelho. Uma barrinha embaixo mostra o
limite de 5 horas. Passou de 95% de contexto (ou rodou `/compact`), o mochi
fica de olhos tontos (`X_X`). Sem notícias do PC por 30 s, ele cochila.

Inspirado no [clawd-mochi](https://github.com/yousifamanuel/clawd-mochi) do
Yousif Amanuel — mesma ideia de hardware, mas ligado ao Claude Code em vez de
funcionar offline por um hotspot.

> Projeto independente de fã, sem vínculo com a Anthropic.

---

**Começando do zero?** Vá direto para **[docs/PROTOBOARD.md](docs/PROTOBOARD.md)** —
montagem na protoboard, sem case e sem solda no circuito, com um teste em cada
etapa. O firmware roda uma animação de boot que valida display e fiação sem
depender do PC.

**O que aparece na tela:** [`docs/tela/tela-mochi.svg`](docs/tela/tela-mochi.svg) —
todas as telas em escala 1:1 (rampa de contexto, piscar, cochilar, `X_X`) mais uma
proposta de expressões vindas dos hooks. O desenho é gerado por
`docs/tela/gera_svg.py`, que copia as constantes e a matemática inteira do
`.ino`; mexeu no firmware, rode o script de novo.

---

## Como funciona

A **status line** do Claude Code roda a cada mensagem do assistente e recebe um
JSON no stdin que já traz tudo pronto:

```json
"context_window": { "used_percentage": 72, "context_window_size": 200000 },
"rate_limits":    { "five_hour": { "used_percentage": 41 } },
"cost":           { "total_cost_usd": 1.2345 }
```

**Por que não usar a API ou um scraper da página de usage:** a Usage & Cost
Admin API exige uma *Admin API key* (`sk-ant-admin01-…`), que só existe para
organizações do Console — a documentação diz explicitamente que *"the Admin API
is unavailable for individual accounts"*. Além disso ela mede o consumo da API
de desenvolvedor, não o da assinatura Pro/Max, e os dados chegam com ~5 min de
atraso em buckets de 1m/1h/1d. A status line é instantânea, local, sem chave e
funciona em qualquer tipo de conta.

---

## Escolha a ligação: serial ou Wi-Fi

O firmware suporta as duas. Escolha no topo do `.ino` (`LINK_SERIAL` /
`LINK_WIFI`) e na variável `MOCHI_LINK` do lado do PC.

### Serial pelo USB — **padrão e recomendado**

```
Claude Code ──stdin──▶ statusline ──escreve arquivo──▶ mochi-serial.py ──USB──▶ ESP8266
                       (nunca toca                     (abre a porta UMA vez,
                        na porta serial)                reenvia a cada 5 s)
```

Funciona **em qualquer rede, ou sem rede nenhuma**. É o modo certo se:

- o PC está numa rede e o mochi em outra (o caso comum: Wi-Fi corporativo com
  WPA2-Enterprise, portal cativo ou registro de MAC, onde o ESP8266 não entra);
- a rede tem **isolamento de cliente** (*AP isolation*), que bloqueia tráfego
  entre dispositivos — a maioria das redes de empresa tem, e nesse caso o modo
  Wi-Fi não funcionaria **nem estando na mesma SSID**;
- o mDNS não atravessa a segmentação de VLAN da rede.

De brinde: sem credenciais no firmware, e como o rádio é desligado sobra RAM
para o display e o consumo cai ~20 mA. O mochi já vai estar no USB para ter
energia de qualquer forma.

**O detalhe que define a arquitetura:** no ESP8266 (NodeMCU / D1 mini), abrir a
porta serial aciona DTR/RTS e **reinicia a placa**. Se a status line abrisse a
porta a cada mensagem, o mochi reiniciaria dezenas de vezes por sessão. Por isso
existe o daemon: ele abre a porta uma única vez, e a status line só escreve um
arquivo de estado (escrita atômica: grava em `.tmp` e renomeia).

Um FIFO seria o instinto natural aqui, mas **escrever num FIFO sem leitor trava
para sempre** — penduraria o seu terminal se o daemon morresse. Arquivo comum
degrada em silêncio: fica velho e pronto.

O daemon reenvia o estado a cada 5 s mesmo sem mudança, então se o ESP reiniciar
ele se recupera sozinho.

### Wi-Fi (HTTP na rede local)

Só use se o PC e o mochi estiverem na **mesma rede sem isolamento de cliente** —
tipicamente a sua rede de casa. O ESP entra como cliente (não cria hotspot) e
responde em `http://mochi.local`.

| Rota | Efeito |
|---|---|
| `GET /` | página de status |
| `GET /state` | JSON com o estado atual |
| `GET /tokens?ctx=42&win=63&state=busy` | atualiza os olhos |
| `GET /backlight?on=0\|1` | apaga/acende a tela |

### E se o mochi ficar em casa e você no trabalho?

Aí não tem jeito de ser direto: seria preciso um intermediário na internet
(um broker MQTT público como o HiveMQ, ou um endpoint que o ESP fica
consultando). Dá para fazer, mas vale perguntar se compensa — se o mochi está
em casa, você não está olhando para ele. O caso que faz sentido é ele estar na
sua mesa, ao lado do notebook, e aí **serial resolve.**

---

## Lista de materiais

| Item | Obs |
|---|---|
| **ESP8266** (NodeMCU, Wemos D1 mini ou ESP-12) | 3,3 V — ideal para o display |
| **Display ST7789 240×240 SPI**, 1.54" ou 1.3" | veja a seção abaixo. **VCC só em 3,3 V, nunca 5 V** |
| Jumpers dupont fêmea-fêmea 10 cm | 7 fios (ou 6, se o módulo não tiver CS) |
| 2× parafuso M2×6 mm | prende o display |
| Fita dupla face fina | fixa a placa do ESP |
| Cabo USB | alimentação **e** dados (no modo serial os dois são usados) |
| Filamento PLA ou PETG | branco leitoso fica ótimo |

**Opcionais que valem a pena:** insertos roscados M2 (heat-set), botão tátil
6×6 mm para trocar de modo, buzzer piezo passivo (bipe no hook `Stop`), 1–3
LEDs WS2812B para as bochechas.

**Não é preciso nenhum resistor.** O ESP8266 e o display são ambos 3,3 V — não
há divisor de tensão, level shifter nem pull-up neste circuito.

### Qual display comprar

**Primeira escolha: ST7789 IPS 1.54" 240×240 SPI.** Área ativa de ~27,7 mm
contra ~23,4 mm da versão 1.3" — num rosto de mochi esses milímetros viram
olhos visivelmente maiores. É também o tamanho usado pelo projeto de referência.

**Alternativa igualmente boa: 1.3" 240×240 ST7789**, mais barata e bem mais
comum no Brasil. Mesmo controlador, mesma resolução, **firmware idêntico** — só
muda `scr_active` no `.scad`.

**7 ou 8 pinos, tanto faz.** Os módulos vêm em duas variantes:

| Variante | Pinos | CS |
|---|---|---|
| 8 pinos | GND VCC SCL SDA RES DC BLK **CS** | tem |
| 7 pinos | GND VCC SCL SDA RES DC BLK | não tem — fica em GND internamente |

A única desvantagem do sem-CS é não poder dividir o barramento SPI com outro
periférico, e aqui o display é o único dispositivo no SPI. Se o seu não tiver
CS, troque `#define TFT_CS D8` por `#define TFT_CS -1` no topo do `.ino` e não
ligue esse fio — sobra um GPIO.

**Checklist para aprovar um anúncio:**

| | |
|---|---|
| ✅ **Aprova** | controlador **ST7789** (ou ST7789V / ST7789VW), **240×240**, **1.54"** ou **1.3"**, **SPI**, **3,3 V** |
| ❌ **Rejeita** | ST7735 / ILI9341 / ILI9488 (outro controlador, outro código) · 240×280, 135×240, 320×240 (resolução diferente, quebra o layout dos olhos) · **GC9A01** (funciona, mas é redondo — é o caminho dos dois olhos separados, outro projeto) · só 5 V · com touch (não usamos e encarece) |
| ⚠️ **Confirmar** | quantos pinos (7 sem CS / 8 com CS) · barra de pinos soldada ou solta |

> **Duas armadilhas que não aparecem na lista de peças:**
>
> 1. O módulo quase sempre vem com a **barra de pinos solta, não soldada** — sem
>    soldar não encaixa em jumper nem protoboard. Precisa de ferro de solda.
> 2. O **cabo USB precisa ter fios de dados**. Muito cabo barato é só de carga e
>    nem enumera a porta serial — no modo serial isso é fatal, e o sintoma é
>    confuso (a placa liga e a tela acende, mas nenhuma porta aparece no PC).

**O Arduino Uno não entra neste projeto.** Sem Wi-Fi, lógica 5 V (mataria o
display de 3,3 V sem level shifter) e 2 KB de RAM — não anima 240×240. E se a
ideia fosse o próprio microcontrolador chamar a API da Anthropic, precisaria de
TLS: o Uno não tem, e o ESP8266 gastaria 16–30 KB de RAM dos 80 KB só no
handshake, brigando com o display — além de exigir a chave gravada no firmware.

---

## Ligações

Alimente o display **apenas com 3,3 V**.

| Display | ESP8266 | GPIO |
|---|---|---|
| VCC | 3V3 | — |
| GND | GND | — |
| SCL / SCK | D5 | GPIO14 |
| SDA / MOSI | D7 | GPIO13 |
| RES / RST | D2 | GPIO4 |
| DC | D1 | GPIO5 |
| CS | D8 | GPIO15 — *só se o módulo tiver esse pino* |
| BLK | **3V3** | ou D6/GPIO12, se quiser controlar o brilho (`USE_BLK_PIN 1`) |

`SCK` e `MOSI` são fixos (SPI por hardware); os outros são configuráveis no topo
do `.ino`. Evite D0/D3/D4 para o display — são pinos de boot no ESP8266.

Módulo de 7 pinos (sem CS): pule essa linha e use `#define TFT_CS -1`.

---

## Firmware

1. Arduino IDE 2.x → **Preferences → Additional Boards Manager URLs**:
   `https://arduino.esp8266.com/stable/package_esp8266com_index.json`
2. **Boards Manager** → instalar *esp8266 by ESP8266 Community*.
3. **Library Manager** → instalar *Adafruit GFX Library* e *Adafruit ST7735 and
   ST7789 Library*.
4. Abrir `firmware/claude_mochi/claude_mochi.ino`, conferir `LINK_SERIAL` /
   `LINK_WIFI` no topo, selecionar a placa e gravar.
5. **Só no modo Wi-Fi:** antes de gravar,
   `cp firmware/claude_mochi/config.example.h firmware/claude_mochi/config.h`
   e preencha SSID e senha (`config.h` está no `.gitignore`).

**Se a imagem sair com ruído:** baixe `setSPISpeed` de `40000000` para
`20000000`. **Se sair de cabeça para baixo ou espelhada:** ajuste
`tft.setRotation(0..3)`.

### Protocolo serial

Uma linha por atualização, pares `chave=valor` separados por espaço, terminada
em `\n`, a 115200 bps. Chaves: `ctx`, `win`, `state`. O firmware responde `ok`.

```
ctx=42 win=63 state=busy
```

Dá para testar à mão pelo Monitor Serial da Arduino IDE antes de montar o resto.

---

## Lado do PC

```bash
cp host/statusline-mochi.sh ~/.claude/statusline-mochi.sh
cp host/mochi-mode.sh       ~/.claude/mochi-mode.sh
chmod +x ~/.claude/statusline-mochi.sh ~/.claude/mochi-mode.sh
```

Copie o bloco `statusLine` (e os `hooks`, se quiser) de
`host/settings.example.json` para o seu `~/.claude/settings.json`.

Os hooks fazem o mochi piscar mais rápido enquanto o Claude trabalha e virar os
olhos de tonto durante a compactação — a status line sozinha não distingue esses
estados.

Requer `jq` (e `curl`, só no modo http).

### Modo serial: subindo a ponte

```bash
pip install pyserial
./host/mochi-serial.py            # detecta a porta sozinho (CH340/CP2102/FT232)
./host/mochi-serial.py --port /dev/ttyUSB0 -v
./host/mochi-serial.py --port COM3          # Windows
```

No Linux, se der erro de permissão: `sudo usermod -aG dialout $USER` e
reconecte a sessão.

Para deixar rodando sozinho — systemd de usuário (Linux):

```ini
# ~/.config/systemd/user/mochi.service
[Unit]
Description=claude-mochi serial bridge
[Service]
ExecStart=%h/.claude/mochi-serial.py
Restart=always
RestartSec=3
[Install]
WantedBy=default.target
```

```bash
cp host/mochi-serial.py ~/.claude/ && chmod +x ~/.claude/mochi-serial.py
systemctl --user daemon-reload && systemctl --user enable --now mochi
```

No macOS, o equivalente é um `launchd` plist em `~/Library/LaunchAgents/`.
Para só testar, `nohup ./host/mochi-serial.py &` resolve.

### Modo Wi-Fi

```bash
export MOCHI_LINK=http
export MOCHI_HOST=mochi.local     # ou o IP, se o mDNS não funcionar na sua rede
```

Nesse modo não precisa da ponte: a status line fala direto com o ESP.

---

## Case 3D

Há **dois** modelos no repositório, ainda não consolidados:

| pasta | para qual placa | estado |
|---|---|---|
| `case/mochi.scad` | ESP8266 + display, **com** janela de tela | renderizado e fechado; medidas de componente ainda por conferir |
| `hardware/mochi.scad` | Raspberry Pi Zero / Pico, **sem** janela de tela | renderizado, sólido fechado, STLs em [`hardware/stl/`](hardware/stl) |

O `hardware/` nasceu de um pedido separado, feito sem saber que o `case/` já
existia — então é o modelo validado geometricamente, mas mira a placa errada
para este projeto. O caminho natural é levar para o `case/` o que foi provado
ali (perfil do corpo, pilares de canto embutidos na parede, `assert` de encaixe
da placa) e ficar com um modelo só. Até lá, **o case do projeto é o `case/`** — o
`hardware/` fica como referência, com guia próprio em
[`hardware/README.md`](hardware/README.md) e `make stl` na raiz.

### case/ — ESP8266 com display

`case/mochi.scad` é um modelo **paramétrico** em OpenSCAD. O corpo é o casco
convexo de 12 esferas em três andares (base larga, barriga, cúpula), o que dá a
forma redonda de mochi e permite calcular a parede interna exata só reduzindo o
raio das esferas — sem `minkowski()`, que é lentíssimo.

```bash
openscad -D 'part="front"' -o front.stl case/mochi.scad
openscad -D 'part="back"'  -o back.stl  case/mochi.scad
```

Use `part="preview"` para ver as duas metades montadas.

> ⚠️ **A geometria já foi renderizada; as medidas de componente não.**
> As duas metades exportam como um sólido fechado e conexo cada uma (CGAL:
> `Simple: yes`, uma peça por STL). O que continua sendo estimativa são as
> medidas do seu display e da sua placa: antes de imprimir, **meça com
> paquímetro** e preencha as variáveis no topo do arquivo — principalmente
> `scr_pcb_w/h`, `scr_active`, `scr_active_dy`, `brd_l/w` e `usb_w/h/z`.
> Os valores atuais são estimativas para um ST7789 1.54" e um Wemos D1 mini
> (NodeMCU v3 é bem maior: 58 × 31 mm). E ninguém imprimiu isto ainda.

**Impressão:** PLA ou PETG, camada 0,15–0,20 mm, 15% de preenchimento. Imprima a
casca frontal com o rosto virado para a mesa — a janela sai sem suporte (a
orientação `part="front"` já faz isso). Folga de 0,3 mm em volta do display e
0,3 mm no lábio da tampa.

### Alternativa

Os modelos do projeto original (`models/clawd_mochi/clawd_mochi_v1.stl` e
`.3mf`) estão sob **CC BY-NC-SA 4.0** — uso não comercial, com atribuição e
compartilhamento pela mesma licença. Só que foram desenhados em volta de um
ESP32-C3 Super Mini (22,5 × 18 mm); um NodeMCU não cabe. Se o seu ESP8266 for um
Wemos D1 mini, vale testar; se for NodeMCU, o `.scad` daqui é o caminho.

---

## Próximos passos possíveis

- Dois displays redondos GC9A01 1.28" — um olho físico por tela, com contexto num
  e limite de 5h no outro (compartilham SPI, cada um com seu CS).
- Buzzer no hook `Stop` para avisar que a tarefa terminou.
- LEDs de bochecha acompanhando a cor da íris.
- Bateria LiPo + TP4056 com proteção (o backlight puxa 30–60 mA, então a
  autonomia real é de poucas horas).

## Licença

Código sob MIT. Se você reaproveitar os STLs do `clawd-mochi`, eles seguem sob
CC BY-NC-SA 4.0 do autor original.
