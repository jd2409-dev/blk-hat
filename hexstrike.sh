#!/bin/bash
#
# Hexstrike wrapper for Linux – mirrors hexstrike.cmd by forwarding to blk-hat.
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

exec ./blk-hat "$@"
