#!/usr/bin/env python3
"""claude-mochi — lado do PC, em um arquivo so.

Substitui o trio statusline-mochi.sh + mochi-mode.sh + mochi-serial.py por um
unico programa Python. Motivo: no Windows nao existe `jq` nem `bash` por
padrao, e a status line do Claude Code e executada pelo Git Bash (quando
instalado) ou pelo PowerShell. Um script bash que depende de `jq` simplesmente
nao roda la.

Os .sh continuam no repositorio para quem ja os tem funcionando no Linux/macOS.
No Windows — e com o Claude Desktop — use este arquivo.

Subcomandos:

    mochi.py install        instala em ~/.claude e configura settings.json
    mochi.py statusline     status line do Claude Code (le JSON no stdin)
    mochi.py tokens busy    numeros + modo, lidos do transcript (hooks)
    mochi.py mode ask       so o modo, sem tocar nos numeros
    mochi.py bridge         ponte serial em primeiro plano (com log)
    mochi.py start|stop     ponte serial em segundo plano
    mochi.py doctor         diagnostico: portas, ponte, firmware
    mochi.py ports          lista as portas e a nota de cada uma
    mochi.py send "..."     manda uma linha crua para o mochi (teste)
    mochi.py uninstall      remove o que o install colocou

Arquitetura (a mesma de antes, e pelos mesmos motivos):

  A status line NUNCA abre a porta serial. Abrir a porta mexe em DTR/RTS e
  REINICIA o ESP8266 — isso aconteceria a cada mensagem do Claude. Quem segura
  a porta aberta e a ponte, um processo so, que fica rodando. A status line
  apenas escreve arquivos de estado (escrita atomica) e sai na hora.

  A ponte reenvia o estado a cada --interval segundos mesmo sem mudanca, entao
  se o ESP reiniciar ele se recupera sozinho em poucos segundos.

Requer pyserial apenas para a ponte:  pip install pyserial
A status line e os hooks funcionam sem ele (so escrevem arquivos).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time

IS_WINDOWS = os.name == "nt"
HOME_CLAUDE = pathlib.Path(os.path.expanduser("~")) / ".claude"

STATE_FILE = pathlib.Path(os.environ.get("MOCHI_STATE_FILE", HOME_CLAUDE / "mochi-state"))
MODE_FILE = pathlib.Path(os.environ.get("MOCHI_MODE_FILE", HOME_CLAUDE / "mochi-mode"))
# Vocabulario de modo. Uma lista so: argparse, validacao e hooks leem daqui.
MODOS = ("idle", "busy", "compact", "ask")
PORT_CACHE = HOME_CLAUDE / "mochi-port"          # ultima porta que funcionou
BEAT_FILE = HOME_CLAUDE / "mochi-bridge.beat"    # ponte viva? (pid + mtime)
LOG_FILE = HOME_CLAUDE / "mochi-bridge.log"

BAUD = 115200

# Se o batimento da ponte estiver mais velho que isto, consideramos que ela
# morreu e subimos outra. Bem maior que o intervalo de batimento (2 s) para
# aguentar a maquina engasgar por um instante sem duplicar processo.
BEAT_STALE_S = 20.0


# ============================================================ portas seriais ==

# VID:PID dos conversores USB-serial usados nas placas ESP8266/ESP32 comuns.
KNOWN_ADAPTERS = {
    (0x1A86, 0x7523): "CH340",
    (0x1A86, 0x7522): "CH340",
    (0x1A86, 0x55D4): "CH9102",
    (0x10C4, 0xEA60): "CP2102",
    (0x10C4, 0xEA70): "CP2105",
    (0x0403, 0x6001): "FT232",
    (0x0403, 0x6015): "FT231X",
    (0x303A, 0x1001): "ESP32-S2/S3 USB nativo",
    (0x2341, 0x0043): "Arduino Uno",
    (0x2A03, 0x0043): "Arduino Uno (clone)",
}

# Pedacos de descricao que denunciam uma porta que NAO e o mochi. Este PC de
# teste tem oito COM de Bluetooth; sem esta lista o autodetect vira loteria.
BLACKLIST_HINTS = ("bluetooth", "bthenum", "virtual", "com0com", "vspd")


def _import_serial():
    """Importa o pyserial com uma mensagem util se ele faltar."""
    try:
        import serial                        # noqa: F401
        from serial.tools import list_ports  # noqa: F401
        return serial, list_ports
    except ImportError:
        sys.exit(
            "faltou o pyserial. instale com:\n"
            f"    {sys.executable} -m pip install pyserial"
        )


def score_port(p) -> tuple[int, str]:
    """Da uma nota para a porta. Maior = mais provavel de ser o mochi.

    Nao basta 'e uma porta COM': num Windows tipico a maioria das COM sao
    Bluetooth. A nota combina VID:PID conhecido, descricao e tipo de barramento.
    """
    desc = f"{p.description} {p.hwid} {getattr(p, 'manufacturer', '') or ''}".lower()

    for hint in BLACKLIST_HINTS:
        if hint in desc:
            return -100, f"ignorada ({hint})"

    if p.vid is not None and (p.vid, p.pid) in KNOWN_ADAPTERS:
        return 100, f"adaptador conhecido: {KNOWN_ADAPTERS[(p.vid, p.pid)]}"

    for nome in ("ch340", "ch910", "cp210", "ftdi", "ft232",
                 "silicon labs", "esp32", "usb-serial", "usb serial"):
        if nome in desc:
            return 60, f"descricao parece USB-serial ({nome})"

    if p.vid is not None:
        return 30, "dispositivo USB generico"

    return 0, "porta sem VID (provavelmente nao e USB)"


def list_candidates():
    """Portas ordenadas da mais provavel para a menos."""
    _, list_ports = _import_serial()
    linhas = []
    for p in list_ports.comports():
        nota, motivo = score_port(p)
        linhas.append((nota, p.device, p.description, motivo))
    linhas.sort(key=lambda r: (-r[0], r[1]))
    return linhas


def probe_port(port: str, timeout: float = 2.5) -> bool:
    """Abre a porta e pergunta se tem um mochi do outro lado.

    O firmware responde 'ok' para cada linha recebida. Se responder, e ele.
    Isso resolve o caso de duas placas ligadas ao mesmo tempo: em vez de
    desistir com 'achei mais de uma placa', perguntamos para cada uma.
    """
    try:
        ser = open_serial(port, BAUD, settle=1.6)
    except Exception:
        return False
    try:
        ser.reset_input_buffer()
        ser.write(b"ctx=0 win=0 state=idle\n")
        ser.flush()
        fim = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < fim:
            buf += ser.read(64)
            if b"ok" in buf or b"mochi" in buf:
                return True
            time.sleep(0.05)
        return False
    finally:
        try:
            ser.close()
        except Exception:
            pass


def resolve_port(explicit: str | None = None, quiet: bool = False) -> str | None:
    """Descobre em qual porta o mochi esta.

    Ordem: --port / MOCHI_PORT  ->  ultima porta que funcionou  ->  melhor nota.
    Com varios candidatos fortes, pergunta para cada um (probe).
    Devolve None se nao achar nada — quem chama decide se espera ou desiste.
    """
    explicit = explicit or os.environ.get("MOCHI_PORT")
    if explicit:
        return explicit

    linhas = [r for r in list_candidates() if r[0] > 0]
    if not linhas:
        return None

    nomes = [r[1] for r in linhas]

    # A porta que funcionou da ultima vez tem prioridade, se ainda existir.
    cache = _read_first_line(PORT_CACHE)
    if cache and cache in nomes:
        return cache

    fortes = [r for r in linhas if r[0] >= 100]
    alvos = [r[1] for r in (fortes or linhas)]
    if len(alvos) == 1:
        return alvos[0]

    # Empate: pergunta para cada placa qual delas e o mochi.
    if not quiet:
        print(f"[mochi] {len(alvos)} candidatas; testando uma a uma", file=sys.stderr)
    for nome in alvos:
        if probe_port(nome):
            return nome
    return alvos[0]


def open_serial(port: str, baud: int = BAUD, settle: float = 1.8):
    """Abre a porta com DTR/RTS baixos para minimizar o reset do ESP."""
    serial, _ = _import_serial()
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 0.2
    # Precisa ser definido ANTES do open() para valer ja na abertura.
    ser.dtr = False
    ser.rts = False
    ser.open()
    # A placa ainda pode reiniciar uma vez aqui; da tempo do firmware subir.
    time.sleep(settle)
    ser.reset_input_buffer()
    return ser


def explain_open_error(port: str, exc: Exception) -> str:
    """Traduz o erro de abrir a porta para algo acionavel."""
    txt = str(exc).lower()
    if "access is denied" in txt or "permission" in txt or "acesso negado" in txt:
        return (
            f"a porta {port} esta ocupada por outro programa.\n"
            "  Quase sempre e um destes:\n"
            "    - uma ponte do mochi ja rodando (inclusive dentro do WSL)\n"
            "    - o Monitor Serial da Arduino IDE aberto\n"
            "  Feche o outro e tente de novo:  mochi.py stop   (ou feche a IDE)"
        )
    if "could not open" in txt or "no such file" in txt:
        return f"a porta {port} sumiu. O cabo caiu? Reconecte o mochi."
    return f"nao consegui abrir {port}: {exc}"


# ================================================== arquivos de estado (I/O) ==

def _read_first_line(path: pathlib.Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return fh.readline().strip()
    except (OSError, UnicodeDecodeError):
        return ""


def _write_atomic(path: pathlib.Path, texto: str) -> None:
    """Grava num temporario e renomeia.

    A ponte nunca le um arquivo pela metade, e nada aqui pode bloquear. Um FIFO
    seria pior: escrever num FIFO sem leitor trava para sempre, o que penduraria
    a status line se a ponte morresse.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(texto if texto.endswith("\n") else texto + "\n")
        os.replace(tmp, path)
    except OSError:
        pass  # a status line jamais pode quebrar por causa disso


