#!/usr/bin/env python3
"""
ollama_hexstrike_cli.py

CLI bridge that sends user input to a local Ollama model and forwards the
model output to Hexstrike AI via its documented HTTP interface.
"""

from __future__ import annotations

import argparse
import atexit
import json
import logging
import os
import subprocess
import sys
import time
import socket
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

HEXSTRIKE_REPO_URL = "https://github.com/0x4m4/hexstrike-ai.git"
DEFAULT_HEXSTRIKE_ENDPOINT = "/api/intelligence/analyze-target"


class CliError(Exception):
    """Raised for expected CLI/user-facing errors."""


_STARTED_SERVER_PROC: Optional[subprocess.Popen] = None


def get_default_config_path() -> Path:
    """Return a sensible per-user config path, optimized for Windows."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "hexstrike-ollama-cli" / "config.json"
        return Path.home() / "AppData" / "Roaming" / "hexstrike-ollama-cli" / "config.json"

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "hexstrike-ollama-cli" / "config.json"
    return Path.home() / ".config" / "hexstrike-ollama-cli" / "config.json"


def default_config() -> Dict[str, Any]:
    """Base config values used when no file exists."""
    return {
        "ollama_mode": "api",  # api or cli
        "ollama_url": "http://localhost:11434/api/generate",
        "ollama_model": "llama3.2",
        "hexstrike_url": "http://localhost:8888",
        "hexstrike_endpoint": DEFAULT_HEXSTRIKE_ENDPOINT,
        "hexstrike_objective": "comprehensive",
        "hexstrike_repo_path": "./hexstrike",
    }


def load_config(config_path: Path, verbose: bool = False) -> Dict[str, Any]:
    """Load config from disk; return defaults if file does not exist."""
    cfg = default_config()
    if not config_path.exists():
        return cfg

    try:
        with config_path.open("r", encoding="utf-8") as fh:
            file_cfg = json.load(fh)
        if isinstance(file_cfg, dict):
            cfg.update(file_cfg)
    except Exception as exc:
        if verbose:
            logging.warning("Failed to load config from %s: %s", config_path, exc)
    return cfg


def save_config(config_path: Path, config: Dict[str, Any]) -> None:
    """Persist config safely."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)


def ensure_hexstrike_repo(repo_path: Path, clone_if_missing: bool, verbose: bool = False) -> None:
    """Reference or clone the Hexstrike repo so integration is explicit and traceable."""
    if repo_path.exists():
        marker = repo_path / "hexstrike_server.py"
        if marker.exists():
            if verbose:
                logging.info("Using existing Hexstrike repo at %s", repo_path)
            return
        raise CliError(
            f"Hexstrike repo path exists but does not look valid: {repo_path}. "
            "Expected file: hexstrike_server.py"
        )

    if not clone_if_missing:
        raise CliError(
            f"Hexstrike repo not found at {repo_path}. "
            "Clone it manually or pass --clone-hexstrike."
        )

    try:
        subprocess.run(
            ["git", "clone", HEXSTRIKE_REPO_URL, str(repo_path)],
            check=True,
            capture_output=not verbose,
            text=True,
        )
    except FileNotFoundError as exc:
        raise CliError("Git is not available on PATH. Install Git and retry.") from exc
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else str(exc)
        raise CliError(f"Failed to clone Hexstrike repo: {msg}") from exc


def install_hexstrike_requirements(repo_path: Path, python_executable: str, verbose: bool = False) -> None:
    """Install Hexstrike requirements into the active Python environment."""
    requirements = repo_path / "requirements.txt"
    if not requirements.exists():
        raise CliError(f"Hexstrike requirements file not found: {requirements}")

    cmd = [python_executable, "-m", "pip", "install", "-r", str(requirements)]
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=not verbose,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else str(exc)
        raise CliError(f"Failed to install Hexstrike requirements: {msg}") from exc


