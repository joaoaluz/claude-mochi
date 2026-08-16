#!/usr/bin/env python3
"""Ponte serial do claude-mochi.

Fica rodando em background, segura a porta serial aberta e empurra o estado
para o ESP8266. A status line do Claude Code NUNCA fala com a porta serial
diretamente: ela só escreve arquivos de estado e sai.

Por que essa separação existe:

  No ESP8266 (NodeMCU / Wemos D1 mini), abrir a porta serial aciona DTR/RTS e
  REINICIA a placa. Se a status line abrisse a porta a cada mensagem do Claude,
  o mochi reiniciaria dezenas de vezes por sessão. Aqui a porta é aberta uma
  única vez.

  E um arquivo é usado em vez de um FIFO de propósito: escrever num FIFO sem
  leitor bloqueia para sempre, o que penduraria o terminal se a ponte morresse.

O estado é reenviado a cada --interval segundos mesmo sem mudança, então se o
ESP reiniciar ele se recupera sozinho em poucos segundos.

Requer: pip install pyserial

Uso:
    ./mochi-serial.py                      # detecta a porta sozinho
    ./mochi-serial.py --port /dev/ttyUSB0
    ./mochi-serial.py --port COM3          # Windows
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("faltou o pyserial. instale com:  pip install pyserial")


# VID:PID dos conversores USB-serial usados nas placas ESP8266 comuns.
KNOWN_ADAPTERS = {
    (0x1A86, 0x7523),  # CH340  — NodeMCU v3 / clones
    (0x1A86, 0x55D4),  # CH9102
    (0x10C4, 0xEA60),  # CP2102 — NodeMCU v2 / Wemos D1 mini
    (0x0403, 0x6001),  # FT232
}


def autodetect_port() -> str | None:
    candidates = [
        p for p in list_ports.comports()
        if p.vid is not None and (p.vid, p.pid) in KNOWN_ADAPTERS
    ]
    if len(candidates) == 1:
        return candidates[0].device
    if len(candidates) > 1:
        found = ", ".join(p.device for p in candidates)
        sys.exit(f"achei mais de uma placa ({found}). escolha com --port")
    return None


def read_first_line(path: pathlib.Path) -> str:
    """Lê a primeira linha de um arquivo; string vazia se não der."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return fh.readline().strip()
    except (OSError, UnicodeDecodeError):
        return ""


def compose(state_file: pathlib.Path, mode_file: pathlib.Path) -> str:
    """Monta a linha do protocolo: 'ctx=42 win=63 state=busy'."""
    payload = read_first_line(state_file) or "ctx=0 win=0"
    mode = read_first_line(mode_file) or "idle"
    # Só aceita modos conhecidos — o firmware ignora o resto, mas não custa.
    if mode not in ("idle", "busy", "compact"):
        mode = "idle"
    return f"{payload} state={mode}"


def open_serial(port: str, baud: int) -> serial.Serial:
    """Abre a porta com DTR/RTS baixos para minimizar o reset do ESP."""
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 0.2
    # Precisa ser definido ANTES do open() para valer já na abertura.
    ser.dtr = False
    ser.rts = False
    ser.open()
    # A placa ainda pode reiniciar uma vez aqui; dá tempo do firmware subir.
    time.sleep(1.8)
    ser.reset_input_buffer()
    return ser


def main() -> int:
    home = pathlib.Path(os.path.expanduser("~/.claude"))
    ap = argparse.ArgumentParser(description="Ponte serial do claude-mochi")
    ap.add_argument("--port", help="porta serial (padrão: detecta sozinho)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--state-file", type=pathlib.Path, default=home / "mochi-state")
    ap.add_argument("--mode-file", type=pathlib.Path, default=home / "mochi-mode")
    ap.add_argument("--interval", type=float, default=5.0,
                    help="reenvio periódico em segundos (recupera reset do ESP)")
    ap.add_argument("--poll", type=float, default=0.2,
                    help="intervalo de verificação dos arquivos de estado")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    port = args.port or autodetect_port()
    if not port:
        sys.exit("não achei nenhuma placa. conecte o mochi ou passe --port")

    print(f"[mochi] porta {port} @ {args.baud}", file=sys.stderr)
    print(f"[mochi] estado: {args.state_file}", file=sys.stderr)

    ser: serial.Serial | None = None
    last_sent = ""
    last_send_at = 0.0

    try:
        while True:
            # (Re)conecta se preciso.
            if ser is None:
                try:
                    ser = open_serial(port, args.baud)
                    last_sent = ""  # força um envio logo após conectar
                    print("[mochi] conectado", file=sys.stderr)
                except (serial.SerialException, OSError) as exc:
                    print(f"[mochi] sem porta ({exc}); tentando de novo em 3 s",
                          file=sys.stderr)
                    time.sleep(3)
                    continue

            line = compose(args.state_file, args.mode_file)
            now = time.monotonic()
            changed = line != last_sent
            stale = (now - last_send_at) >= args.interval

            if changed or stale:
                try:
                    ser.write((line + "\n").encode("ascii", "ignore"))
                    ser.flush()
                    last_sent = line
                    last_send_at = now
                    if args.verbose and changed:
                        print(f"[mochi] -> {line}", file=sys.stderr)
                except (serial.SerialException, OSError) as exc:
                    print(f"[mochi] porta caiu ({exc}); reconectando", file=sys.stderr)
                    try:
                        ser.close()
                    except Exception:
                        pass
                    ser = None
                    continue

            # Descarta o eco do firmware para o buffer não encher.
            try:
                if ser.in_waiting:
                    ser.read(ser.in_waiting)
            except (serial.SerialException, OSError):
                pass

            time.sleep(args.poll)
    except KeyboardInterrupt:
        print("\n[mochi] tchau", file=sys.stderr)
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
