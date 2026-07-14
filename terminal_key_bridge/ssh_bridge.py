"""Persistent interactive SSH terminal transport."""

from __future__ import annotations

import socket
import threading
from typing import Callable

import paramiko


class BridgeError(RuntimeError):
    pass


class SSHBridgeClosed(Exception):
    """Internal signal raised when the remote PTY reaches EOF."""


class SSHBridge:
    def __init__(self, on_error: Callable[[str], None]) -> None:
        self._on_error = on_error
        self._client: paramiko.SSHClient | None = None
        self._channel: paramiko.Channel | None = None
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._channel is not None and not self._channel.closed

    def connect(self, host: str, port: int, username: str, password: str, timeout: float = 10) -> None:
        self.close()
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                host, port=port, username=username, password=password,
                timeout=timeout, auth_timeout=timeout, banner_timeout=timeout,
                look_for_keys=False, allow_agent=False,
            )
            transport = client.get_transport()
            if transport is None:
                raise BridgeError("SSH-транспорт не создан")
            channel = client.invoke_shell(term="xterm-256color", width=120, height=40)
        except (OSError, socket.error, paramiko.SSHException, BridgeError) as exc:
            client.close()
            raise BridgeError(str(exc)) from exc
        self._client, self._channel = client, channel
        threading.Thread(target=self._drain_output, args=(channel,), daemon=True).start()

    def _drain_output(self, channel: paramiko.Channel) -> None:
        """Drain remote PTY output so its SSH window cannot fill and block input."""
        try:
            while self._channel is channel and not channel.closed:
                if not channel.recv(4096):
                    raise SSHBridgeClosed
        except (OSError, paramiko.SSHException, SSHBridgeClosed):
            if self._channel is channel:
                self.close()
                self._on_error("SSH-соединение разорвано")

    def send(self, data: bytes) -> None:
        with self._lock:
            try:
                if not self.connected or self._channel is None:
                    raise BridgeError("соединение закрыто")
                self._channel.sendall(data)
            except (OSError, paramiko.SSHException, BridgeError) as exc:
                self.close()
                self._on_error(str(exc))

    def close(self) -> None:
        channel, client = self._channel, self._client
        self._channel = self._client = None
        if channel is not None:
            try:
                channel.close()
            except Exception:
                pass
        if client is not None:
            client.close()
