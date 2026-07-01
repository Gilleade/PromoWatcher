"""
Sobe o watcher (backend) e a interface Streamlit (frontend) juntos, com um
único comando: `python run_app.py`.

O front é apenas para acompanhamento e gerenciamento básico (dashboard,
promoções, mensagens e CRUD de alertas) — quem faz o trabalho de verdade é o
watcher rodando em segundo plano.
"""
import subprocess
import sys
import threading
import time

WATCHER_CMD = [sys.executable, "watch_promos.py"]
UI_CMD = [sys.executable, "-m", "streamlit", "run", "run_ui.py"]

_shutdown = threading.Event()


def _stream_output(process: subprocess.Popen, prefix: str):
    for line in iter(process.stdout.readline, ""):
        if not line:
            break
        print(f"[{prefix}] {line.rstrip()}")
    process.stdout.close()


def _start(cmd, prefix: str) -> subprocess.Popen:
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    thread = threading.Thread(target=_stream_output, args=(process, prefix), daemon=True)
    thread.start()
    return process


def _stop(process: subprocess.Popen, prefix: str, timeout: float = 8.0):
    if process.poll() is not None:
        return
    print(f"[run_app] encerrando {prefix}...")
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[run_app] {prefix} não encerrou a tempo, forçando kill...")
        process.kill()
        process.wait()


def main():
    print("[run_app] iniciando watcher e interface Streamlit...")
    watcher = _start(WATCHER_CMD, "watcher")
    ui = _start(UI_CMD, "ui")

    try:
        while not _shutdown.is_set():
            time.sleep(1)
            watcher_status = watcher.poll()
            ui_status = ui.poll()
            if watcher_status is not None:
                print(f"[run_app] watcher encerrou sozinho (código {watcher_status}) — parando tudo.")
                break
            if ui_status is not None:
                print(f"[run_app] interface encerrou sozinha (código {ui_status}) — parando tudo.")
                break
    except KeyboardInterrupt:
        print("\n[run_app] Ctrl+C recebido, encerrando watcher e interface...")
    finally:
        _stop(ui, "ui")
        _stop(watcher, "watcher")
        print("[run_app] finalizado.")


if __name__ == "__main__":
    main()
