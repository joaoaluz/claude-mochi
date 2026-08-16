# claude-mochi

Um mochi de mesa cujos **olhos indicam o consumo de tokens do Claude Code**.

Quanto mais a janela de contexto enche, mais os olhos se fecham e mais quente
fica a cor da íris — verde → âmbar → vermelho. Uma barrinha embaixo mostra o
limite de 5 horas. Passou de 95% de contexto (ou rodou `/compact`), o mochi
fica de olhos tontos (`X_X`).

Inspirado no [clawd-mochi](https://github.com/yousifamanuel/clawd-mochi) do
Yousif Amanuel — mesma ideia de hardware, mas ligado ao Claude Code em vez de
funcionar offline por um hotspot.

> Projeto independente de fã, sem vínculo com a Anthropic.

---

## Como funciona

```
Claude Code ──JSON no stdin──▶ statusline-mochi.sh ──HTTP GET──▶ ESP8266 ──▶ olhos
                               (imprime a barra +      (Wi-Fi cliente,
                                curl em background)     mochi.local)
```

A **status line** do Claude Code roda a cada mensagem do assistente e recebe um
JSON que já traz tudo pronto:

```json
"context_window": { "used_percentage": 72, "context_window_size": 200000 },
"rate_limits":    { "five_hour": { "used_percentage": 41 } },
"cost":           { "total_cost_usd": 1.2345 }
```

O script imprime a status line normal e dispara um `curl` em background com
timeout de 400 ms — se o mochi estiver desligado, falha em silêncio e o terminal
nem percebe (medido: 25 ms de execução total com o host inalcançável).

**Por que não usar a API ou um scraper da página de usage:** a Usage & Cost
Admin API exige uma *Admin API key* (`sk-ant-admin01-…`), que só existe para
organizações do Console — a documentação diz explicitamente que *"the Admin API
is unavailable for individual accounts"*. Além disso ela mede o consumo da API
de desenvolvedor, não o da assinatura Pro/Max, e os dados chegam com ~5 min de
atraso em buckets de 1m/1h/1d. A status line é instantânea, local, sem chave e
funciona em qualquer tipo de conta.

---

## Lista de materiais

| Item | Obs |
|---|---|
| **ESP8266** (NodeMCU, Wemos D1 mini ou ESP-12) | 3,3 V — ideal para o display |
| **Display ST7789 1.54" 240×240 SPI**, módulo de **7 pinos (com CS)** | **VCC só em 3,3 V, nunca 5 V** |
| Jumpers dupont fêmea-fêmea 10 cm (7 fios) *ou* fio silicone 30 AWG + solda | solda deixa bem mais compacto |
| 2× parafuso M2×6 mm | prende o display |
| Fita dupla face fina | fixa a placa do ESP |
| Cabo USB | alimentação e gravação |
| Filamento PLA ou PETG | branco leitoso fica ótimo |

**Opcionais que valem a pena:** insertos roscados M2 (heat-set), botão tátil
6×6 mm para trocar de modo, buzzer piezo passivo (bipe no hook `Stop`), 1–3
LEDs WS2812B para as bochechas.

**O Arduino Uno não entra neste projeto.** Sem Wi-Fi, lógica 5 V (mataria o
display de 3,3 V sem level shifter) e 2 KB de RAM — não anima 240×240. E se a
ideia fosse o próprio microcontrolador chamar a API da Anthropic, precisaria de
TLS: o Uno não tem, e o ESP8266 gastaria 16–30 KB de RAM dos 80 KB só no
handshake, brigando com o display — além de exigir a chave de API gravada no
firmware.

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
| CS | D8 | GPIO15 |
| BLK | D6 (PWM) ou 3V3 | GPIO12 |

`SCK` e `MOSI` são fixos (SPI por hardware); os outros são configuráveis no topo
do `.ino`. Evite D0/D3/D4 para o display — são pinos de boot no ESP8266.

---

## Firmware

1. Arduino IDE 2.x → **Preferences → Additional Boards Manager URLs**:
   `https://arduino.esp8266.com/stable/package_esp8266com_index.json`
2. **Boards Manager** → instalar *esp8266 by ESP8266 Community*.
3. **Library Manager** → instalar *Adafruit GFX Library* e *Adafruit ST7735 and
   ST7789 Library*.
4. `cp firmware/claude_mochi/config.example.h firmware/claude_mochi/config.h` e
   preencher SSID e senha (`config.h` está no `.gitignore`).
5. Abrir `firmware/claude_mochi/claude_mochi.ino`, selecionar a placa e gravar.

Na primeira inicialização o display mostra o IP. O mochi também responde em
`http://mochi.local`.

**Se a imagem sair com ruído:** baixe `setSPISpeed` de `40000000` para
`20000000`. **Se sair de cabeça para baixo ou espelhada:** ajuste
`tft.setRotation(0..3)`.

### Endpoints

| Rota | Efeito |
|---|---|
| `GET /` | página de status |
| `GET /state` | JSON com o estado atual |
| `GET /tokens?ctx=42&win=63&state=busy` | atualiza os olhos |
| `GET /backlight?on=0\|1` | apaga/acende a tela |

---

## Lado do PC

```bash
cp host/statusline-mochi.sh ~/.claude/statusline-mochi.sh
chmod +x ~/.claude/statusline-mochi.sh
```

Depois copie o bloco `statusLine` de `host/settings.example.json` para o seu
`~/.claude/settings.json`. Se o mDNS não funcionar na sua rede, exporte o IP:

```bash
export MOCHI_HOST=192.168.0.42
```

Os hooks opcionais no mesmo arquivo (`UserPromptSubmit`, `Stop`, `PreCompact`)
fazem o mochi piscar mais rápido enquanto o Claude trabalha e virar os olhos de
tonto durante a compactação — a status line sozinha não distingue esses estados.

Requer `jq` e `curl`.

---

## Case 3D

`case/mochi.scad` é um modelo **paramétrico** em OpenSCAD. O corpo é o casco
convexo de 12 esferas em três andares (base larga, barriga, cúpula), o que dá a
forma redonda de mochi e permite calcular a parede interna exata só reduzindo o
raio das esferas — sem `minkowski()`, que é lentíssimo.

```bash
openscad -D 'part="front"' -o front.stl case/mochi.scad
openscad -D 'part="back"'  -o back.stl  case/mochi.scad
```

Use `part="preview"` para ver as duas metades montadas.

> ⚠️ **Este modelo é um ponto de partida v0 e ainda não foi renderizado nem
> impresso.** Não havia OpenSCAD disponível no ambiente onde ele foi escrito,
> então a geometria não foi validada visualmente. Antes de imprimir: abra no
> OpenSCAD, confira o preview, e **meça com paquímetro** o seu display e a sua
> placa para preencher as variáveis no topo do arquivo — principalmente
> `scr_pcb_w/h`, `scr_active`, `scr_active_dy`, `brd_l/w` e `usb_w/h/z`.
> Os valores atuais são estimativas para um ST7789 1.54" e um Wemos D1 mini
> (NodeMCU v3 é bem maior: 58 × 31 mm).

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
