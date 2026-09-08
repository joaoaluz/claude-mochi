---
name: claude-mochi
description: Instala, conserta e diagnostica o claude-mochi (o bichinho de mesa com olhos de ST7789 que mostra o consumo de tokens do Claude Code). Use quando o usuario plugar o mochi num computador novo, disser que o mochi nao acende / travou / ficou dormindo / esta com olho de tonto, quiser configurar a status line e os hooks do mochi, ou mencionar mochi, ponte serial, COM/ttyUSB, ESP8266 ou NodeMCU no contexto deste projeto.
---

# claude-mochi — instalar e consertar

Objetivo: **plugou o mochi no USB, ele acende e passa a seguir os tokens.**
Nada de systemd, Agendador de Tarefas ou abrir terminal toda vez.

Tudo passa por um unico programa: `host/mochi.py`. Ele nao depende de `bash`
nem de `jq`, entao roda igual no Windows, no macOS e no Linux.

## 0. Ache o mochi.py

Nesta ordem, use o primeiro que existir:

1. `host/mochi.py` na raiz do repositorio claude-mochi (preferido — e o atual)
2. `~/.claude/mochi.py` (copia ja instalada)

Se nenhum existir, o repositorio nao esta por perto: peca para o usuario
clonar `claude-mochi` e rode a partir de `host/mochi.py`.

Nos comandos abaixo, `PY` e o interpretador Python do usuario. No Windows,
prefira `python`; se nao responder, tente `py -3`.

## 1. Instalacao num computador novo (o caso "computador do trabalho")

Rode na ordem e mostre a saida de cada passo:

```bash
PY -m pip install --user pyserial
PY host/mochi.py doctor
PY host/mochi.py install
```

- `doctor` antes do `install` de proposito: ele diz se a placa foi vista e se
  o pyserial esta la, entao voce descobre o problema antes de mexer em
  configuracao.
- `install` faz backup do `settings.json` existente (`settings.json.bak-mochi`),
  preserva hooks de terceiros, escreve a `statusLine` e os hooks do mochi, e
  ja sobe a ponte. Rodar de novo e seguro (idempotente).
- **Avise o usuario para reiniciar o Claude Desktop / Claude Code no fim.** A
  status line e os hooks so passam a valer numa sessao nova.

Depois de reiniciar, confirme:

```bash
PY host/mochi.py doctor
```

Deve terminar em `=> tudo certo`.

## 2. Como saber se esta funcionando

Sem depender de olhar a tela: `doctor` mostra a porta escolhida, se a ponte
esta viva (pid) e o que a status line publicou pela ultima vez.

Olhando o mochi:

| O que a tela mostra          | Significado                                     |
|------------------------------|-------------------------------------------------|
| Olhos fechados (tracinho)    | Sem noticias do PC ha mais de 30 s              |
| Olhos abertos + barra        | Recebendo estado normalmente                    |
| Olhos mais fechados          | Cota de 5 h mais consumida (e o esperado)       |
| Olho de tonto (X)            | Cota >= 95% **ou** compactacao em curso         |
| Varredura 0->100% ao ligar   | Boot demo: display e fiacao OK, sem depender do PC |

## 3. Problemas, do mais comum para o menos

### "A porta esta ocupada" / Access is denied

So um processo pode segurar a porta. Culpados, em ordem:

1. **Uma ponte do mochi ja rodando** — inclusive uma dentro do **WSL**, ou uma
   apontando para caminhos `\\wsl.localhost\...`. Rode `PY host/mochi.py stop`.
   Se o processo for de outro Python (WSL, outro venv), ache e encerre:
   - Windows: `Get-CimInstance Win32_Process -Filter "Name like '%python%'" | Select ProcessId, CommandLine`
   - Linux/macOS: `ps aux | grep mochi`
2. **Monitor Serial da Arduino IDE aberto** — feche a janela do monitor.

Nunca rode duas pontes ao mesmo tempo (ex.: uma no WSL e outra no Windows).

### O mochi nao e encontrado

```bash
PY host/mochi.py ports
```

Mostra todas as portas com uma nota. Interprete:

- Nota **100** = adaptador USB-serial conhecido (CH340, CP2102, FT232...). E ele.
- Nota **-100** = descartada (Bluetooth, porta virtual). Normal ter varias.
- **Nenhuma com nota > 0**: e driver ou cabo.
  - Cabo de **so carga** nao tem fio de dados — troque por um cabo de dados.
  - Falta o driver do CH340 (comum em Windows corporativo). Instale o driver
    do fabricante. Se o computador do trabalho bloqueia instalacao de driver,
    esse e o limite: fale com o usuario, nao tente contornar.

Se o usuario souber a porta, force: `PY host/mochi.py start --port COM7`,
ou defina a variavel de ambiente `MOCHI_PORT`.

### A tela acende mas fica dormindo (olhos fechados)

A placa esta viva, o PC e que nao esta falando. Verifique nesta ordem:

1. `PY host/mochi.py doctor` — a ponte esta rodando?
2. O `estado` esta velho (muitos segundos atras)? Entao a status line nao esta
   rodando: confira se o `settings.json` tem a `statusLine` do mochi e se o
   Claude Desktop foi reiniciado depois do `install`.
3. Teste o caminho direto, sem a ponte:
   ```bash
   PY host/mochi.py stop
   PY host/mochi.py send "ctx=50 win=80 state=busy"
   PY host/mochi.py start
   ```
   Se o `send` responder `b'ok\r\n'`, firmware e cabo estao bons e o problema
   esta na status line.

### A status line nao aparece no Windows

Quase sempre e caminho. A status line do Claude Code aceita **so uma string**
de comando e roda pelo **Git Bash** quando ele existe — e o Git Bash come
contrabarras: `C:\Users\dev` chega como `C:Usersdev` e falha calado.

O `install` ja resolve isso (barras normais e caminho curto 8.3 quando ha
espacos). Se alguem editou o `settings.json` na mao, o valor certo se parece com:

```json
"statusLine": { "type": "command", "command": "C:/Users/voce/miniconda3/python.exe C:/Users/voce/.claude/mochi.py statusline", "padding": 1 }
```

Se o caminho do Python tiver espaco (`C:/Program Files/...`), rode o `install`
de novo em vez de escrever a mao — ele converte para o nome curto.

### Firmware

O firmware normalmente **ja esta gravado**. Nao regrave sem necessidade.
Regravar so quando o `send` nao responde `ok` E o boot demo nao roda ao ligar
(nesse caso o problema e a placa/fiacao, nao o PC). O sketch e
`firmware/claude_mochi/claude_mochi.ino`, ESP8266 + ST7789 240x240.

## 4. Desinstalar

```bash
PY host/mochi.py uninstall
```

Tira a `statusLine` e os hooks do `settings.json` e encerra a ponte. O arquivo
`~/.claude/mochi.py` fica — apague na mao se quiser.

## Regras

- **Nunca** faca a status line abrir a porta serial. Abrir a porta mexe em
  DTR/RTS e reinicia o ESP8266; isso aconteceria a cada mensagem do Claude. A
  status line so escreve arquivos; quem fala com a porta e a ponte.
- Antes de escrever no `settings.json` do usuario, garanta o backup (o
  `install` ja faz) e preserve hooks que nao sejam do mochi.
- Se o computador for corporativo e travar driver ou instalacao, diga isso
  claramente ao usuario em vez de tentar contornar a politica da maquina.
