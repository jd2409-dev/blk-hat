# BLK-HAT + Hexstrike (Windows)

`README_SNIPPET.md` is a copy-ready quickstart for this repo.

## Prerequisites

- Python 3.9+
- Git
- Ollama installed (`ollama --version`)
- Local Hexstrike checkout in `./hexstrike`

## Setup

```powershell
cd C:\Users\Jaydan\hexstrike
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install requests
```

If Hexstrike is missing:

```powershell
git clone https://github.com/0x4m4/hexstrike-ai.git hexstrike
```

## Configure once

```powershell
python .\ollama_hexstrike_cli.py --config `
  --ollama-mode api `
  --ollama-url http://localhost:11434/api/generate `
  --model llama3.2 `
  --hexstrike-url http://localhost:8888 `
  --hexstrike-endpoint /api/intelligence/analyze-target `
  --hexstrike-repo .\hexstrike
```

## Run options

```powershell
# GUI wrapper
.\blk-hat.cmd

# Simple launcher
.\hexstrike.cmd

# One-shot prompt
python .\ollama_hexstrike_cli.py --prompt "Analyze scan approach for example.com"

# Prompt from file
python .\ollama_hexstrike_cli.py --file .\input.txt
```

## Notes

- Default Hexstrike endpoint is `/api/intelligence/analyze-target`.
- Use `--verbose` for troubleshooting.
- `run_hexstrike.bat` is still available for batch-driven startup.
- Last updated: 2026-03-07.