# ======================================================= ponte em background ==

def pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WINDOWS:
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        h = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def bridge_alive() -> bool:
    """A ponte esta viva? Batimento recente E processo existente.

    So o pid nao basta: o Windows recicla pid. So o mtime tambem nao: um
    processo congelado deixaria o arquivo velho mas o pid vivo.
    """
    try:
        idade = time.time() - BEAT_FILE.stat().st_mtime
    except OSError:
        return False
    if idade > BEAT_STALE_S:
        return False
    pid = _read_first_line(BEAT_FILE)
    return pid.isdigit() and pid_running(int(pid))


def spawn_bridge(port: str | None = None) -> bool:
    """Sobe a ponte destacada do terminal. Nao espera, nao trava.

    E isto que faz o 'plugou, funcionou': a status line chama esta funcao
    quando percebe que nao ha ponte viva. Sem systemd, sem Agendador de
    Tarefas, sem lembrar de abrir nada.
    """
    if bridge_alive():
        return False

    exe = sys.executable
    if IS_WINDOWS:
        # pythonw.exe roda sem abrir janela de console.
        pw = pathlib.Path(exe).with_name("pythonw.exe")
        if pw.exists():
            exe = str(pw)

    cmd = [exe, str(pathlib.Path(__file__).resolve()), "bridge", "--quiet"]
    if port:
        cmd += ["--port", port]

    kwargs: dict = {}
    if IS_WINDOWS:
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = (
            DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW)
    else:
        kwargs["start_new_session"] = True

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        log = LOG_FILE.open("a", encoding="utf-8", errors="replace")
        subprocess.Popen(cmd, stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, close_fds=True, **kwargs)
        return True
    except OSError:
        return False


def stop_bridge() -> bool:
    pid = _read_first_line(BEAT_FILE)
    if not pid.isdigit() or not pid_running(int(pid)):
        try:
            BEAT_FILE.unlink()
        except OSError:
            pass
        return False
    alvo = int(pid)
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(alvo), "/F"],
                           capture_output=True, check=False)
        else:
            import signal
            os.kill(alvo, signal.SIGTERM)
    except Exception:
        return False
    for _ in range(30):
        if not pid_running(alvo):
            break
        time.sleep(0.1)
    try:
        BEAT_FILE.unlink()
    except OSError:
        pass
    return True


