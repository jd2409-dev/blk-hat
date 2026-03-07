# BLK-HAT + Hexstrike Quickstart (Windows)

This snippet is the working path for this repo as of 2026-03-07.

## 1) Prerequisites

- Python 3.9+
- Git
- Ollama installed (`ollama --version`)

## 2) One-time setup

```powershell
cd C:\Users\Jaydan\hexstrike
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install requests
```

## 3) Start Ollama and pull a model

```powershell
ollama serve
```

In a second terminal:

```powershell
ollama pull llama3.2
```

## 4) Save config (works even if `.\hexstrike` is missing initially)

```powershell
python .\ollama_hexstrike_cli.py --config `
  --ollama-mode api `
  --ollama-url http://localhost:11434/api/generate `
  --model llama3.2 `
  --hexstrike-url http://localhost:8888 `
  --hexstrike-endpoint /api/intelligence/analyze-target `
  --hexstrike-repo .\hexstrike
```

## 5) Run (recommended)

This command auto-clones Hexstrike if missing, installs Hexstrike deps, and auto-starts Hexstrike:

```powershell
python .\ollama_hexstrike_cli.py `
  --clone-hexstrike `
  --auto-start-hexstrike `
  --install-hexstrike-deps `
  --prompt "Analyze scan approach for example.com"
```

## 6) Equivalent launcher

```powershell
.\run_hexstrike.bat --clone-hexstrike --prompt "Analyze scan approach for example.com"
```

## Optional: BLK-HAT wrapper

`.\blk-hat.cmd` / `.\hexstrike.cmd` runs `blk_hat_app.py repl`. It also requires:
- Python packages: `typer`, `requests`, and `gpt4all`
- A local GPT4All model file matching the default name in `blk_hat_app.py`

## Troubleshooting

- Add `--verbose` to `ollama_hexstrike_cli.py` for detailed logs.
- If Ollama is unreachable, verify `http://localhost:11434`.
- If Hexstrike startup fails, run it manually from `.\hexstrike`:

```powershell
python .\hexstrike\hexstrike_server.py
```
