# BLK-HAT + Hexstrike Quickstart (Windows)

This snippet is the working path for this repo as of 2026-03-07.

## 1) Prerequisites

- Python 3.9+
- Git
- GPT4All Python package and a local model file

## 2) One-time setup

```powershell
cd C:\Users\Jaydan\hexstrike
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install gpt4all typer requests
python -m pip install -r .\hexstrike\requirements.txt
```

## 3) Start Hexstrike server

```powershell
python .\hexstrike\hexstrike_server.py
```

## 4) Run BLK-HAT CLI

```powershell
python .\blk_hat_app.py repl `
  --model mistral-7b-instruct-v0.1.Q4_0.gguf `
  --hexstrike-url http://127.0.0.1:8888 `
  --hexstrike-endpoint /api/command `
  --hexstrike-repo .\hexstrike
```

## 5) Launchers

`.\blk-hat.cmd` and `.\hexstrike.cmd` run `blk_hat_app.py repl`.

They require:
- Python packages: `typer`, `requests`, and `gpt4all`
- A local GPT4All model file matching the default name in `blk_hat_app.py`

## Troubleshooting

- Add `--help` to inspect available CLI options:

```powershell
python .\blk_hat_app.py repl --help
```

- If Hexstrike startup fails, run it manually from `.\hexstrike`:

```powershell
python .\hexstrike\hexstrike_server.py
```
