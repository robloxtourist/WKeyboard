#!/usr/bin/env python3
"""Tk desktop client for TerminalKeyBridge."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from .ssh_bridge import BridgeError, SSHBridge
from .terminal_api import hangup_command, key_command, remote_button_command


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("WKeyboard")
        self.geometry("800x740")
        self.minsize(800, 720)
        self.configure(bg="#050a07")
        self.bridge = SSHBridge(lambda msg: self.events.put(("error", msg)))
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.capture = False
        self.sent_keys = 0
        self.pause_started: float | None = None
        self.pause_release_job: str | None = None
        self.key_history: list[tk.Label] = []
        self.remote_open = False
        self.compact_position: tuple[int, int] | None = None
        self._configure_styles()
        self._build()
        self.bind_all("<KeyPress>", self._key_down)
        self.bind_all("<KeyRelease>", self._key_up)
        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.after(100, self._poll)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Fluent.TEntry", fieldbackground="#020604", foreground="#9cffb8",
                        insertcolor="#39ff88", bordercolor="#1b5e32", lightcolor="#1b5e32",
                        darkcolor="#1b5e32", padding=(12, 10), font=("DejaVu Sans Mono", 10))
        style.map("Fluent.TEntry", bordercolor=[("focus", "#39ff88")])
        style.configure("Accent.TButton", background="#123d22", foreground="#9cffb8",
                        borderwidth=1, padding=(16, 11), font=("DejaVu Sans Mono", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#1d6b38"), ("disabled", "#102b19")])

    def _build(self) -> None:
        root = tk.Frame(self, bg="#050a07", padx=30, pady=26,
                        highlightbackground="#1b5e32", highlightthickness=1)
        root.configure(width=800, height=740)
        root.pack(side="left", fill="y")
        root.pack_propagate(False)
        header = tk.Frame(root, bg="#050a07")
        header.pack(fill="x")
        tk.Label(header, text="[ WKEYBOARD // SSH TERMINAL ]", bg="#050a07", fg="#39ff88",
                 font=("DejaVu Sans Mono", 10, "bold")).pack(side="left", anchor="n")
        self.remote_toggle = tk.Button(header, text="☷  Пульт", command=self._toggle_remote,
                                       bg="#0d2415", activebackground="#1d6b38", fg="#9cffb8",
                                       activeforeground="#ffffff", relief="groove", bd=2,
                                       padx=16, pady=9, font=("DejaVu Sans Mono", 10, "bold"), cursor="hand2")
        self.remote_toggle.pack(side="right", anchor="n")
        self.capture_lamp = tk.Label(header, text="● CAPTURE OFF", bg="#050a07", fg="#ff3b3b",
                                     font=("DejaVu Sans Mono", 10, "bold"), padx=16, pady=9)
        self.capture_lamp.pack(side="right", anchor="n")
        tk.Label(root, text="WKeyboard",
                 bg="#050a07", fg="#9cffb8", justify="left",
                 font=("DejaVu Sans Mono", 24, "bold")).pack(anchor="w", pady=(4, 0))
        tk.Label(root, text="Virtual Keyboard // CRT MODE", bg="#050a07", fg="#5fa874",
                 font=("DejaVu Sans Mono", 11)).pack(anchor="w", pady=(0, 18))

        connection = tk.Frame(root, bg="#08150d", padx=20, pady=18,
                              highlightbackground="#1b5e32", highlightthickness=1)
        connection.pack(fill="x")
        tk.Label(connection, text="> SSH CONNECTION", bg="#08150d", fg="#39ff88",
                 font=("DejaVu Sans Mono", 13, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))
        self.host = self._field(connection, 1, 0, "IP-адрес", "10.1.0.", width=22)
        self.port = self._field(connection, 1, 1, "SSH-порт", "22", width=9)
        self.user = self._field(connection, 1, 2, "Логин", "admin", width=13)
        self.password = self._field(connection, 1, 3, "Пароль", "123", width=13)
        self.button = ttk.Button(connection, text="Подключиться", style="Accent.TButton", command=self._toggle_connection)
        self.button.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(16, 0))
        connection.columnconfigure(0, weight=3)
        connection.columnconfigure(1, weight=1)
        connection.columnconfigure(2, weight=2)
        connection.columnconfigure(3, weight=2)

        self.status = tk.StringVar(value="Не подключено")
        self.capture_text = tk.StringVar(value="Передача клавиш выключена")
        self.sent_text = tk.StringVar(value="Отправлено команд: 0")
        state_card = tk.Frame(root, bg="#08150d", padx=20, pady=16, highlightbackground="#1b5e32", highlightthickness=1)
        state_card.pack(fill="x", pady=12)
        self.status_dot = tk.Label(state_card, text="●", bg="#08150d", fg="#43694d", font=("DejaVu Sans Mono", 16))
        self.status_dot.grid(row=0, column=0, rowspan=2, padx=(0, 12))
        tk.Label(state_card, textvariable=self.status, bg="#08150d", fg="#9cffb8",
                 font=("DejaVu Sans Mono", 11, "bold")).grid(row=0, column=1, sticky="w")
        tk.Label(state_card, textvariable=self.capture_text, bg="#08150d", fg="#5fa874",
                 font=("DejaVu Sans Mono", 9)).grid(row=1, column=1, sticky="w")
        tk.Label(state_card, textvariable=self.sent_text, bg="#08150d", fg="#39ff88",
                 font=("DejaVu Sans Mono", 10, "bold")).grid(row=0, column=2, rowspan=2, sticky="e")
        state_card.columnconfigure(1, weight=1)
        self.capture_button = tk.Button(state_card, text="Включить захват", command=self._toggle_capture,
                                        state="disabled", bg="#102b19", activebackground="#1d6b38",
                                        disabledforeground="#43694d", fg="#9cffb8", activeforeground="#ffffff",
                                        relief="groove", bd=2, padx=14, pady=9,
                                        font=("DejaVu Sans Mono", 9, "bold"), cursor="hand2")
        self.capture_button.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(14, 0))

        keys_card = tk.Frame(root, bg="#08150d", padx=20, pady=18, highlightbackground="#1b5e32", highlightthickness=1)
        keys_card.pack(fill="both", expand=True)
        tk.Label(keys_card, text="> LAST TRANSMISSION", bg="#08150d", fg="#5fa874",
                 font=("DejaVu Sans Mono", 9)).pack(anchor="w")
        self.last_key = tk.Label(keys_card, text="_", bg="#08150d", fg="#9cffb8",
                                 font=("DejaVu Sans Mono", 28, "bold"))
        self.last_key.pack(anchor="w", pady=(4, 14))
        tk.Label(keys_card, text="> TRANSMISSION LOG", bg="#08150d", fg="#5fa874",
                 font=("DejaVu Sans Mono", 9)).pack(anchor="w")
        self.history_frame = tk.Frame(keys_card, bg="#08150d")
        self.history_frame.pack(fill="x", pady=(9, 0))

        tk.Label(root, text="F8  Передача вкл/выкл     F10  Выход     Pause/Break  Поддерживает удержание",
                 bg="#050a07", fg="#568765", font=("DejaVu Sans Mono", 9)).pack(anchor="w", pady=(14, 0))

        self._build_remote_panel()

    def _build_remote_panel(self) -> None:
        self.remote_panel = tk.Frame(self, bg="#06110b", padx=14, pady=10,
                                     highlightbackground="#39ff88", highlightthickness=1)
        top = tk.Frame(self.remote_panel, bg="#06110b")
        top.pack(fill="x", pady=(0, 7))
        tk.Label(top, text="[ REMOTE ]", bg="#06110b", fg="#39ff88",
                 font=("DejaVu Sans Mono", 15, "bold")).pack(side="left")
        tk.Button(top, text="×", command=self._toggle_remote, bg="#06110b", fg="#9cffb8",
                  activebackground="#1b5e32", activeforeground="#ffffff", relief="groove",
                  bd=1, font=("DejaVu Sans Mono", 18), cursor="hand2").pack(side="right")
        self.remote_buttons: list[tk.Button] = []

        grid = tk.Frame(self.remote_panel, bg="#06110b")
        grid.pack(fill="both", expand=True)
        self._remote_button(grid, "⏻", 0, 0, lambda: self._send_remote("Power", remote_button_command("power")), accent="#102b19")
        self._remote_button(grid, "⏏", 0, 2, lambda: self._send_remote("Eject", key_command("XF86Eject")))
        self._remote_button(grid, "🔊 +", 1, 0, lambda: self._send_remote("Volume +", remote_button_command("volume+")))
        self._remote_button(grid, "⌕ +", 1, 2, lambda: self._send_remote("Zoom +", remote_button_command("zoom+")))
        self._remote_button(grid, "🔉 −", 2, 0, lambda: self._send_remote("Volume −", remote_button_command("volume-")))
        self._remote_button(grid, "⌕ −", 2, 2, lambda: self._send_remote("Zoom −", remote_button_command("zoom-")))

        self._remote_button(grid, "▲", 3, 1, lambda: self._send_remote("Up", key_command("Up")), accent="#123d22")
        self._remote_button(grid, "◀", 4, 0, lambda: self._send_remote("Left", key_command("Left")))
        self._remote_button(grid, "OK", 4, 1, lambda: self._send_remote("Enter", key_command("Return")), accent="#1d6b38")
        self._remote_button(grid, "▶", 4, 2, lambda: self._send_remote("Right", key_command("Right")))
        self._remote_button(grid, "▼", 5, 1, lambda: self._send_remote("Down", key_command("Down")), accent="#123d22")

        actions = (
            ("⌂\nHOME", "Home", remote_button_command("home")),
            ("↶\nBACK", "Back", remote_button_command("back")),
            ("▣\nSAVE", "Save", remote_button_command("save")),
            ("▧\nSELFVIEW", "Selfview", remote_button_command("far")),
            ("▦\nMCU LAYOUT", "MCU Layout", remote_button_command("layout")),
            ("▦\nSCREEN", "Screen Layout", remote_button_command("layout")),
            ("▤\nPC", "PC", remote_button_command("pc")),
            ("★\nPROGRAM", "Program", key_command("F12")),
            ("▣\nVIDEO", "Video input", remote_button_command("pc")),
        )
        for index, (text, name, data) in enumerate(actions):
            self._remote_button(grid, text, 6 + index // 3, index % 3,
                                lambda n=name, d=data: self._send_remote(n, d), small=True)

        self._remote_button(grid, "☎", 9, 0, lambda: self._send_remote("Call", remote_button_command("call")), accent="#16833b")
        self._remote_button(grid, "←", 9, 1, lambda: self._send_remote("Back", remote_button_command("back")))
        self._remote_button(grid, "☎", 9, 2, lambda: self._send_remote("Hangup", hangup_command()), accent="#c42b1c")

        for index, key in enumerate(("1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#")):
            self._remote_button(grid, key, 10 + index // 3, index % 3,
                                lambda k=key: self._send_remote(k, key_command(k)), small=True)
        for column in range(3):
            grid.columnconfigure(column, weight=1, uniform="remote")

    def _remote_button(self, parent: tk.Widget, text: str, row: int, column: int,
                       command: object, accent: str = "#0d2415", small: bool = False) -> None:
        button = tk.Button(parent, text=text, command=command, state="disabled",
                           bg=accent, activebackground="#287346", fg="#9cffb8",
                           activeforeground="#ffffff", disabledforeground="#43694d",
                           relief="groove", bd=1, padx=4, pady=2 if small else 5,
                           font=("DejaVu Sans Mono", 7 if small else 12, "bold"), cursor="hand2")
        button.grid(row=row, column=column, sticky="nsew", padx=3, pady=2)
        self.remote_buttons.append(button)

    @staticmethod
    def _field(parent: tk.Widget, row: int, column: int, label: str, value: str, **kwargs: object) -> ttk.Entry:
        box = tk.Frame(parent, bg="#08150d")
        box.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 5, 5 if column < 3 else 0))
        tk.Label(box, text=label.upper(), bg="#08150d", fg="#5fa874", font=("DejaVu Sans Mono", 8)).pack(anchor="w", pady=(0, 4))
        entry = ttk.Entry(box, style="Fluent.TEntry", **kwargs)
        entry.insert(0, value)
        entry.pack(fill="x")
        return entry

    def _toggle_connection(self) -> None:
        if self.bridge.connected:
            self._disconnect()
            return
        try:
            port = int(self.port.get())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "SSH-порт должен быть числом от 1 до 65535")
            return
        host, user, password = self.host.get().strip(), self.user.get().strip(), self.password.get()
        if not host or not user or not password:
            messagebox.showerror("Ошибка", "Заполните IP, логин и пароль")
            return
        self.button.configure(state="disabled")
        self.status.set(f"Подключение к {host}…")
        self.status_dot.configure(fg="#fce100")
        threading.Thread(target=self._connect_worker, args=(host, port, user, password), daemon=True).start()

    def _toggle_capture(self) -> None:
        if not self.bridge.connected:
            return
        if not self.capture and self.remote_open:
            self._toggle_remote()
        self._set_capture(not self.capture)
        if self.capture:
            self.focus_set()

    def _set_capture(self, enabled: bool) -> None:
        self.capture = enabled and self.bridge.connected
        self.capture_text.set(
            "Захват клавиатуры включён — можно печатать"
            if self.capture else "Захват клавиатуры выключен"
        )
        self.capture_button.configure(
            text="Отключить захват" if self.capture else "Включить захват",
            bg="#1d6b38" if self.capture else "#102b19",
        )
        self.capture_lamp.configure(
            text="● CAPTURE ON" if self.capture else "● CAPTURE OFF",
            fg="#39ff88" if self.capture else "#ff3b3b",
        )
        if not self.capture:
            if self.pause_release_job is not None:
                self.after_cancel(self.pause_release_job)
                self.pause_release_job = None
            self.pause_started = None

    def _toggle_remote(self) -> None:
        if not self.remote_open:
            if self.capture:
                self._set_capture(False)
            self.update_idletasks()
            self.compact_position = (self.winfo_x(), self.winfo_y())
            x = max(0, min(self.winfo_x(), self.winfo_screenwidth() - 1100 - 12))
            y = max(0, min(self.winfo_y(), self.winfo_screenheight() - 740 - 32))
            self.geometry(f"1100x740+{x}+{y}")
            self.remote_panel.place(relx=1.0, y=0, anchor="ne", width=300, relheight=1.0)
            self.remote_toggle.configure(text="×  Закрыть пульт", bg="#1d6b38")
            self.remote_open = True
        else:
            self.remote_panel.place_forget()
            if self.compact_position is None:
                self.geometry("800x740")
            else:
                x, y = self.compact_position
                x = max(0, min(x, self.winfo_screenwidth() - 800 - 12))
                y = max(0, min(y, self.winfo_screenheight() - 740 - 32))
                self.geometry(f"800x740+{x}+{y}")
            self.remote_toggle.configure(text="☷  Пульт", bg="#0d2415")
            self.remote_open = False

    def _send_remote(self, label: str, data: bytes | None) -> None:
        if not self.bridge.connected or data is None:
            return
        self.bridge.send(data)
        self.sent_keys += 1
        self.sent_text.set(f"Отправлено команд: {self.sent_keys}")
        self._record_key(label)

    def _connect_worker(self, host: str, port: int, user: str, password: str) -> None:
        try:
            self.bridge.connect(host, port, user, password)
            self.events.put(("connected", host))
        except BridgeError as exc:
            self.events.put(("error", str(exc)))

    def _poll(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                self.button.configure(state="normal")
                if kind == "connected":
                    self.status.set(f"Подключено к {value}")
                    self.status_dot.configure(fg="#6ccb5f")
                    self.button.configure(text="Отключиться")
                    self._set_fields_state("disabled")
                    self.capture_button.configure(state="normal")
                    for remote_button in self.remote_buttons:
                        remote_button.configure(state="normal")
                    self._set_capture(not self.remote_open)
                    if self.capture:
                        self.focus_set()
                else:
                    self._disconnect()
                    messagebox.showerror("Ошибка соединения", value)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _key_down(self, event: tk.Event) -> str | None:
        if event.keysym == "F10":
            self._quit()
            return "break"
        if event.keysym == "F8":
            self._toggle_capture()
            return "break"
        if self.capture and event.keysym in {"Pause", "Break"}:
            if self.pause_release_job is not None:
                self.after_cancel(self.pause_release_job)
                self.pause_release_job = None
            if self.pause_started is None:
                self.pause_started = time.monotonic()
            return "break"
        if self.capture:
            data = key_command(event.keysym, event.state)
            if data:
                self.bridge.send(data)
                self.sent_keys += 1
                self.sent_text.set(f"Отправлено команд: {self.sent_keys}")
                self._record_key(event.keysym)
                return "break"
        return None

    def _key_up(self, event: tk.Event) -> str | None:
        if self.capture and event.keysym in {"Pause", "Break"}:
            # X11 generates release/press pairs during key auto-repeat. Waiting
            # briefly lets the following repeat press cancel this release.
            self.pause_release_job = self.after(100, self._send_pause_release, event.keysym, event.state)
            return "break"
        if self.capture:
            return "break"
        return None

    def _send_pause_release(self, keysym: str, state: int) -> None:
        self.pause_release_job = None
        if self.pause_started is None or not self.capture:
            self.pause_started = None
            return
        hold_ms = round((time.monotonic() - self.pause_started) * 1000)
        self.pause_started = None
        data = key_command(keysym, state, hold_ms=hold_ms)
        if data:
            self.bridge.send(data)
            self.sent_keys += 1
            self.sent_text.set(f"Отправлено команд: {self.sent_keys}")
            self._record_key(f"Pause  {hold_ms / 1000:.1f} с")

    def _record_key(self, name: str) -> None:
        """Show the latest key and keep a compact six-item visual history."""
        friendly = {
            "Return": "Enter", "BackSpace": "Backspace", "Escape": "Esc",
            "Prior": "Page Up", "Next": "Page Down", "space": "Space",
        }.get(name, name)
        self.last_key.configure(text=friendly, fg="#39ff88")
        self.after(160, lambda: self.last_key.configure(fg="#9cffb8"))
        chip = tk.Label(self.history_frame, text=f"[{friendly}]", bg="#102b19", fg="#9cffb8",
                        padx=12, pady=7, font=("DejaVu Sans Mono", 9, "bold"),
                        highlightbackground="#1b5e32", highlightthickness=1)
        chip.pack(side="left", padx=(0, 7))
        self.key_history.append(chip)
        if len(self.key_history) > 6:
            self.key_history.pop(0).destroy()

    def _set_fields_state(self, state: str) -> None:
        for field in (self.host, self.port, self.user, self.password):
            field.configure(state=state)

    def _disconnect(self) -> None:
        if self.pause_release_job is not None:
            self.after_cancel(self.pause_release_job)
            self.pause_release_job = None
        self.pause_started = None
        self._set_capture(False)
        self.sent_keys = 0
        self.bridge.close()
        self.status.set("Не подключено")
        self.status_dot.configure(fg="#777777")
        self.capture_text.set("Захват клавиатуры выключен")
        self.sent_text.set("Отправлено команд: 0")
        self.last_key.configure(text="_", fg="#9cffb8")
        for chip in self.key_history:
            chip.destroy()
        self.key_history.clear()
        self._set_fields_state("normal")
        self.capture_button.configure(state="disabled")
        for remote_button in self.remote_buttons:
            remote_button.configure(state="disabled")
        self.button.configure(text="Подключиться", state="normal")

    def _quit(self) -> None:
        self._disconnect()
        self.destroy()


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