def wait_for_hexstrike_server(base_url: str, timeout_seconds: int = 90) -> bool:
    """Poll Hexstrike health endpoint until it is available."""
    health_url = base_url.rstrip("/") + "/health"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(health_url, timeout=3)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(1.5)
    return False


def wait_for_hexstrike_port(base_url: str, timeout_seconds: int = 90) -> bool:
    """Wait until the TCP port is accepting connections."""
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(1.0)
    return False


def start_hexstrike_server(
    repo_path: Path,
    base_url: str,
    python_executable: str,
    start_timeout_seconds: int,
    keep_server_running: bool,
    verbose: bool = False,
) -> Tuple[bool, Optional[subprocess.Popen]]:
    """Ensure Hexstrike server is running; start it if needed."""
    global _STARTED_SERVER_PROC
    if wait_for_hexstrike_port(base_url, timeout_seconds=2):
        return False, None

    server_script = repo_path / "hexstrike_server.py"
    if not server_script.exists():
        raise CliError(f"Hexstrike server script not found: {server_script}")

    stdout_pipe = None if verbose else subprocess.DEVNULL
    stderr_pipe = None if verbose else subprocess.DEVNULL
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0

    server_env = os.environ.copy()
    server_env.setdefault("PYTHONUTF8", "1")
    server_env.setdefault("PYTHONIOENCODING", "utf-8")

    try:
        proc = subprocess.Popen(
            [python_executable, "-X", "utf8", str(server_script)],
            cwd=str(repo_path),
            stdout=stdout_pipe,
            stderr=stderr_pipe,
            env=server_env,
            creationflags=creationflags,
        )
    except Exception as exc:
        raise CliError(f"Failed to start Hexstrike server: {exc}") from exc

    if not wait_for_hexstrike_port(base_url, timeout_seconds=start_timeout_seconds):
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            pass
        raise CliError(
            "Hexstrike server did not become healthy in time. "
            "Run manually with `python hexstrike/hexstrike_server.py` to inspect logs."
        )

    _STARTED_SERVER_PROC = proc
    if not keep_server_running:
        atexit.register(_terminate_started_server)
    return True, proc


def _terminate_started_server() -> None:
    """Best-effort shutdown for server process started by this CLI."""
    global _STARTED_SERVER_PROC
    proc = _STARTED_SERVER_PROC
    if not proc:
        return
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    _STARTED_SERVER_PROC = None


def load_input_text(prompt_arg: Optional[str], file_arg: Optional[str]) -> str:
    """Read input from --prompt, --file, or interactive stdin."""
    if prompt_arg:
        return prompt_arg.strip()

    if file_arg:
        path = Path(file_arg)
        if not path.exists():
            raise CliError(f"Input file does not exist: {path}")
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception as exc:
            raise CliError(f"Failed to read input file {path}: {exc}") from exc

    # Interactive fallback for CLI usage.
    try:
        return input("Enter prompt> ").strip()
    except EOFError as exc:
        raise CliError("No input provided. Use --prompt or --file.") from exc


