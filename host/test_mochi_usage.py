#!/usr/bin/env python3
"""Checagem de le_widget_usage(): sobe um /usage falso e confere o que entra.

Rode com:  python host/test_mochi_usage.py
"""
import datetime
import http.server
import json
import os
import pathlib
import tempfile
import threading

TMP = pathlib.Path(tempfile.mkdtemp())
os.environ["MOCHI_WIN_FILE"] = str(TMP / "win.json")
os.environ["MOCHI_STATE_FILE"] = str(TMP / "state")
os.environ["MOCHI_MODE_FILE"] = str(TMP / "mode")

CORPO = {"payload": b"{}"}


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(CORPO["payload"])

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["MOCHI_USAGE_URL"] = f"http://127.0.0.1:{srv.server_port}/usage"

import mochi  # noqa: E402  (precisa das env vars acima ja definidas)


def responde(pct, idade_s):
    quando = datetime.datetime.now() - datetime.timedelta(seconds=idade_s)
    CORPO["payload"] = json.dumps({
        "atualizado_em": quando.isoformat(),
        "sessao_atual": {"percentual": pct, "reset_info": "2h15min"},
    }).encode()


# dado fresco entra
responde(37, 5)
assert mochi.le_widget_usage() == ""
assert mochi.win_atual() == 37, mochi.win_atual()

# dado velho e recusado: o valor anterior fica de pe
responde(99, mochi.USAGE_MAX_IDADE_S + 60)
assert mochi.le_widget_usage() != ""
assert mochi.win_atual() == 37

# widget nao publica `resets`; o que o /usage deixou tem que sobreviver
futuro = (mochi._agora() + datetime.timedelta(hours=2)).isoformat()
mochi._guarda_win(50, futuro, mochi._agora(), "usage-report")
responde(61, 5)
assert mochi.le_widget_usage() == ""
assert mochi._le_win()["resets"] == futuro
assert mochi.win_atual() == 61

# janela ja virou -> zero de verdade, nao o ultimo numero
passado = (mochi._agora() - datetime.timedelta(minutes=1)).isoformat()
mochi._guarda_win(61, passado, mochi._agora(), "usage-report")
assert mochi.win_atual() == 0

# PC dormiu/desconectou por horas: o `resets` de ontem ficou orfao no arquivo.
# O widget volta com pct fresco e SEM resets (e assim mesmo) — o valor vencido
# nao pode arrastar e zerar um numero que acabou de chegar ao vivo.
responde(50, 5)
assert mochi.le_widget_usage() == ""
assert mochi.win_atual() == 50, mochi.win_atual()

# servidor fora do ar nao explode nem apaga nada
os.environ["MOCHI_USAGE_URL"] = "http://127.0.0.1:1/usage"
mochi.USAGE_URL = os.environ["MOCHI_USAGE_URL"]
assert mochi.le_widget_usage() != ""

# modo: o vocabulario chega inteiro na linha do protocolo, e lixo vira idle
mochi.STATE_FILE.write_text("ctx=10 win=20", encoding="utf-8")
for modo in mochi.MODOS:
    mochi.MODE_FILE.write_text(modo, encoding="utf-8")
    assert mochi.compose_line() == f"ctx=10 win=20 state={modo}", modo
mochi.MODE_FILE.write_text("perguntando", encoding="utf-8")
assert mochi.compose_line().endswith("state=idle")

srv.shutdown()
print("ok")
