#!/usr/bin/env bash
# claude-mochi — status line do Claude Code que também alimenta o mochi.
#
# O Claude Code envia um JSON no stdin a cada mensagem do assistente.
# Este script imprime a status line normal E publica o estado para o mochi.
#
# Duas formas de publicar (variável MOCHI_LINK):
#
#   serial (padrão)  Escreve um arquivo de estado de forma atômica. Quem fala
#                    com a porta USB é o daemon host/mochi-serial.py.
#                    Este script NUNCA abre a porta serial — abrir a porta
#                    reinicia o ESP8266, e isso aconteceria a cada mensagem.
#
#   http             Dispara um GET para o ESP na rede local. Só funciona se o
#                    PC e o mochi estiverem na mesma rede sem isolamento de
#                    cliente (redes de empresa normalmente têm isolamento).
#
#   both             Os dois.
#
# Instalação:
#   cp host/statusline-mochi.sh ~/.claude/statusline-mochi.sh
#   chmod +x ~/.claude/statusline-mochi.sh
#   e aponte "statusLine.command" no ~/.claude/settings.json para ele
#   (veja host/settings.example.json).
#
# Requisitos: jq. E curl, se usar o modo http.

set -uo pipefail

MOCHI_LINK="${MOCHI_LINK:-serial}"
MOCHI_HOST="${MOCHI_HOST:-mochi.local}"
MOCHI_STATE_FILE="${MOCHI_STATE_FILE:-$HOME/.claude/mochi-state}"

input=$(cat)

CTX=$(printf '%s' "$input"  | jq -r '.context_window.used_percentage // 0'        | cut -d. -f1)
WIN=$(printf '%s' "$input"  | jq -r '.rate_limits.five_hour.used_percentage // 0' | cut -d. -f1)
COST=$(printf '%s' "$input" | jq -r '.cost.total_cost_usd // 0')
MODEL=$(printf '%s' "$input" | jq -r '.model.display_name // "Claude"')
DIR=$(printf '%s' "$input"  | jq -r '.workspace.current_dir // .cwd // ""')

# --------------------------------------------------------------- publicação ---

if [ "$MOCHI_LINK" = "serial" ] || [ "$MOCHI_LINK" = "both" ]; then
  # Escrita atômica: grava num temporário e renomeia. A ponte nunca lê
  # um arquivo pela metade, e nada aqui pode bloquear.
  mkdir -p "$(dirname "$MOCHI_STATE_FILE")" 2>/dev/null
  if printf 'ctx=%s win=%s\n' "$CTX" "$WIN" > "${MOCHI_STATE_FILE}.tmp" 2>/dev/null; then
    mv -f "${MOCHI_STATE_FILE}.tmp" "$MOCHI_STATE_FILE" 2>/dev/null
  fi
fi

if [ "$MOCHI_LINK" = "http" ] || [ "$MOCHI_LINK" = "both" ]; then
  # Fire-and-forget: subshell desanexado + timeout de 400 ms.
  # Se o mochi estiver desligado, isto falha em silêncio.
  ( curl -fsS -m 0.4 "http://${MOCHI_HOST}/tokens?ctx=${CTX}&win=${WIN}" \
      >/dev/null 2>&1 & ) >/dev/null 2>&1
fi

# ------------------------------------------------------------------- saída ---

if   [ "$CTX" -ge 85 ]; then COLOR='\033[31m'   # vermelho
elif [ "$CTX" -ge 60 ]; then COLOR='\033[33m'   # âmbar
else                         COLOR='\033[32m'   # verde
fi
RESET='\033[0m'
DIM='\033[2m'

FILLED=$(( CTX / 10 ))
BAR=""
for i in $(seq 1 10); do
  if [ "$i" -le "$FILLED" ]; then BAR="${BAR}█"; else BAR="${BAR}░"; fi
done

printf "%b[%s]%b %s\n" "$DIM" "$MODEL" "$RESET" "${DIR##*/}"
printf "%b%s%b %s%% ctx %b·%b 5h %s%% %b·%b \$%.2f\n" \
  "$COLOR" "$BAR" "$RESET" "$CTX" "$DIM" "$RESET" "$WIN" "$DIM" "$RESET" "$COST"
