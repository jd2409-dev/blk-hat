# BLK-HAT CLI (GPT4All + Hexstrike)

`blk_hat_app.py` is a local CLI bridge:
- Runs a local GPT4All model
- Sends generated command output to a Hexstrike server (`/api/command` by default)

## What Was Fixed for TailsOS/Linux

- Added Linux-safe command fallbacks (`ss`, `ps`) instead of Windows-only fallbacks.
- Added platform-aware safe command allowlists for execution approval prompts.
- Added robust GPT4All import/init error handling (clean CLI errors instead of tracebacks).
- Kept Windows behavior unchanged.

## TailsOS Setup

Tails is Debian-based and usually ephemeral unless Persistent Storage is enabled.

1. Install system packages:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl
```

2. Create and activate a virtualenv:

```bash
cd ~/hexstrike
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

3. Install Python dependencies for BLK-HAT CLI:

```bash
pip install gpt4all typer requests
```

4. Install Hexstrike dependencies:

```bash
pip install -r hexstrike/requirements.txt
```

## Start Hexstrike Server

```bash
python3 hexstrike/hexstrike_server.py
```

Health check:

```bash
curl http://127.0.0.1:8888/health
```

## Run the GPT4All + Hexstrike CLI

```bash
python3 blk_hat_app.py repl \
  --model mistral-7b-instruct-v0.1.Q4_0.gguf \
  --hexstrike-url http://127.0.0.1:8888 \
  --hexstrike-endpoint /api/command \
  --hexstrike-repo ./hexstrike
```

Notes:
- If your model filename differs, pass it with `--model`.
- On first run, GPT4All may download models to user cache.
- Use `--no-auto-start-hexstrike` if you manage server startup manually.

## Quick Commands

- Show version:

```bash
python3 blk_hat_app.py version
```

- Help:

```bash
python3 blk_hat_app.py repl --help
```

## Troubleshooting (TailsOS)

- `GPT4All is not available`:
  - Install deps in active venv: `pip install gpt4all typer requests`
- `Failed to initialize GPT4All model`:
  - Verify model name/path passed to `--model`
- `Cannot reach Hexstrike server`:
  - Confirm server is running on `127.0.0.1:8888`
  - Check `curl http://127.0.0.1:8888/health`
- Tails reset after reboot:
  - Enable Persistent Storage, or repeat setup each session