# ================================================================== a ponte ==

def compose_line() -> str:
    """Monta a linha do protocolo: 'ctx=42 win=63 state=busy'."""
    payload = _read_first_line(STATE_FILE) or "ctx=0 win=0"
    modo = _read_first_line(MODE_FILE) or "idle"
    if modo not in MODOS:
        modo = "idle"
    return f"{payload} state={modo}"


def cmd_bridge(args) -> int:
    """Segura a porta aberta e empurra o estado para o ESP.

    Nunca desiste: se nao houver placa, fica procurando. Se o cabo cair,
    reconecta sozinha — inclusive numa porta COM diferente, que e exatamente
    o que acontece quando voce replug em outra entrada USB.
    """
    def log(msg: str) -> None:
        if (not args.quiet) or args.verbose:
            print(msg, file=sys.stderr, flush=True)

    # Duas pontes brigando pela mesma porta nao adianta nada: a segunda nunca
    # consegue abrir. Pior, ela sobrescreveria o batimento com o proprio pid e
    # o `stop` acabaria matando a errada.
    if bridge_alive() and not args.force:
        log(f"[mochi] ja existe uma ponte rodando (pid {_read_first_line(BEAT_FILE)}). "
            "Use 'mochi.py restart', ou --force se souber o que esta fazendo.")
        return 0

    _write_atomic(BEAT_FILE, str(os.getpid()))

    ser = None
    port = None
    ultimo_envio = ""
    enviado_em = 0.0
    batido_em = 0.0
    ja_avisou = False

    log(f"[mochi] ponte no ar (pid {os.getpid()})")
    log(f"[mochi] estado: {STATE_FILE}")

    try:
        while True:
            agora = time.monotonic()

            # Batimento: e assim que a status line sabe que nao precisa subir
            # outra ponte, e como o doctor sabe que esta tudo vivo.
            if agora - batido_em >= 2.0:
                _write_atomic(BEAT_FILE, str(os.getpid()))
                batido_em = agora

            # (Re)conecta. Redescobre a porta a cada tentativa, entao trocar de
            # entrada USB (COM5 -> COM7) se resolve sozinho.
            if ser is None:
                port = resolve_port(args.port, quiet=True)
                if not port:
                    if not ja_avisou:
                        log("[mochi] nenhuma placa encontrada; procurando...")
                        ja_avisou = True
                    time.sleep(3)
                    continue
                try:
                    ser = open_serial(port, args.baud)
                    _write_atomic(PORT_CACHE, port)
                    ultimo_envio = ""      # forca um envio logo apos conectar
                    ja_avisou = False
                    log(f"[mochi] conectado em {port} @ {args.baud}")
                except Exception as exc:
                    if not ja_avisou:
                        log("[mochi] " + explain_open_error(port, exc))
                        ja_avisou = True
                    ser = None
                    time.sleep(3)
                    continue

            linha = compose_line()
            mudou = linha != ultimo_envio
            velho = (agora - enviado_em) >= args.interval

            if mudou or velho:
                try:
                    ser.write((linha + "\n").encode("ascii", "ignore"))
                    ser.flush()
                    ultimo_envio = linha
                    enviado_em = agora
                    if args.verbose and mudou:
                        log(f"[mochi] -> {linha}")
                except Exception as exc:
                    log(f"[mochi] porta caiu ({exc}); reconectando")
                    try:
                        ser.close()
                    except Exception:
                        pass
                    ser = None
                    continue

            # Descarta o eco 'ok' do firmware para o buffer nao encher.
            try:
                if ser.in_waiting:
                    ser.read(ser.in_waiting)
            except Exception:
                pass

            time.sleep(args.poll)
    except KeyboardInterrupt:
        log("\n[mochi] tchau")
    finally:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        try:
            if _read_first_line(BEAT_FILE) == str(os.getpid()):
                BEAT_FILE.unlink()
        except OSError:
            pass
    return 0


# ============================================================== status line ==

def _pct(valor) -> int:
    """Converte para inteiro 0..100, aguentando None, float e string."""
    try:
        if valor is None:
            return 0
        return max(0, min(100, int(float(valor))))
    except (TypeError, ValueError):
        return 0


