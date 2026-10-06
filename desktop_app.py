import socket
import threading

from werkzeug.serving import make_server

from app import app


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "Desktop component is not installed. Run INSTALL_DESKTOP_APP.bat once, then try again."
        ) from exc

    webview.settings['ALLOW_DOWNLOADS'] = True

    port = _free_port()
    server = make_server("127.0.0.1", port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        webview.create_window(
            "Sol Plaatje University Timetable Optimizer",
            f"http://127.0.0.1:{port}/login",
            width=1280,
            height=820,
            min_size=(1000, 650),
        )
        webview.start()
    finally:
        server.shutdown()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
