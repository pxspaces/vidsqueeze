#!/bin/bash
# HalveIt launcher for macOS. Double-click this file.
#
# If macOS refuses to open it, right-click the file and choose Open, then
# confirm. That only has to be done once.

cd "$(dirname "$0")" || exit 1

echo
echo "  HalveIt"
echo "  -------"
echo

find_python() {
    for candidate in \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        "$(command -v python3 2>/dev/null)" \
        /usr/bin/python3
    do
        [ -n "$candidate" ] || continue
        [ -x "$candidate" ] || continue
        # The stub at /usr/bin/python3 exits non-zero until the developer
        # tools are installed, so actually run something to be sure.
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

PYTHON=$(find_python)

if [ -z "$PYTHON" ]; then
    echo "  HalveIt needs Python 3.9 or newer, which this Mac does not have yet."
    echo
    echo "  The easiest way to get it:"
    echo
    echo "    1. Open the App Store and install Xcode Command Line Tools, or"
    echo "       run this in Terminal:   xcode-select --install"
    echo
    echo "    2. Or download Python from https://www.python.org/downloads/"
    echo
    read -r -p "  Try running 'xcode-select --install' now? (y/N) " answer
    case "$answer" in
        [Yy]*)
            xcode-select --install
            echo
            echo "  Follow the installer, then double-click HalveIt again."
            ;;
        *)
            echo "  No changes made."
            ;;
    esac
    echo
    read -r -p "  Press Enter to close. " _
    exit 1
fi

"$PYTHON" -m halveit "$@"
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
    echo
    echo "  HalveIt stopped unexpectedly (code $STATUS)."
    echo "  The logs folder may explain why."
    echo
    read -r -p "  Press Enter to close. " _
fi

exit $STATUS
