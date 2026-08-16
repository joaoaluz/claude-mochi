#!/usr/bin/env bash
# claude-mochi — status line do Claude Code que também alimenta o mochi.
#
# O Claude Code envia um JSON no stdin a cada mensagem do assistente.
# Este script imprime a status line normal E dispara um GET para o ESP,
# em background e com timeout curto, para nunca travar o terminal.
#
# Instalação:
#   cp host/statusline-mochi.sh ~/.claude/statusline-mochi.sh
#   chmod +x ~/.claude/statusline-mochi.sh
#   e aponte "statusLine.command" no ~/.claude/settings.json para ele
#   (veja host/settings.example.json).
#
# Requisitos: jq e curl.

set -uo pipefail

MOCHI_HOST="${MOCHI_HOST:-mochi.local}"

input=$(cat)

CTX=$(printf '%s' "$input"  | jq -r '.context_window.used_percentage // 0'        | cut -d. -f1)
WIN=$(printf '%s' "$input"  | jq -r '.rate_limits.five_hour.used_percentage // 0' | cut -d. -f1)
COST=$(printf '%s' "$input" | jq -r '.cost.total_cost_usd // 0')
MODEL=$(printf '%s' "$input" | jq -r '.model.display_name // "Claude"')
DIR=$(printf '%s' "$input"  | jq -r '.workspace.current_dir // .cwd // ""')

# Fire-and-forget: subshell desanexado + timeout de 400 ms.
# Se o mochi estiver desligado, isto falha em silêncio e o terminal nem percebe.
( curl -fsS -m 0.4 "http://${MOCHI_HOST}/tokens?ctx=${CTX}&win=${WIN}" >/dev/null 2>&1 & ) >/dev/null 2>&1

# Barra de contexto com as mesmas cores dos olhos.
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