def cmd_statusline(args) -> int:
    """Imprime a status line E publica o estado para o mochi.

    Os campos podem faltar: `rate_limits` so aparece para assinante Pro/Max e
    some quando a janela expira; `context_window.used_percentage` vem null no
    inicio da sessao e logo depois de um /compact. Por isso tudo passa por
    .get() com padrao — a status line nao pode quebrar nunca.
    """
    dados = _stdin_json()

    janela = dados.get("context_window") or {}
    limites = dados.get("rate_limits") or {}
    cinco_h = limites.get("five_hour") or {}
    custo = dados.get("cost") or {}
    modelo = dados.get("model") or {}
    espaco = dados.get("workspace") or {}

    ctx = _pct(janela.get("used_percentage"))
    win = _pct(cinco_h.get("used_percentage"))
    try:
        usd = float(custo.get("total_cost_usd") or 0.0)
    except (TypeError, ValueError):
        usd = 0.0
    nome = modelo.get("display_name") or "Claude"
    # A unica fonte confiavel do tamanho da janela: guarda para os hooks.
    _aprende_ctx_size(modelo.get("id") or nome, janela.get("context_window_size"))
    # Prioridade por FONTE, nao por relogio. As duas carimbam "agora", entao
    # desempatar por timestamp so faz a ultima a rodar ganhar — e a status line
    # roda a cada mensagem, enquanto o widget so e lido nos hooks. Resultado:
    # o numero do widget aparecia e sumia. Aqui a regra fica explicita: widget
    # vivo manda, status line e o reserva.
    if le_widget_usage() and cinco_h.get("used_percentage") is not None:
        _guarda_win(win, cinco_h.get("resets_at"), _agora(), "statusline")
    win = win_atual() or win
    diretorio = espaco.get("current_dir") or dados.get("cwd") or ""

    # ---------------------------------------------------------- publicacao ---
    link = os.environ.get("MOCHI_LINK", "serial")

    if link in ("serial", "both"):
        _write_atomic(STATE_FILE, f"ctx={ctx} win={win}")
        # Plug and play: se nao ha ponte viva, sobe uma. No caso comum (ponte
        # ja rodando) isso custa um stat() — barato o bastante para rodar a
        # cada mensagem do assistente.
        if os.environ.get("MOCHI_AUTOSTART", "1") != "0" and not bridge_alive():
            spawn_bridge()

    if link in ("http", "both"):
        _fire_http(f"ctx={ctx}&win={win}")

    # --------------------------------------------------------------- saida ---
    if ctx >= 85:
        cor = "\033[31m"    # vermelho
    elif ctx >= 60:
        cor = "\033[33m"    # ambar
    else:
        cor = "\033[32m"    # verde
    reset, dim = "\033[0m", "\033[2m"

    cheios = ctx // 10
    barra = "\u2588" * cheios + "\u2591" * (10 - cheios)
    pasta = os.path.basename(diretorio.replace("\\", "/").rstrip("/"))

    _print_unicode(
        f"{dim}[{nome}]{reset} {pasta}\n"
        f"{cor}{barra}{reset} {ctx}% ctx {dim}\u00b7{reset} "
        f"5h {win}% {dim}\u00b7{reset} ${usd:.2f}"
    )
    return 0


