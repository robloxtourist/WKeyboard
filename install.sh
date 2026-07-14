#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP_DIR=${XDG_DATA_HOME:-"$HOME/.local/share"}/wkeyboard
BIN_DIR=${XDG_BIN_HOME:-"$HOME/.local/bin"}

if [ "$(id -u)" -eq 0 ]; then
    echo "Не запускайте установщик через sudo. Запустите: ./install.sh" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import tkinter, paramiko' >/dev/null 2>&1; then
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "Установите Tkinter и Paramiko для системного Python 3." >&2
        exit 1
    fi
    echo "Устанавливаются системные зависимости из репозитория Debian…"
    sudo apt-get update
    sudo apt-get install -y python3 python3-tk python3-paramiko
fi

python3 -c 'import tkinter, paramiko' >/dev/null
mkdir -p "$APP_DIR" "$BIN_DIR"
rm -rf "$APP_DIR/terminal_key_bridge"
cp -R "$SCRIPT_DIR/terminal_key_bridge" "$APP_DIR/terminal_key_bridge"
install -m 0755 "$SCRIPT_DIR/terminal-key-bridge" "$APP_DIR/terminal-key-bridge"
install -m 0755 "$SCRIPT_DIR/wkeyboard" "$BIN_DIR/wkeyboard"

echo
echo "WKeyboard установлен. Запуск:"
echo "  $BIN_DIR/wkeyboard"
case ":$PATH:" in
    *":$BIN_DIR:"*) echo "  или: wkeyboard" ;;
    *) echo "Добавьте $BIN_DIR в PATH, чтобы запускать командой wkeyboard." ;;
esac
