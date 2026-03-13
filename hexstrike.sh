#!/bin/bash
#
# Hexstrike wrapper for Linux – runs blk_hat_app.py with repl command.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment and run with local packages
source "$SCRIPT_DIR/hexstrike_env/Scripts/activate"
exec python blk_hat_app.py repl .