def _print_unicode(texto: str) -> None:
    """Imprime UTF-8 mesmo com o console em cp1252 (padrao no Windows pt-BR)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(texto)
    except Exception:
        sys.stdout.buffer.write(texto.encode("utf-8", "replace") + b"\n")
        sys.stdout.flush()


def _fire_http(query: str) -> None:
    """GET disparado e esquecido para o ESP na rede local (modo http)."""
    host = os.environ.get("MOCHI_HOST", "mochi.local")
    try:
        import urllib.request
        urllib.request.urlopen(f"http://{host}/tokens?{query}", timeout=0.4).close()
    except Exception:
        pass  # mochi desligado / outra rede: falha em silencio


def cmd_mode(args) -> int:
    """Publica o modo (idle | busy | compact | ask). Chamado pelos hooks."""
    modo = args.modo if args.modo in MODOS else "idle"
    link = os.environ.get("MOCHI_LINK", "serial")
    if link in ("serial", "both"):
        _write_atomic(MODE_FILE, modo)
    if link in ("http", "both"):
        _fire_http(f"state={modo}")
    return 0


# ============================================= numeros vindos do transcript ==

# Quanto da cauda do .jsonl lemos atras do ultimo `usage`. Uma linha de
# assistant raramente passa de poucos KB; 512 KB cobrem varias com folga e
# custam ~1 ms mesmo num transcript de dezenas de MB.
TAIL_BYTES = 512 * 1024

# Janela de contexto. NAO da para chutar: o mesmo modelo roda com 200k ou com
# 1M dependendo da conta e do beta ligado, e o transcript nao diz qual e. Errar
# aqui erra a tela inteira — com 200k assumido numa janela de 1M, 158k de
# contexto viram 79% em vez de 16%.
#
# Entao o tamanho e APRENDIDO: a status line recebe context_window_size pronto
# no JSON e guarda o valor por modelo neste arquivo. Os hooks so consultam. Uma
# unica sessao no terminal ja calibra o Desktop para sempre. Sem nenhuma
# calibracao, MOCHI_CTX_SIZE resolve na mao.
CTX_SIZES_FILE = pathlib.Path(
    os.environ.get("MOCHI_CTX_SIZES_FILE", HOME_CLAUDE / "mochi-ctx-sizes.json"))
CTX_SIZE_PADRAO = 200_000


def _stdin_json() -> dict:
    """JSON que o Claude Code manda no stdin (status line e hooks).

    Com stdin num terminal nao ha o que ler e um read() ficaria pendurado — por
    isso o isatty(). O PowerShell prefixa um BOM ao que manda para um processo
    nativo, e json.loads engasga nele; o lstrip tira.
    """
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        bruto = sys.stdin.read().lstrip("\ufeff\r\n\t ")
        dados = json.loads(bruto) if bruto else {}
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _campo(linha: str, chave: str) -> int:
    """Le `ctx` ou `win` de uma linha 'ctx=42 win=63' ja gravada."""
    for par in linha.split():
        k, _, v = par.partition("=")
        if k == chave:
            return _pct(v)
    return 0


def _ctx_sizes() -> dict:
    try:
        dados = json.loads(CTX_SIZES_FILE.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _ctx_size(modelo: str | None = None) -> int:
    """Tamanho da janela: variavel de ambiente > aprendido > padrao."""
    forcado = os.environ.get("MOCHI_CTX_SIZE")
    if forcado:
        try:
            n = int(forcado)
            if n > 0:
                return n
        except ValueError:
            pass
    if modelo:
        try:
            n = int(_ctx_sizes().get(modelo) or 0)
            if n > 0:
                return n
        except (TypeError, ValueError):
            pass
    return CTX_SIZE_PADRAO


def _aprende_ctx_size(modelo: str | None, tamanho) -> None:
    """Guarda o context_window_size que a status line recebeu, por modelo."""
    try:
        n = int(tamanho or 0)
    except (TypeError, ValueError):
        return
    if not modelo or n <= 0:
        return
    sizes = _ctx_sizes()
    if sizes.get(modelo) == n:
        return
    sizes[modelo] = n
    _write_atomic(CTX_SIZES_FILE, json.dumps(sizes, ensure_ascii=False))


def _tail_lines(path: pathlib.Path) -> list[bytes]:
    with path.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        tamanho = fh.tell()
        fh.seek(max(0, tamanho - TAIL_BYTES))
        bruto = fh.read()
    linhas = bruto.split(b"\n")
    if tamanho > TAIL_BYTES:
        linhas = linhas[1:]      # a primeira veio cortada no meio
    return linhas


def ctx_do_transcript(caminho) -> int | None:
    """% da janela de contexto, recalculado do ultimo `usage` do transcript.

    E o mesmo numero que a status line recebe pronto em
    `context_window.used_percentage`. Aqui ele e refeito na mao porque o hook
    nao recebe esse campo — recebe o caminho do transcript, e la esta o `usage`
    de cada resposta: o que entrou (input + cache lido + cache escrito) mais o
    que saiu e um dia vira entrada.

    Mensagens de subagente (`isSidechain`) sao puladas: o contexto delas e
    outro, e sem isso os olhos abririam de repente no meio de uma busca.

    Devolve None quando nao da para saber — o chamador preserva o valor antigo
    em vez de zerar o mochi.
    """
    if not caminho:
        return None
    try:
        linhas = _tail_lines(pathlib.Path(caminho))
    except (OSError, ValueError, TypeError):
        return None

    for linha in reversed(linhas):
        if b'"usage"' not in linha:
            continue
        try:
            reg = json.loads(linha.decode("utf-8", "replace"))
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(reg, dict):
            continue
        if reg.get("type") != "assistant" or reg.get("isSidechain"):
            continue
        msg = reg.get("message") or {}
        uso = msg.get("usage") or {}
        total = 0
        for chave in ("input_tokens", "cache_read_input_tokens",
                      "cache_creation_input_tokens", "output_tokens"):
            try:
                total += int(uso.get(chave) or 0)
            except (TypeError, ValueError):
                pass
        if total > 0:
            return max(0, min(100, round(100 * total / _ctx_size(msg.get("model")))))
    return None


# ============================================ o limite de 5 horas (a cota) ==

# A cota NAO esta no transcript nem em disco: o app do Desktop busca ao vivo e
# guarda so na memoria (procurei em Local Storage, IndexedDB e main.log). A
# status line recebe ela pronta, mas o Desktop nao desenha status line.
#
# Sobra uma fonte: o relatorio do /usage. Ele nao vira registro de comando no
# transcript, mas quando o usuario cola o texto no chat ele entra como mensagem
# — e o formato e legivel:
#
#   Claude Code usage report (2026-09-09T01:14:59.961Z)
#   Plan limits:
#   - session-0: 13% (resets 2026-09-09T05:20:00.081310+00:00)
#   - weekly_all-1: 22% (resets 2026-09-13T07:00:00.081331+00:00)
#
# O "resets" e o que faz isso valer a pena. Com ele o numero nunca mente:
# exato no instante do relatorio, PISO depois (consumo so sobe dentro da
# janela) e ZERO de verdade quando a hora do reset passa.
WIN_FILE = pathlib.Path(os.environ.get("MOCHI_WIN_FILE", HOME_CLAUDE / "mochi-win.json"))

MARCA_USAGE = "Claude Code usage report"


def _agora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(txt):
    # `resets_at` da status line vem como epoch (numero), nao ISO. Sem isto o
    # _iso devolvia None e win_atual() nunca zerava a cota quando a janela
    # virava: o mochi ficava preso no ultimo percentual para sempre.
    if isinstance(txt, (int, float)) and not isinstance(txt, bool):
        try:
            return datetime.datetime.fromtimestamp(txt, datetime.timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    try:
        d = datetime.datetime.fromisoformat((txt or "").strip().replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)


def _le_win() -> dict:
    try:
        dados = json.loads(WIN_FILE.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def win_atual() -> int:
    """A cota agora: 0 se a janela ja virou, senao o ultimo valor conhecido."""
    dados = _le_win()
    reset = _iso(dados.get("resets"))
    if reset and _agora() >= reset:
        return 0          # a janela rolou — 0 aqui e verdade, nao chute
    return _pct(dados.get("pct"))


def _guarda_win(pct: int, resets: str | None, visto, fonte: str) -> None:
    dados = _le_win()
    anterior = _iso(dados.get("visto"))
    if anterior and visto and visto <= anterior:
        return            # ja temos algo mais novo
    # O widget nao manda `resets` (so tem o numero, ja atualizado ao vivo), e
    # preservar o `resets` antigo do slot ajuda quando ele so ficou em silencio
    # por alguns minutos. Mas depois de o PC dormir/desconectar por horas, esse
    # `resets` HERDADO ja passou — e um pct FRESCO (do widget) com um reset
    # MORTO (de uma fonte antiga) fazia win_atual() zerar a cota, mentindo.
    # So descarta o herdado; um `resets` que esta fonte trouxe agora, mesmo
    # vencido, e informacao real dela (ex.: usage-report dizendo que aquela
    # janela ja fechou) e continua valendo.
    herdado = dados.get("resets")
    if not resets and herdado:
        reset_iso = _iso(herdado)
        if reset_iso and (visto or _agora()) >= reset_iso:
            herdado = None
    dados.update({"pct": _pct(pct), "resets": resets or herdado,
                  "fonte": fonte,
                  "visto": (visto or _agora()).isoformat()})
    _write_atomic(WIN_FILE, json.dumps(dados, ensure_ascii=False))


def _texto_da_mensagem(reg: dict) -> str:
    """Texto de um registro do transcript, seja string ou lista de blocos."""
    conteudo = (reg.get("message") or {}).get("content")
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        return " ".join(b.get("text", "") for b in conteudo
                        if isinstance(b, dict) and b.get("type") == "text")
    return ""


def le_relatorio_usage(caminho) -> bool:
    """Procura o /usage mais recente colado no chat e guarda a cota.

    Devolve True se aprendeu algo novo.
    """
    if not caminho:
        return False
    try:
        linhas = _tail_lines(pathlib.Path(caminho))
    except (OSError, ValueError, TypeError):
        return False

    for linha in reversed(linhas):
        if MARCA_USAGE.encode() not in linha:
            continue
        try:
            reg = json.loads(linha.decode("utf-8", "replace"))
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(reg, dict) or reg.get("type") != "user":
            continue
        texto = _texto_da_mensagem(reg)
        if MARCA_USAGE not in texto:
            continue

        # cabecalho: "Claude Code usage report (2026-09-09T01:14:59.961Z)"
        cabecalho = texto.split(MARCA_USAGE, 1)[1].partition("(")[2].partition(")")[0]
        quando = _iso(cabecalho) or _iso(reg.get("timestamp"))

        for l in texto.splitlines():
            l = l.strip()
            # "- session-0: 13% (resets 2026-09-09T05:20:00.081310+00:00)"
            if not l.startswith("- session"):
                continue
            pct_txt, _, resto = l.partition(":")[2].strip().partition("%")
            try:
                pct = int(pct_txt.strip())
            except ValueError:
                continue
            resets = resto.partition("(resets")[2].strip().rstrip(")").strip() or None
            _guarda_win(pct, resets, quando, "usage-report")
            return True
    return False


# ================================================ cota do widget claude-usage ==

# O claude-usage (extensao Chrome + servidor local em 127.0.0.1:7878) le a API
# real de uso do claude.ai a cada 15s. Enquanto ele estiver de pe esta e a
# MELHOR fonte da cota: numero vivo, sem depender de colar /usage no chat — que
# e exatamente o buraco do Claude Desktop, onde a status line nunca roda.
USAGE_URL = os.environ.get("MOCHI_USAGE_URL", "http://127.0.0.1:7878/usage")

# Widget aberto mas extensao morta (Chrome fechado, sessao caiu) devolve o
# ultimo numero para sempre. Sem este corte ele sobrescreveria o /usage do
# transcript a cada hook e congelaria o mochi num valor velho.
USAGE_MAX_IDADE_S = 300


def le_widget_usage() -> str:
    """Le a cota do widget claude-usage.

    Devolve "" quando aprendeu, ou o motivo da recusa. Motivo em vez de False
    porque as duas falhas pedem conserto diferente: "nao respondeu" e o widget
    fechado, "dado de X min atras" e o widget aberto com a extensao parada — e
    quem so ve um bool sai procurando o problema errado.
    """
    try:
        import urllib.request
        with urllib.request.urlopen(USAGE_URL, timeout=0.4) as r:
            dados = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return "nao respondeu (widget fechado?)"

    # `atualizado_em` e datetime.now() sem fuso — compare com now() sem fuso
    # tambem, senao 3h de diferenca fazem todo dado parecer velho.
    try:
        visto = datetime.datetime.fromisoformat(dados.get("atualizado_em") or "")
    except (TypeError, ValueError):
        return "sem atualizado_em valido"
    idade = abs((datetime.datetime.now() - visto).total_seconds())
    if idade > USAGE_MAX_IDADE_S:
        return (f"dado de {idade/60:.0f} min atras "
                "(widget de pe, extensao parada; logado no claude.ai?)")

    pct = (dados.get("sessao_atual") or {}).get("percentual")
    if pct is None:
        return "sem sessao_atual.percentual"
    # ponytail: resets=None de proposito. O widget so publica o reset ja
    # humanizado ("2h15min"), e enquanto ele estiver vivo nao precisamos
    # extrapolar nada — o proprio numero zera quando a janela vira. Se ele
    # morrer, _guarda_win preserva o resets que o /usage tinha deixado.
    _guarda_win(_pct(pct), None, _agora(), "widget")
    return ""


def cmd_tokens(args) -> int:
    """Publica numeros + modo de uma vez so. E o que os hooks chamam.

    Existe porque o Claude Desktop nao desenha status line: la o
    `mochi.py statusline` nunca roda, e sem isto os olhos ficariam parados no
    ultimo numero que veio do terminal. Hooks rodam nos dois, e todo hook
    recebe o transcript no stdin.

    O que NAO da para recalcular daqui e o limite de 5 horas: ele so aparece no
    JSON da status line, nunca no transcript. Por isso `win` e preservado como
    estava, em vez de virar zero e mentir que a cota se renovou.
    """
    modo = args.modo if args.modo in MODOS else "idle"
    dados = _stdin_json()

    transcript = dados.get("transcript_path")
    anterior = _read_first_line(STATE_FILE)
    ctx = ctx_do_transcript(transcript)
    if ctx is None:
        ctx = _campo(anterior, "ctx")

    le_relatorio_usage(transcript)
    le_widget_usage()
    win = win_atual() or _campo(anterior, "win")

    link = os.environ.get("MOCHI_LINK", "serial")
    if link in ("serial", "both"):
        _write_atomic(STATE_FILE, f"ctx={ctx} win={win}")
        _write_atomic(MODE_FILE, modo)
        if os.environ.get("MOCHI_AUTOSTART", "1") != "0" and not bridge_alive():
            spawn_bridge()
    if link in ("http", "both"):
        _fire_http(f"ctx={ctx}&win={win}")
        _fire_http(f"state={modo}")

    if getattr(args, "verbose", False):
        print(f"ctx={ctx} win={win} state={modo}")
    return 0


# ================================================================= install ===

def _fs(p) -> str:
    """Caminho com barras normais.

    No Windows a status line roda pelo Git Bash quando ele existe, e o Git Bash
    trata a contrabarra como escape: 'C:\\Users\\dev' chega como 'C:Usersdev' e
    o comando falha calado. Barra normal funciona nos dois shells.
    """
    return str(p).replace("\\", "/")


def _short_path(p) -> str:
    """Caminho curto 8.3 do Windows, para eliminar espacos.

    A status line aceita apenas uma STRING de comando, sem lista de argumentos.
    Se o caminho do python tiver espaco ('C:/Program Files/...'), o PowerShell
    trata a string entre aspas como texto, nao como comando. O nome curto
    ('C:/PROGRA~1/...') resolve sem depender de aspas.
    """
    p = str(p)
    if " " not in p or not IS_WINDOWS:
        return p
    try:
        import ctypes
        from ctypes import wintypes
        fn = ctypes.windll.kernel32.GetShortPathNameW
        fn.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        fn.restype = wintypes.DWORD
        buf = ctypes.create_unicode_buffer(1024)
        n = fn(p, buf, 1024)
        if n and n < 1024 and " " not in buf.value:
            return buf.value
    except Exception:
        pass
    return p


def _is_mochi(obj) -> bool:
    return "mochi" in json.dumps(obj).lower()


def cmd_install(args) -> int:
    import shutil

    origem = pathlib.Path(__file__).resolve()
    destino = HOME_CLAUDE / "mochi.py"

    HOME_CLAUDE.mkdir(parents=True, exist_ok=True)
    if not destino.exists() or destino.resolve() != origem:
        shutil.copyfile(origem, destino)
    print(f"[mochi] script em {destino}")

    py = _short_path(sys.executable)
    script = _short_path(destino)

    # Status line: so aceita string. Caminhos absolutos, com barra normal e
    # sem espacos, funcionam tanto no Git Bash quanto no PowerShell.
    status_cmd = f"{_fs(py)} {_fs(script)} statusline"

    # Hooks: aceitam forma exec (command + args), que nao passa por shell
    # nenhum. Aqui o caminho original serve, espacos inclusive.
    def hook(modo: str) -> dict:
        return {"hooks": [{
            "type": "command",
            "command": sys.executable,
            "args": [str(destino), "tokens", modo],
        }]}

    settings_path = HOME_CLAUDE / "settings.json"
    try:
        cfg = (json.loads(settings_path.read_text(encoding="utf-8"))
               if settings_path.exists() else {})
        if not isinstance(cfg, dict):
            cfg = {}
    except (json.JSONDecodeError, OSError):
        print(f"[mochi] {settings_path} esta ilegivel; nao vou sobrescrever.")
        return 1

    if settings_path.exists():
        backup = settings_path.with_suffix(".json.bak-mochi")
        shutil.copyfile(settings_path, backup)
        print(f"[mochi] backup do settings.json em {backup}")

    cfg["statusLine"] = {"type": "command", "command": status_cmd, "padding": 1}

    if not args.sem_hooks:
        hooks = cfg.get("hooks")
        if not isinstance(hooks, dict):
            hooks = {}
        for evento, modo in (("SessionStart", "idle"),
                             ("UserPromptSubmit", "busy"),
                             # PostToolUse e quem da o "ao vivo": dispara a cada
                             # ferramenta, entao os numeros andam durante a
                             # resposta, e nao so no fim dela.
                             ("PostToolUse", "busy"),
                             # Notification = o Claude parou para perguntar
                             # alguma coisa (permissao, escolha): "?" na tela.
                             ("Notification", "ask"),
                             ("Stop", "idle"),
                             ("PreCompact", "compact"),
                             ("PostCompact", "busy"),
                             ("SessionEnd", "idle")):
            # Preserva hooks de terceiros; troca so os nossos (idempotente).
            outros = [m for m in hooks.get(evento, []) if not _is_mochi(m)]
            hooks[evento] = outros + [hook(modo)]
        cfg["hooks"] = hooks

    settings_path.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[mochi] settings.json atualizado ({settings_path})")
    print(f"[mochi] statusLine -> {status_cmd}")

    spawn_bridge()
    time.sleep(2.5)
    print("[mochi] ponte:",
          "no ar" if bridge_alive() else "NAO subiu (rode: mochi.py doctor)")
    print("\nReinicie o Claude Desktop para a status line e os hooks valerem.")
    return 0


def cmd_uninstall(args) -> int:
    stop_bridge()
    settings_path = HOME_CLAUDE / "settings.json"
    try:
        cfg = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("[mochi] settings.json nao encontrado/ilegivel; nada a limpar")
        return 0
    if _is_mochi(cfg.get("statusLine", {})):
        cfg.pop("statusLine", None)
    hooks = cfg.get("hooks")
    if isinstance(hooks, dict):
        for evento in list(hooks):
            hooks[evento] = [m for m in hooks[evento] if not _is_mochi(m)]
            if not hooks[evento]:
                hooks.pop(evento)
        if not hooks:
            cfg.pop("hooks", None)
    settings_path.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("[mochi] removido do settings.json (mochi.py continua em ~/.claude)")
    return 0


# ================================================================== doctor ===

def cmd_ports(args) -> int:
    linhas = list_candidates()
    if not linhas:
        print("nenhuma porta serial no sistema.")
        return 1
    print(f"{'nota':>5}  {'porta':<8} {'descricao':<38} motivo")
    for nota, dev, desc, motivo in linhas:
        print(f"{nota:>5}  {dev:<8} {desc[:38]:<38} {motivo}")
    escolhida = resolve_port()
    print(f"\nescolhida: {escolhida or 'NENHUMA'}")
    return 0


def cmd_send(args) -> int:
    if bridge_alive():
        print("a ponte esta rodando e segurando a porta. Pare com:  mochi.py stop")
        return 1
    port = resolve_port(args.port)
    if not port:
        print("nao achei nenhuma placa.")
        return 1
    try:
        ser = open_serial(port, BAUD)
    except Exception as exc:
        print(explain_open_error(port, exc))
        return 1
    try:
        ser.write((args.linha + "\n").encode("ascii", "ignore"))
        ser.flush()
        time.sleep(0.4)
        print(f"{port} <- {args.linha}")
        print(f"{port} -> {ser.read(200)!r}")
        if args.hold > 0:
            print(f"segurando a porta aberta por {args.hold:.0f}s "
                  "(feche o terminal ou espere passar pra soltar)...")
            time.sleep(args.hold)
    finally:
        ser.close()
    return 0


def cmd_doctor(args) -> int:
    ok = True
    print("== claude-mochi doctor ==\n")

    print(f"python            {sys.version.split()[0]}  ({sys.executable})")
    try:
        import serial
        print(f"pyserial          {serial.__version__}")
    except ImportError:
        print(f"pyserial          AUSENTE -> {sys.executable} -m pip install pyserial")
        ok = False

    print("\n-- portas --")
    alvo = None
    try:
        for nota, dev, desc, motivo in list_candidates():
            marca = "*" if nota > 0 else " "
            print(f" {marca} {dev:<8} nota {nota:>4}  {desc[:34]:<34} {motivo}")
        alvo = resolve_port(args.port, quiet=True)
        print(f"\nporta escolhida   {alvo or 'NENHUMA (o mochi esta plugado?)'}")
        if not alvo:
            ok = False
    except SystemExit:
        ok = False

    print("\n-- ponte --")
    viva = bridge_alive()
    pid = _read_first_line(BEAT_FILE)
    print(f"rodando           {('sim (pid ' + pid + ')') if viva else 'NAO'}")
    if not viva:
        ok = False
    print(f"log               {LOG_FILE}")

    print("\n-- arquivos de estado --")
    for rotulo, caminho in (("estado", STATE_FILE), ("modo", MODE_FILE)):
        if caminho.exists():
            idade = time.time() - caminho.stat().st_mtime
            print(f"{rotulo:<17} {_read_first_line(caminho)!r}  ({idade:.0f}s atras)")
        else:
            print(f"{rotulo:<17} ainda nao existe (status line e hooks nao rodaram)")
    sizes = _ctx_sizes()
    print(f"{'janela':<17} " + (", ".join(f"{m}={n:,}" for m, n in sizes.items())
                                if sizes else f"nao aprendida (assumindo {CTX_SIZE_PADRAO:,})"))

    print("\n-- cota de 5h --")
    motivo = le_widget_usage()
    w = _le_win()
    print(f"{'valor':<17} {win_atual()}%  (fonte: {w.get('fonte') or 'nenhuma'})")
    print(f"{'no mochi agora':<17} {_campo(_read_first_line(STATE_FILE), 'win')}%")
    print(f"{'widget usage':<17} " + (motivo or "ok, cota veio dele"))
    print(f"{'':<17} {USAGE_URL}")

    print("\n-- claude code --")
    settings_path = HOME_CLAUDE / "settings.json"
    try:
        cfg = json.loads(settings_path.read_text(encoding="utf-8"))
        aponta = _is_mochi(cfg.get("statusLine", {}))
        print("statusLine        " + ("mochi OK" if aponta else "NAO aponta para o mochi"))
        if not aponta:
            ok = False
        n = sum(1 for ms in (cfg.get("hooks") or {}).values()
                for m in ms if _is_mochi(m))
        print(f"hooks do mochi    {n}")
    except (OSError, json.JSONDecodeError):
        print("settings.json     nao encontrado -> rode: mochi.py install")
        ok = False

    # Teste de ponta a ponta so quando a ponte nao esta segurando a porta.
    if alvo and not viva:
        print("\n-- firmware --")
        print("respondeu 'ok'    " + ("sim" if probe_port(alvo) else "NAO"))

    print("\n=> " + ("tudo certo" if ok else "tem coisa faltando (veja acima)"))
    return 0 if ok else 1


def cmd_start(args) -> int:
    if bridge_alive():
        print(f"ponte ja esta rodando (pid {_read_first_line(BEAT_FILE)})")
        return 0
    spawn_bridge(args.port)
    for _ in range(40):
        if bridge_alive():
            print(f"ponte no ar (pid {_read_first_line(BEAT_FILE)})")
            return 0
        time.sleep(0.25)
    print(f"a ponte nao subiu. Veja o log: {LOG_FILE}")
    return 1


def cmd_stop(args) -> int:
    print("ponte encerrada" if stop_bridge() else "nao havia ponte rodando")
    return 0


def cmd_restart(args) -> int:
    stop_bridge()
    time.sleep(0.5)
    return cmd_start(args)


# ==================================================================== main ===

def main() -> int:
    ap = argparse.ArgumentParser(
        description="claude-mochi — lado do PC (Windows / macOS / Linux)")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("statusline", help="status line do Claude Code (JSON no stdin)")
    p.set_defaults(func=cmd_statusline)

    p = sub.add_parser("mode", help="publica o modo (chamado pelos hooks)")
    p.add_argument("modo", nargs="?", default="idle",
                   choices=list(MODOS))
    p.set_defaults(func=cmd_mode)

    p = sub.add_parser("tokens", help="numeros + modo, do transcript (hooks)")
    p.add_argument("modo", nargs="?", default="busy",
                   choices=list(MODOS))
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_tokens)

    p = sub.add_parser("bridge", help="ponte serial em primeiro plano")
    p.add_argument("--port", help="porta serial (padrao: detecta sozinho)")
    p.add_argument("--baud", type=int, default=BAUD)
    p.add_argument("--interval", type=float, default=5.0,
                   help="reenvio periodico em s (recupera reset do ESP)")
    p.add_argument("--poll", type=float, default=0.2)
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="sobe mesmo se ja houver uma ponte viva")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_bridge)

    p = sub.add_parser("start", help="sobe a ponte em segundo plano")
    p.add_argument("--port")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("stop", help="encerra a ponte")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("restart", help="reinicia a ponte")
    p.add_argument("--port")
    p.set_defaults(func=cmd_restart)

    p = sub.add_parser("install", help="instala em ~/.claude e ajusta settings.json")
    p.add_argument("--sem-hooks", action="store_true", help="so a status line")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("uninstall", help="desfaz o install")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("doctor", help="diagnostico completo")
    p.add_argument("--port")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("ports", help="lista as portas e a nota de cada uma")
    p.set_defaults(func=cmd_ports)

    p = sub.add_parser("send", help="manda uma linha crua (teste)")
    p.add_argument("linha")
    p.add_argument("--port")
    p.add_argument("--hold", type=float, default=0.0,
                    help="segura a porta aberta por N segundos antes de fechar. "
                         "Fechar a porta reseta o ESP (mesmo com DTR/RTS baixos "
                         "na abertura) e apaga o que voce acabou de mandar antes "
                         "de dar tempo de olhar — use --hold pra testar de verdade.")
    p.set_defaults(func=cmd_send)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
