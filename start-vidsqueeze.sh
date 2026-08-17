#!/bin/bash
# VidSqueeze launcher for Linux.
#
# Double-click it in your file manager (choose "Run" or "Run in Terminal"),
# or run ./start-vidsqueeze.sh from a terminal.

cd "$(dirname "$0")" || exit 1

echo
echo "  VidSqueeze"
echo "  ----------"
echo

PYTHON=""
for candidate in python3 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
            PYTHON=$(command -v "$candidate")
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  VidSqueeze needs Python 3.9 or newer."
    echo
    if command -v apt >/dev/null 2>&1; then
        echo "    sudo apt install python3"
    elif command -v dnf >/dev/null 2>&1; then
        echo "    sudo dnf install python3"
    elif command -v pacman >/dev/null 2>&1; then
        echo "    sudo pacman -S python"
    else
        echo "    Install Python 3 using your distribution's package manager."
    fi
    echo
    read -r -p "  Press Enter to close. " _
    exit 1
fi

"$PYTHON" -m vidsqueeze "$@"
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
    echo
    echo "  VidSqueeze stopped unexpectedly (code $STATUS)."
    echo "  The logs folder may explain why."
    echo
    read -r -p "  Press Enter to close. " _
fi

exit $STATUS