def send_to_ollama(
    prompt: str,
    model: str,
    mode: str,
    ollama_url: str,
    timeout: int = 120,
) -> str:
    """Send text to Ollama via HTTP API or local CLI and return model output."""
    if mode == "api":
        payload = {"model": model, "prompt": prompt, "stream": False}
        try:
            response = requests.post(ollama_url, json=payload, timeout=timeout)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise CliError(
                "Cannot connect to Ollama API. Ensure Ollama is running locally "
                "(e.g., `ollama serve`) and endpoint is correct."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise CliError(f"Ollama API request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise CliError("Ollama returned non-JSON output.") from exc

        if not isinstance(data, dict) or "response" not in data:
            raise CliError("Invalid Ollama response: expected JSON with 'response'.")

        model_output = str(data["response"]).strip()
        if not model_output:
            raise CliError("Ollama returned an empty response.")
        return model_output

    if mode == "cli":
        try:
            completed = subprocess.run(
                ["ollama", "run", model, prompt],
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise CliError("`ollama` CLI not found on PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise CliError("Ollama CLI request timed out.") from exc
        except subprocess.CalledProcessError as exc:
            msg = exc.stderr.strip() if exc.stderr else "Unknown Ollama CLI error"
            raise CliError(f"Ollama CLI failed: {msg}") from exc

        output = completed.stdout.strip()
        if not output:
            raise CliError("Ollama CLI returned empty output.")
        return output

    raise CliError(f"Unsupported Ollama mode: {mode}. Use 'api' or 'cli'.")


def build_hexstrike_payload(endpoint: str, ollama_output: str, objective: str) -> Dict[str, Any]:
    """Construct payload based on common documented Hexstrike endpoint contracts."""
    endpoint = endpoint.strip()

    if endpoint == "/api/command":
        return {"command": ollama_output, "use_cache": True}

    payload: Dict[str, Any] = {"target": ollama_output}

    if endpoint in {
        "/api/intelligence/select-tools",
        "/api/intelligence/create-attack-chain",
        "/api/intelligence/smart-scan",
    }:
        payload["objective"] = objective

    return payload


def send_to_hexstrike(
    ollama_output: str,
    base_url: str,
    endpoint: str,
    objective: str,
    timeout: int = 180,
) -> Dict[str, Any]:
    """Forward Ollama output to Hexstrike and return parsed JSON response."""
    # Best-effort health probe. Some builds run expensive checks in /health.
    health_url = base_url.rstrip("/") + "/health"
    try:
        requests.get(health_url, timeout=5)
    except requests.exceptions.ConnectionError as exc:
        raise CliError(
            "Cannot reach Hexstrike server. Start it first (e.g., `python hexstrike_server.py`)."
        ) from exc
    except requests.exceptions.RequestException:
        logging.warning("Hexstrike /health check timed out; continuing with endpoint request.")

    url = base_url.rstrip("/") + endpoint
    payload = build_hexstrike_payload(endpoint, ollama_output, objective)

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise CliError("Network/connectivity error while sending data to Hexstrike.") from exc
    except requests.exceptions.RequestException as exc:
        raise CliError(f"Hexstrike request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise CliError("Hexstrike returned invalid (non-JSON) response.") from exc

    if not isinstance(data, dict):
        raise CliError("Invalid Hexstrike response: expected a JSON object.")
    return data


def print_section(title: str, body: str) -> None:
    """Pretty terminal section printer."""
    line = "=" * 78
    print(f"\n{line}\n{title}\n{line}")
    print(body)


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Bridge local Ollama outputs into Hexstrike AI endpoints.",
    )

    parser.add_argument("--prompt", help="Direct input prompt text.")
    parser.add_argument("--file", help="Path to a text file containing prompt input.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    parser.add_argument(
        "--auto-start-hexstrike",
        action="store_true",
        help="Start Hexstrike server automatically if not already running.",
    )
    parser.add_argument(
        "--install-hexstrike-deps",
        action="store_true",
        help="Install Hexstrike requirements before starting the server.",
    )
    parser.add_argument(
        "--keep-server-running",
        action="store_true",
        help="Keep auto-started Hexstrike server running after this command exits.",
    )
    parser.add_argument(
        "--server-start-timeout",
        type=int,
        default=120,
        help="Seconds to wait for Hexstrike server to become healthy when auto-starting.",
    )
    parser.add_argument(
        "--python-exe",
        default=sys.executable,
        help="Python executable used to start Hexstrike server and install deps.",
    )

    # Config behavior
    parser.add_argument(
        "--config",
        action="store_true",
        help="Save provided endpoint/model settings to local config file.",
    )
    parser.add_argument(
        "--config-path",
        help="Optional custom config file path (default: user config directory).",
    )

    # Endpoint/model overrides
    parser.add_argument("--ollama-mode", choices=["api", "cli"], help="Ollama transport mode.")
    parser.add_argument("--ollama-url", help="Ollama API endpoint URL.")
    parser.add_argument("--model", help="Ollama model name.")
    parser.add_argument("--hexstrike-url", help="Hexstrike base URL (e.g., http://localhost:8888).")
    parser.add_argument("--hexstrike-endpoint", help="Hexstrike endpoint path.")
    parser.add_argument("--hexstrike-objective", help="Objective for intelligence endpoints.")

    # Repo integration
    parser.add_argument(
        "--hexstrike-repo",
        help="Local path to Hexstrike repo clone/reference.",
    )
    parser.add_argument(
        "--clone-hexstrike",
        action="store_true",
        help="Clone Hexstrike repo automatically if missing.",
    )

    return parser


def merge_args_into_config(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply CLI overrides to runtime config."""
    mapping = {
        "ollama_mode": args.ollama_mode,
        "ollama_url": args.ollama_url,
        "ollama_model": args.model,
        "hexstrike_url": args.hexstrike_url,
        "hexstrike_endpoint": args.hexstrike_endpoint,
        "hexstrike_objective": args.hexstrike_objective,
        "hexstrike_repo_path": args.hexstrike_repo,
    }

    for key, value in mapping.items():
        if value:
            config[key] = value
    return config


def main() -> int:
    """Program entrypoint."""
    parser = build_arg_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    config_path = Path(args.config_path).expanduser().resolve() if args.config_path else get_default_config_path()
    config = load_config(config_path, verbose=args.verbose)
    config = merge_args_into_config(args, config)

    if args.config:
        save_config(config_path, config)
        print(f"Saved config to: {config_path}")
        if not args.prompt and not args.file:
            return 0

    try:
        repo_path = Path(config["hexstrike_repo_path"]).expanduser().resolve()
        ensure_hexstrike_repo(repo_path, clone_if_missing=args.clone_hexstrike, verbose=args.verbose)

        if args.install_hexstrike_deps:
            install_hexstrike_requirements(
                repo_path=repo_path,
                python_executable=args.python_exe,
                verbose=args.verbose,
            )

        if args.auto_start_hexstrike:
            started, _proc = start_hexstrike_server(
                repo_path=repo_path,
                base_url=config["hexstrike_url"],
                python_executable=args.python_exe,
                start_timeout_seconds=args.server_start_timeout,
                keep_server_running=args.keep_server_running,
                verbose=args.verbose,
            )
            if args.verbose and started:
                logging.debug("Hexstrike server was started by this CLI command.")

        prompt_text = load_input_text(args.prompt, args.file)
        if not prompt_text:
            raise CliError("Input cannot be empty.")

        if args.verbose:
            logging.debug("Prompt length: %d characters", len(prompt_text))
            logging.debug("Using Ollama mode: %s", config["ollama_mode"])

        ollama_output = send_to_ollama(
            prompt=prompt_text,
            model=config["ollama_model"],
            mode=config["ollama_mode"],
            ollama_url=config["ollama_url"],
        )

        hexstrike_response = send_to_hexstrike(
            ollama_output=ollama_output,
            base_url=config["hexstrike_url"],
            endpoint=config["hexstrike_endpoint"],
            objective=config.get("hexstrike_objective", "comprehensive"),
        )

        print_section("OLLAMA OUTPUT", ollama_output)
        pretty_hex = json.dumps(hexstrike_response, indent=2, ensure_ascii=False)
        print_section("HEXSTRIKE RESPONSE", pretty_hex)

        if args.auto_start_hexstrike and not args.keep_server_running:
            _terminate_started_server()

        return 0

    except CliError as exc:
        logging.error(str(exc))
        return 2
    except KeyboardInterrupt:
        logging.error("Interrupted by user.")
        return 130
    except Exception as exc:
        logging.exception("Unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
