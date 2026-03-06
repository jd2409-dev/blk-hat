# Ollama + Hexstrike CLI (Windows)

This tool bridges a local Ollama model to Hexstrike AI:
1. Reads your prompt (`--prompt`, `--file`, or interactive input)
2. Sends it to Ollama (`api` or `cli` mode)
3. Forwards Ollama output to Hexstrike's documented API endpoint
4. Prints both outputs in the terminal

## 1) Prerequisites

- Python 3.9+
- Git
- Ollama installed (`ollama --version`)
- Hexstrike repo cloned locally (or use `--clone-hexstrike`)

## 2) Install dependencies

```powershell
cd C:\Users\Jaydan\hexstrike
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install requests
```

For CMD:

```cmd
cd C:\Users\Jaydan\hexstrike
python -m venv .venv
.venv\Scripts\activate.bat
pip install requests
```

## 3) Clone Hexstrike repo

```powershell
git clone https://github.com/0x4m4/hexstrike-ai.git hexstrike
```

Then start Hexstrike server from that repo:

```powershell
cd .\hexstrike
python hexstrike_server.py
```

## 4) Make sure Ollama is running locally

In a separate terminal, verify/start Ollama:

```powershell
ollama list
# If needed, start background service:
ollama serve
```

Optional model pull:

```powershell
ollama pull llama3.2
```

## 5) Save local endpoint config

```powershell
python .\ollama_hexstrike_cli.py --config ^
  --ollama-mode api ^
  --ollama-url http://localhost:11434/api/generate ^
  --model llama3.2 ^
  --hexstrike-url http://localhost:8888 ^
  --hexstrike-endpoint /api/intelligence/analyze-target ^
  --hexstrike-repo .\hexstrike
```

PowerShell multiline alternative:

```powershell
python .\ollama_hexstrike_cli.py --config `
  --ollama-mode api `
  --ollama-url http://localhost:11434/api/generate `
  --model llama3.2 `
  --hexstrike-url http://localhost:8888 `
  --hexstrike-endpoint /api/intelligence/analyze-target `
  --hexstrike-repo .\hexstrike
```

## 6) Run the CLI

Single-command mode (auto-installs Hexstrike deps and auto-starts server):

```powershell
.\run_hexstrike.bat --prompt "Analyze scan approach for example.com"
```

Direct prompt:

```powershell
python .\ollama_hexstrike_cli.py --prompt "Analyze scan approach for example.com"
```

From file:

```powershell
python .\ollama_hexstrike_cli.py --file .\input.txt
```

Verbose debugging:

```powershell
python .\ollama_hexstrike_cli.py --prompt "test" --verbose
```

Auto-start server from CLI without the batch launcher:

```powershell
python .\ollama_hexstrike_cli.py --auto-start-hexstrike --install-hexstrike-deps --prompt "test"
```

## Notes

- Default Hexstrike integration endpoint is `/api/intelligence/analyze-target`.
- You can override endpoint per run with `--hexstrike-endpoint`.
- `--clone-hexstrike` can auto-clone the repo if your configured path does not exist.
