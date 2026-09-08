# Passo a passo — do zero ao mochi funcionando

Guia de construção para seguir de cima para baixo, numa sessão só. Cada fase
termina com um **teste**: se ele passar, a fase está pronta e você nunca mais
precisa voltar nela. Se falhar, o problema está no que você acabou de fazer —
não no resto.

**Ordem proposital:** hardware antes de software, e software antes do case. O
case é a última coisa: só vale imprimir depois de ter certeza de qual placa e
qual display cabem lá dentro.

| Fase | O que acontece | Tempo |
|---|---|---|
| [0](#fase-0--antes-de-encostar-no-ferro) | Conferir peças e instalar o que precisa de internet | 30 min |
| [1](#fase-1--soldar-a-barra-de-pinos-do-display) | Soldar a barra de pinos do display | 15 min |
| [2](#fase-2--ligar-os-fios) | Ligar os 7 (ou 8) fios | 15 min |
| [3](#fase-3--gravar-o-firmware) | Gravar o firmware e ver a animação de boot | 30 min |
| [4](#fase-4--testar-o-protocolo-na-mão) | Falar com o mochi pelo Monitor Serial | 10 min |
| [5](#fase-5--ligar-no-claude-code) | Status line + ponte serial | 20 min |
| [6](#fase-6--hooks-opcional) | Hooks (`busy` / `compact`) | 5 min |
| [7](#fase-7--deixar-rodando-sozinho) | Serviço que sobe junto com o sistema | 10 min |
| [8](#fase-8--o-case-3d) | Medir, ajustar o `.scad`, imprimir, montar | horas |

> Faltou alguma peça? Dá para fazer as fases 0 e 3–5 **sem o display**: o
> firmware grava e roda igual, e o Monitor Serial já responde `ok`. Você só não
> vê o rosto.

---

## Fase 0 — antes de encostar no ferro

### 0.1 Confira as peças

- [ ] ESP8266 (NodeMCU v2/v3 ou Wemos D1 mini)
- [ ] Display **ST7789 240×240 SPI**, 1.54" ou 1.3"
- [ ] Jumpers **fêmea-fêmea** (7 ou 8) — ou macho-fêmea + protoboard
- [ ] Cabo USB **com fios de dados**
- [ ] Ferro de solda + estanho (para a barra de pinos do display)

Duas conferências que evitam perder o dia:

**O display é mesmo ST7789 240×240?** Olhe o verso do módulo. Se estiver escrito
ST7735, ILI9341 ou GC9A01, é outro controlador e este firmware não serve. Se a
resolução for 240×280 ou 135×240, o layout dos olhos quebra.

**O cabo USB tem dados?** Plugue a placa no PC sem nada mais e rode:

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Se não aparecer nada, ou o cabo é só de carga, ou falta o driver do conversor
(CH340 / CP2102). Resolva isso **agora** — no modo serial, sem porta não há
projeto. No Windows, o equivalente é procurar a porta COM no Gerenciador de
Dispositivos.

### 0.2 Instale o que depende de internet

Arduino IDE 2.x:

1. **Preferences → Additional Boards Manager URLs**, cole:
   `https://arduino.esp8266.com/stable/package_esp8266com_index.json`
2. **Boards Manager** → instale *esp8266 by ESP8266 Community*
3. **Library Manager** → instale *Adafruit GFX Library* e
   *Adafruit ST7735 and ST7789 Library* (aceite as dependências que ela pedir)

No PC:

```bash
pip install pyserial
```

`jq` também é obrigatório (a status line usa). No Linux: `sudo apt install jq`.
No macOS: `brew install jq`.

### 0.3 Linux: permissão da porta serial

```bash
sudo usermod -aG dialout $USER
```

**Faça agora**, porque só vale depois de sair e entrar de novo na sessão (ou
reiniciar). Descobrir isso na fase 5, com tudo montado, é frustrante à toa.

✅ **Teste da fase 0:** a placa aparece como porta serial no PC e a Arduino IDE
lista a placa "NodeMCU 1.0" (ou "LOLIN(WEMOS) D1 R2 & mini") no menu de placas.

---

## Fase 1 — soldar a barra de pinos do display

O módulo quase sempre vem com a barra de pinos **solta, dentro do saquinho**.
Sem soldar, nenhum jumper encaixa.

Truque para ficar reto: espete a barra numa protoboard, apoie a placa do display
por cima, e solde primeiro **um pino só** nas pontas. Confira o esquadro, corrija
reaquecendo esse pino, e só então solde o resto.

Solda rápida em cada pino — 2 a 3 segundos. O display é sensível ao calor.

✅ **Teste da fase 1:** todos os pinos brilhantes e cônicos (não em bola fosca),
nenhuma ponte de estanho entre pinos vizinhos. Olhe contra a luz.

---

## Fase 2 — ligar os fios

**Nada de resistor.** ESP8266 e display são ambos 3,3 V — sem divisor, sem level
shifter, sem pull-up.

> ⚠️ **Confira a linha VCC duas vezes antes de energizar. 5 V queima o display.**
> `VIN` e `5V` do ESP são 5 V. Você quer o pino escrito **3V3**.

| Display | ESP8266 | GPIO | Observação |
|---|---|---|---|
| GND | GND | — | |
| VCC | **3V3** | — | nunca 5 V / VIN |
| SCL / SCK | D5 | GPIO14 | fixo, SPI por hardware |
| SDA / MOSI | D7 | GPIO13 | fixo, SPI por hardware |
| RES / RST | D2 | GPIO4 | |
| DC | D1 | GPIO5 | |
| BLK | **3V3** | — | backlight sempre aceso, o mais simples |
| CS | D8 | GPIO15 | **só se o seu módulo tiver esse pino** |

**Seu módulo tem 7 pinos (sem CS)?** Não ligue fio nenhum aí e, na fase 3, troque
no topo do `.ino`:

```c
#define TFT_CS   -1
```

Isso é a causa nº 1 de "backlight aceso, tela branca, imagem nunca aparece".

Jumpers **curtos**. Fio longo em SPI a 40 MHz vira ruído na tela.

### Energizar sem gravar nada

Plugue o USB. Esperado: LED da placa aceso e **backlight do display aceso** —
tela branca ou cinza uniforme, sem imagem. Isso é o certo: ainda não há firmware.

Se nada acender, ou se qualquer coisa esquentar, tire da tomada e refaça
VCC/GND antes de seguir.

✅ **Teste da fase 2:** tela branca acesa, nada quente.

---

## Fase 3 — gravar o firmware

Abra `firmware/claude_mochi/claude_mochi.ino`.

Confira no topo do arquivo:

```c
#define LINK_SERIAL 1     // deixe assim — é o modo recomendado
#define LINK_WIFI   0
```

E, se o seu módulo não tem CS, o `#define TFT_CS -1` da fase 2.

> **Só se você escolheu Wi-Fi** (`LINK_WIFI 1`): antes de gravar,
> `cp firmware/claude_mochi/config.example.h firmware/claude_mochi/config.h`
> e preencha SSID e senha. O `config.h` está no `.gitignore`, então a senha não
> vai para o repositório. **Nesse modo o PC e o mochi precisam estar na mesma
> rede, sem isolamento de cliente** — se for rede de empresa, quase certamente
> não vai funcionar; fique no serial.

Selecione a placa e a porta, e grave.

**Esperado ao terminar a gravação:** os olhos varrem de arregalados a
semicerrados e voltam, com a cor indo de verde → âmbar → vermelho e a barra de
baixo enchendo — uns 3 segundos. Depois os olhos "cochilam" (viram um traço
fino), esperando notícias do PC.

Essa é a animação de boot (`BOOT_DEMO 1`). Ela não depende de rede, de status
line nem de ponte serial: é o teste de fiação puro.

### Se a imagem saiu, mas errada

| Sintoma | Correção |
|---|---|
| Listras, ruído, pixels aleatórios | baixe `setSPISpeed` de `40000000` para `20000000` |
| De cabeça para baixo ou espelhada | ajuste `tft.setRotation(0..3)` |
| Cores em negativo | acrescente `tft.invertDisplay(false);` depois do `tft.init(...)` |

✅ **Teste da fase 3:** a animação de boot rodou. **Seu hardware está pronto** —
daqui para frente é tudo software.

---

## Fase 4 — testar o protocolo na mão

Ainda sem tocar em nenhuma configuração do Claude Code.

Abra o **Monitor Serial** da Arduino IDE e ajuste **duas** coisas:

- velocidade: **115200**
- terminação de linha: **Nova linha (NL)**

> ⚠️ **É aqui que quase todo mundo trava.** O firmware só processa a linha
> quando recebe o `\n`. Com o Monitor Serial em "Sem final de linha" você digita,
> aperta enter e **não acontece absolutamente nada** — sem erro, sem pista.

Abrir o Monitor Serial reinicia a placa (DTR/RTS no ESP8266), então a animação
de boot roda de novo. Normal.

Digite e envie, uma linha de cada vez:

```
ctx=20 win=10 state=idle
```

Olhos bem abertos, verdes; a placa responde `ok`. Agora os extremos:

```
ctx=75 win=50 state=busy      -> semicerrados, âmbar, piscando rápido
ctx=97 win=90 state=idle      -> olhos de tonto (X_X)
ctx=0  win=0  state=idle      -> volta ao normal
```

Por fim, **pare de enviar por 30 segundos**: ele cochila sozinho. Isso confirma
o timeout de "sem notícias do PC".

✅ **Teste da fase 4:** os quatro comandos acima produzem quatro rostos
diferentes, e o mochi cochila sozinho depois de 30 s.

---

## Fase 5 — ligar no Claude Code

> **Feche o Monitor Serial antes de continuar.** Ele segura a porta, e a ponte
> não vai conseguir abrir.

### 5.1 Instale os scripts do lado do PC

> **No Windows (ou com o Claude Desktop), pule esta parte.** Estes scripts
> precisam de `bash` e `jq`, que o Windows nao tem. La use um comando so:
> `python host/mochi.py install`. Detalhes na secao "Lado do PC" do README.

```bash
cp host/statusline-mochi.sh ~/.claude/statusline-mochi.sh
cp host/mochi-mode.sh       ~/.claude/mochi-mode.sh
cp host/mochi-serial.py     ~/.claude/mochi-serial.py
chmod +x ~/.claude/statusline-mochi.sh ~/.claude/mochi-mode.sh ~/.claude/mochi-serial.py
```

### 5.2 Configure a status line

Abra `~/.claude/settings.json` e acrescente o bloco `statusLine` de
`host/settings.example.json`:

```json
"statusLine": {
  "type": "command",
  "command": "~/.claude/statusline-mochi.sh",
  "padding": 1
}
```

Se você já tem uma status line, só troque o `command`.

**Por que isso funciona:** a status line roda a cada mensagem do assistente e
recebe no stdin um JSON que já traz `context_window.used_percentage` e
`rate_limits.five_hour.used_percentage` prontos. O script imprime a status line
normal no terminal **e** grava esses números em `~/.claude/mochi-state`, com
escrita atômica (grava `.tmp`, renomeia). Ela nunca abre a porta serial —
se abrisse, o ESP reiniciaria a cada mensagem.

### 5.3 Suba a ponte serial

Numa aba separada do terminal:

```bash
~/.claude/mochi-serial.py -v
```

Ela detecta a porta sozinha (CH340 / CH9102 / CP2102 / FT232). Se tiver mais de
um conversor plugado, aponte na mão:

```bash
~/.claude/mochi-serial.py --port /dev/ttyUSB0 -v
```

No Windows, `--port COM3`.

O `-v` mostra cada linha enviada — vale muito na primeira vez. A ponte reenvia o
estado a cada 5 s mesmo sem mudança, então se o ESP reiniciar ele se recupera
sozinho.

### 5.4 Abra o Claude Code

Em outra aba, abra o Claude Code e mande qualquer mensagem. A cada resposta do
assistente os olhos devem reagir — e ir fechando conforme a conversa cresce.

✅ **Teste da fase 5:** o `-v` da ponte imprime linhas `ctx=… win=…` conforme
você conversa, e o rosto muda junto.

---

## Fase 6 — hooks (opcional)

A status line sozinha não sabe distinguir "o Claude está trabalhando" de "o
Claude está esperando você", nem detectar uma compactação. Os hooks resolvem
isso: o mochi pisca mais rápido enquanto trabalha e fica de olhos tontos durante
o `/compact`.

Copie o bloco `hooks` de `host/settings.example.json` para o seu
`~/.claude/settings.json` — são cinco eventos (`UserPromptSubmit`, `Stop`,
`PreCompact`, `PostCompact`, `SessionEnd`) chamando `~/.claude/mochi-mode.sh`.

Esses scripts escrevem num arquivo separado (`~/.claude/mochi-mode`) para não
brigar com o que a status line escreve; a ponte junta os dois numa linha só.
Nunca bloqueiam e nunca tocam na porta serial.

✅ **Teste da fase 6:** mande uma tarefa longa. Durante o trabalho, piscada
rápida; ao terminar, volta ao normal.

---

## Fase 7 — deixar rodando sozinho

Enquanto a ponte não estiver rodando, o mochi cochila. Para não ter que subir na
mão toda vez:

**Linux (systemd de usuário):**

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
systemctl --user daemon-reload && systemctl --user enable --now mochi
```

Conferir depois: `systemctl --user status mochi`.

**macOS:** o equivalente é um `launchd` plist em `~/Library/LaunchAgents/`.

**Só testando:** `nohup ~/.claude/mochi-serial.py &` resolve.

> Quando quiser regravar o firmware, **pare a ponte antes**
> (`systemctl --user stop mochi`) — senão ela segura a porta e a Arduino IDE não
> grava.

✅ **Teste da fase 7:** reinicie o PC, abra o Claude Code, e o mochi reage sem
você ter feito nada.

---

## Fase 8 — o case 3D

Deixe para depois de tudo funcionar na bancada.

> ⚠️ **A geometria do `case/mochi.scad` já foi renderizada; as medidas de
> componente não.** Elas são estimativas para um ST7789 1.54" e um Wemos D1
> mini. E ninguém imprimiu isto ainda — você vai ser o primeiro.

### 8.1 Meça com paquímetro e preencha

Abra `case/mochi.scad` e corrija, no topo, as variáveis que descrevem **as suas**
peças:

| Variável | O que medir |
|---|---|
| `scr_pcb_w`, `scr_pcb_h`, `scr_pcb_t` | placa do display: largura, altura, espessura |
| `scr_active` | lado da área ativa (27,7 mm no 1.54"; 23,4 mm no 1.3") |
| `scr_active_dy` | quanto a área ativa está deslocada do centro da placa |
| `brd_l`, `brd_w`, `brd_t` | a placa do ESP (D1 mini 34,2×25,6 · NodeMCU v3 58×31) |
| `usb_w`, `usb_h`, `usb_z` | o conector USB e a altura do centro dele |

O `body_w/d/h` só precisa mexer se a sua placa não couber — o arquivo tem
`assert` de encaixe e vai reclamar em vez de gerar um case impossível.

### 8.2 Veja montado antes de exportar

Abra no OpenSCAD com `part="preview"` para ver as duas metades juntas. Depois:

```bash
openscad -D 'part="front"' -o front.stl case/mochi.scad
openscad -D 'part="back"'  -o back.stl  case/mochi.scad
```

### 8.3 Imprimir

PLA ou PETG, camada 0,15–0,20 mm, 15% de preenchimento. Imprima a casca frontal
com o rosto virado para a mesa — a janela sai sem suporte, e a orientação de
`part="front"` já faz isso. As folgas (0,3 mm em volta do display, 0,3 mm no
lábio da tampa) já estão no modelo.

Branco leitoso fica ótimo: o backlight atravessa um pouco a parede e o rosto
inteiro ganha um brilho suave.

### 8.4 Montar

2 parafusos M2×6 mm prendem o display; fita dupla face fina segura a placa do
ESP. Passe o cabo pelo recorte do USB antes de fechar as metades.

> O `hardware/mochi.scad` é **outro** modelo — mira Raspberry Pi Zero / Pico e
> não tem janela de tela. Ele existe como referência geométrica validada
> (`make stl` na raiz gera os STLs dele). Para este projeto, o case é o `case/`.

---

## Quando algo dá errado

| Sintoma | Causa provável |
|---|---|
| Backlight aceso, tela branca, nunca aparece imagem | `RES` ou `DC` no pino errado; ou `#define TFT_CS D8` num módulo sem CS |
| Tela totalmente apagada | `BLK` sem 3,3 V, ou `VCC` sem contato |
| Listras, ruído ou pixels aleatórios | jumper longo demais; baixe `setSPISpeed` para `20000000` |
| Imagem de cabeça para baixo ou espelhada | ajuste `tft.setRotation(0..3)` |
| Cores trocadas (negativo) | acrescente `tft.invertDisplay(false);` depois do `tft.init(...)` |
| Nenhuma porta aparece no PC | cabo USB só de carga, ou falta o driver CH340 / CP2102 |
| Monitor Serial não reage ao comando | terminação de linha não está em **Nova linha (NL)** |
| A placa reinicia ao abrir o Monitor Serial | normal no ESP8266 (DTR/RTS) |
| `mochi-serial.py` não abre a porta | Monitor Serial ou a ponte já rodando seguram a porta; ou falta `usermod -aG dialout $USER` |
| Arduino IDE não consegue gravar | a ponte (`mochi.service`) está segurando a porta — pare antes |
| Olhos cochilando com o Claude Code aberto | a ponte não está rodando, ou a `statusLine` não foi configurada |
| Status line vazia ou com erro no terminal | falta o `jq` |
| No modo Wi-Fi, `mochi.local` não responde | mDNS não atravessa a rede, ou o roteador tem isolamento de cliente — use o IP, ou volte para serial |

---

## Referências

- [`docs/PROTOBOARD.md`](PROTOBOARD.md) — as fases 1–5 em mais detalhe, focadas na bancada
- [`docs/tela/tela-mochi.svg`](tela/tela-mochi.svg) — todas as telas em escala 1:1, para saber o que esperar
- [`README.md`](../README.md) — por que a arquitetura é assim, e como escolher o display
- [`hardware/README.md`](../hardware/README.md) — o case alternativo (Pi Zero / Pico)
