"""Browser navigation burst with one idle speculative connection; bounded sockets."""
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from backend.infrastructure.composition.factories.local_browser import build_local_saved
from backend.infrastructure.config.schemas.http import LocalBrowserHttpConfiguration
from tests.integration.test_r4_local_http import available_port


def navigation_burst(app):
    port = app.server.server_port
    blocker = socket.create_connection(("127.0.0.1", port), timeout=1)
    deadline = time.monotonic() + 1
    while app.server._active is None and time.monotonic() < deadline:
        time.sleep(.005)
    assert app.server._active is not None
    clients = []

    def connect(index):
        try:
            connection = socket.create_connection(("127.0.0.1", port), timeout=1)
            connection.sendall(f"GET /assets/app.js HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())
            return index, connection
        except OSError:
            return index, None

    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            clients = list(pool.map(connect, range(6)))
        blocker.close()
        outcomes = []
        for _index, connection in clients:
            status = "CONNECT_FAILED"
            if connection is not None:
                connection.settimeout(3)
                try:
                    status = "HTTP_200" if connection.recv(256).startswith(b"HTTP/1.0 200") else "INVALID_RESPONSE"
                except OSError:
                    status = "RESPONSE_FAILED"
                finally:
                    connection.close()
            outcomes.append(status)
        return outcomes
    finally:
        blocker.close()
        for _, connection in clients:
            if connection is not None:
                connection.close()


def test_navigation_assets_survive_six_connections_and_idle_speculation(tmp_path):
    app = build_local_saved(LocalBrowserHttpConfiguration(available_port()), tmp_path / "store", create=True)
    thread = threading.Thread(target=app.serve_forever)
    thread.start()
    assert app.server._running.wait(2)
    try:
        assert navigation_burst(app) == ["HTTP_200"] * 6
    finally:
        app.close()
        thread.join(5)
