from __future__ import annotations

import socket
import threading
from collections.abc import Callable

HOST = "127.0.0.1"
PORT = 50781
ACTIVATE = b"activate"


class SingleInstance:
    def __init__(self, port: int = PORT) -> None:
        self.port = port
        self._sock: socket.socket | None = None

    def acquire(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((HOST, self.port))
            sock.listen(8)
        except OSError:
            sock.close()
            return False
        self._sock = sock
        return True

    def notify(self) -> None:
        try:
            with socket.create_connection((HOST, self.port), timeout=3) as conn:
                conn.sendall(ACTIVATE)
        except OSError:
            pass

    def serve(self, on_activate: Callable[[], None]) -> None:
        def loop() -> None:
            assert self._sock is not None
            while True:
                conn, _ = self._sock.accept()
                with conn:
                    if not conn.recv(len(ACTIVATE)):
                        continue
                    conn.recv(1)
                    on_activate()

        threading.Thread(target=loop, daemon=True, name="single-instance").start()
