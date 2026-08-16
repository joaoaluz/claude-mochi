#!/usr/bin/env bash
# claude-mochi — publica o "modo" do mochi (idle | busy | compact).
#
# Chamado pelos hooks do Claude Code. A status line publica ctx/win; este
# script publica só o modo, num arquivo separado, para os dois não se
# sobrescreverem. A ponte serial junta os dois numa linha só.
#
# Uso: mochi-mode.sh busy
#
# No modo http, manda direto para o ESP em vez de escrever arquivo.

set -uo pipefail

MODE="${1:-idle}"
MOCHI_LINK="${MOCHI_LINK:-serial}"
MOCHI_HOST="${MOCHI_HOST:-mochi.local}"
MOCHI_MODE_FILE="${MOCHI_MODE_FILE:-$HOME/.claude/mochi-mode}"

case "$MODE" in
  idle|busy|compact) ;;
  *) MODE="idle" ;;
esac

if [ "$MOCHI_LINK" = "serial" ] || [ "$MOCHI_LINK" = "both" ]; then
  mkdir -p "$(dirname "$MOCHI_MODE_FILE")" 2>/dev/null
  if printf '%s\n' "$MODE" > "${MOCHI_MODE_FILE}.tmp" 2>/dev/null; then
    mv -f "${MOCHI_MODE_FILE}.tmp" "$MOCHI_MODE_FILE" 2>/dev/null
  fi
fi

if [ "$MOCHI_LINK" = "http" ] || [ "$MOCHI_LINK" = "both" ]; then
  ( curl -fsS -m 0.4 "http://${MOCHI_HOST}/tokens?state=${MODE}" \
      >/dev/null 2>&1 & ) >/dev/null 2>&1
fi

exit 0
