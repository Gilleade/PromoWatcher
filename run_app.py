"""
Sobe o watcher (backend), a API (FastAPI) e o frontend web (Vite/React)
juntos, com um único comando: `python run_app.py`.

Quem faz o trabalho de verdade é o watcher, rodando em segundo plano. A
API expõe os dados (catálogo de produtos, feed, alertas, cupons) para o
frontend web, que é a interface principal de acompanhamento e gestão.

A interface Streamlit antiga (`run_ui.py`) não sobe mais por padrão —
ela continua disponível para depuração pontual (`streamlit run run_ui.py`),
mas o frontend web em `web/` é quem recebe manutenção.
"""
import platform
import subprocess
import sys
import threading
import time

IS_WINDOWS = platform.system() == "Windows"

WATCHER_CMD = [sys.executable, "-u", "watch_promos.py"]
API_CMD = [sys.executable, "-u", "-m", "uvicorn", "app.api.main:app", "--host", "127.0.0.1", "--port", "8000"]
# `shell=True` com a string completa evita o problema comum no Windows de
# `npm`/`npm.cmd` não ser executável diretamente via CreateProcess.
WEB_CMD = "npm run dev --prefix web"

_shutdown = threading.Event()


def _stream_output(process: subprocess.Popen, prefix: str):
    for line in iter(process.stdout.readline, ""):
        if not line:
            break
        print(f"[{prefix}] {line.rstrip()}")
    process.stdout.close()


def _start(cmd, prefix: str, *, shell: bool = False) -> subprocess.Popen:
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, shell=shell,
    )
    thread = threading.Thread(target=_stream_output, args=(process, prefix), daemon=True)
    thread.start()
    return process


def _stop(process: subprocess.Popen, prefix: str, timeout: float = 8.0):
    if process.poll() is not None:
        return
    print(f"[run_app] encerrando {prefix}...")
    if IS_WINDOWS:
        # `terminate()` sozinho mataria só o processo raiz (ex.: o `cmd.exe`
        # do `npm run dev`), deixando o processo node/vite filho órfão.
        # `taskkill /T` mata a árvore inteira.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        process.wait()
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[run_app] {prefix} não encerrou a tempo, forçando kill...")
        process.kill()
        process.wait()


def main():
    print("[run_app] iniciando watcher, API e frontend web...")
    processes = [
        (_start(WATCHER_CMD, "watcher"), "watcher"),
        (_start(API_CMD, "api"), "api"),
        (_start(WEB_CMD, "web", shell=True), "web"),
    ]

    try:
        while not _shutdown.is_set():
            time.sleep(1)
            for process, name in processes:
                status = process.poll()
                if status is not None:
                    print(f"[run_app] {name} encerrou sozinho (código {status}) — parando tudo.")
                    raise SystemExit
    except (KeyboardInterrupt, SystemExit):
        print("\n[run_app] encerrando watcher, API e frontend...")
    finally:
        for process, name in reversed(processes):
            _stop(process, name)
        print("[run_app] finalizado.")


if __name__ == "__main__":
    main()
