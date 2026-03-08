#!/usr/bin/env python3
"""BLK-HAT CLI.

Terminal chat interface for local model + Hexstrike orchestration.
"""

import importlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
from collections import namedtuple
try:
    from typing import Annotated
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    from typing_extensions import Annotated

import typer
import requests

_gpt4all_import_error = None
try:
    BLKHATModel = getattr(importlib.import_module("gpt" + "4all"), "GPT" + "4All")
except Exception as exc:  # pragma: no cover - import-time guard for runtime envs
    BLKHATModel = None
    _gpt4all_import_error = exc


MESSAGES = [
    {
        "role": "system",
        "content": (
            "You are a cybersecurity command planner integrated with the Hexstrike server. "
            "Return only the exact command to execute for the user's request, with no "
            "explanations, no markdown, and no extra text."
        ),
    },
    {"role": "user", "content": "Hello there."},
    {"role": "assistant", "content": "Hi, how can I help you?"},
]

SPECIAL_COMMANDS = {
    "/reset": lambda messages: messages.clear(),
    "/exit": lambda _: sys.exit(),
    "/clear": lambda _: print("\n" * 100),
    "/help": lambda _: print("Special commands: /reset, /exit, /help and /clear"),
}

DEFAULT_HEXSTRIKE_URL = "http://localhost:8888"
DEFAULT_HEXSTRIKE_ENDPOINT = "/api/command"
DEFAULT_HEXSTRIKE_REPO = str((Path(__file__).resolve().parent / "hexstrike"))
DEFAULT_HEXSTRIKE_INPUT = "assistant"
DEFAULT_CONFIRM_PENTEST_TOOLS = True
STRICT_APPROVAL_FOR_NONSAFE_COMMANDS = True

SAFE_COMMAND_HEADS = {
    "netstat", "tasklist", "ipconfig", "systeminfo", "whoami",
    "hostname", "ping", "tracert", "route", "arp", "nslookup",
}
SAFE_COMMAND_HEADS_POSIX = {
    "ss", "netstat", "lsof", "ps", "whoami", "hostname",
    "ping", "ip", "route", "arp", "nslookup", "cat",
    "grep", "awk", "sed", "ls", "find",
}

PENTEST_TOOL_HEADS = {
    # Recon and network
    "nmap", "masscan", "rustscan", "amass", "subfinder", "fierce", "dnsenum", "autorecon",
    "theharvester", "arp-scan", "nbtscan", "rpcclient", "enum4linux", "enum4linux-ng",
    "smbmap", "responder", "netexec", "crackmapexec",
    # Web and API security
    "dirbuster", "gobuster", "feroxbuster", "dirsearch", "ffuf", "dirb", "httpx", "katana", "hakrawler",
    "gau", "waybackurls", "nuclei", "nikto", "sqlmap", "wpscan", "arjun", "paramspider",
    "x8", "jaeles", "dalfox", "wafw00f", "testssl", "testssl.sh", "sslscan", "sslyze",
    "anew", "qsreplace", "uro", "whatweb", "jwt-tool", "graphql-voyager", "zap", "zaproxy",
    "owasp-zap", "burp", "burpsuite", "burpsuite_pro", "wfuzz", "commix", "nosqlmap", "tplmap",
    "xsstrike", "ssrfmap",
    # Vulnerability scanners
    "nessus", "openvas", "gvm", "gvm-cli",
    # Password/auth
    "hydra", "john", "john-the-ripper", "hashcat", "medusa", "patator", "evil-winrm",
    "hash-identifier", "hashid", "ophcrack",
    # Exploitation frameworks
    "msfconsole", "msfvenom", "metasploit", "searchsploit", "empire", "covenant",
    # Reversing and binary
    "gdb", "gdb-peda", "gdb-gef", "radare2", "r2", "ghidra", "ida", "ida64", "binaryninja",
    "binwalk", "ropgadget", "ropper", "one_gadget", "one-gadget", "checksec", "objdump",
    "readelf", "xxd", "hexdump", "pwntools", "angr", "pwninit", "upx", "strings",
    # Forensics and stego
    "volatility", "volatility3", "foremost", "photorec", "testdisk", "steghide", "stegsolve",
    "zsteg", "outguess", "exiftool", "scalpel", "bulk_extractor", "autopsy", "sleuthkit",
    "tsk_recover", "fls", "icat",
    # Cloud/container/k8s
    "prowler", "scout-suite", "cloudmapper", "pacu", "trivy", "clair", "kube-hunter",
    "kube-bench", "docker-bench-security", "falco", "checkov", "terrascan", "cloudsploit",
    "kubectl", "helm", "istioctl", "opa",
    # OSINT and bug bounty
    "aquatone", "subjack", "sherlock", "social-analyzer", "recon-ng", "maltego",
    "spiderfoot", "shodan", "censys", "trufflehog",
    # Wireless and post-exploitation
    "aircrack-ng", "airmon-ng", "airodump-ng", "aireplay-ng", "mimikatz",
    "impacket", "psexec.py", "wmiexec.py", "smbexec.py", "secretsdump.py", "ntlmrelayx.py",
    # Tunneling, proxy, phishing frameworks
    "proxychains", "proxychains4", "chisel", "evilginx2",
    # AD / C2 / post-exploitation frameworks
    "bloodhound", "bloodhound-python", "sharpound", "sharphound", "rubeus",
    "powersploit", "powerview", "seatbelt", "pupy", "sliver", "sliver-server",
    "cobalt", "cobaltstrike", "cobalt-strike", "mythic", "donut", "avalon",
    # Additional recon/web tools
    "rustscan", "naabu", "httpx", "katana", "feroxbuster", "arjun", "tplmap",
    "nosqlmap", "joomscan", "wpscan", "droopescan", "cmseek",
    # Network / IoT / mitm
    "routersploit", "bettercap",
    # DFIR / reverse / mobile
    "hashdeep", "foremost", "volatility", "rekall", "autopsy", "sleuthkit",
    "sleuth", "tsk", "binwalk", "radare2", "ghidra", "cutter", "frida",
    "objection", "qark", "mobsf", "androbugs",
    # Common packet/capture tools
    "wireshark", "tshark", "tcpdump",
}

VersionInfo = namedtuple('VersionInfo', ['major', 'minor', 'micro'])
VERSION_INFO = VersionInfo(1, 0, 2)
VERSION = '.'.join(map(str, VERSION_INFO))  # convert to string form, like: '1.2.3'

CLI_START_MESSAGE = f"""

██████  ██      ██   ██       ██   ██  █████  ████████
██   ██ ██      ██  ██        ██   ██ ██   ██    ██
██████  ██      █████   █████ ███████ ███████    ██
██   ██ ██      ██  ██        ██   ██ ██   ██    ██
██████  ███████ ██   ██       ██   ██ ██   ██    ██

Welcome to BLK-HAT CLI! Version {VERSION}
Type /help for special commands.

"""

# create typer app
app = typer.Typer()

@app.command()
def repl(
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Model to use for chatbot"),
    ] = "mistral-7b-instruct-v0.1.Q4_0.gguf",
    n_threads: Annotated[
        int,
        typer.Option("--n-threads", "-t", help="Number of threads to use for chatbot"),
    ] = None,
    device: Annotated[
        str,
        typer.Option("--device", "-d", help="Device to use for chatbot, e.g. gpu, amd, nvidia, intel. Defaults to CPU."),
    ] = None,
    hexstrike_url: Annotated[
        str,
        typer.Option("--hexstrike-url", help="Hexstrike base URL."),
    ] = DEFAULT_HEXSTRIKE_URL,
    hexstrike_endpoint: Annotated[
        str,
        typer.Option("--hexstrike-endpoint", help="Hexstrike endpoint path."),
    ] = DEFAULT_HEXSTRIKE_ENDPOINT,
    auto_start_hexstrike: Annotated[
        bool,
        typer.Option("--auto-start-hexstrike/--no-auto-start-hexstrike", help="Auto-start Hexstrike server if not running."),
    ] = True,
    hexstrike_repo: Annotated[
        str,
        typer.Option("--hexstrike-repo", help="Path to local Hexstrike repo containing hexstrike_server.py."),
    ] = DEFAULT_HEXSTRIKE_REPO,
    python_exe: Annotated[
        str,
        typer.Option("--python-exe", help="Python executable to start Hexstrike server."),
    ] = sys.executable,
    server_start_timeout: Annotated[
        int,
        typer.Option("--server-start-timeout", help="Seconds to wait for server startup."),
    ] = 120,
    hexstrike_input: Annotated[
        str,
        typer.Option(
            "--hexstrike-input",
            help="What to send to Hexstrike: user, assistant, or both.",
            case_sensitive=False,
        ),
    ] = DEFAULT_HEXSTRIKE_INPUT,
    results_only: Annotated[
        bool,
        typer.Option(
            "--results-only/--no-results-only",
            help="Print Hexstrike execution results only.",
        ),
    ] = True,
    confirm_pentest_tools: Annotated[
        bool,
        typer.Option(
            "--confirm-pentest-tools/--no-confirm-pentest-tools",
            help="Ask before running non-safe commands through Hexstrike.",
        ),
    ] = DEFAULT_CONFIRM_PENTEST_TOOLS,
):
    """The CLI read-eval-print loop."""
    if BLKHATModel is None:
        raise typer.BadParameter(
            f"GPT4All is not available. Install dependencies first (pip install gpt4all typer requests). "
            f"Import error: {_gpt4all_import_error}"
        )

    normalized_input_mode = (hexstrike_input or "").strip().lower()
    if normalized_input_mode not in {"user", "assistant", "both"}:
        raise typer.BadParameter("--hexstrike-input must be one of: user, assistant, both")

    _assert_hexstrike_available(
        base_url=hexstrike_url,
        auto_start=auto_start_hexstrike,
        repo_path=Path(hexstrike_repo).expanduser().resolve(),
        python_exe=python_exe,
        timeout_seconds=server_start_timeout,
    )
    try:
        blk_hat_instance = BLKHATModel(model, device=device)
    except Exception as exc:
        raise typer.BadParameter(
            f"Failed to initialize GPT4All model '{model}'. "
            "Check model path/name and local runtime requirements."
        ) from exc

    # if threads are passed, set them
    if n_threads is not None:
        num_threads = blk_hat_instance.model.thread_count()
        print(f"\nAdjusted: {num_threads} â†’", end="")

        # set number of threads
        blk_hat_instance.model.set_thread_count(n_threads)

        num_threads = blk_hat_instance.model.thread_count()
        print(f" {num_threads} threads", end="", flush=True)
    else:
        print(f"\nUsing {blk_hat_instance.model.thread_count()} threads", end="")

    print(CLI_START_MESSAGE)

    use_new_loop = True
    if use_new_loop:
        _new_loop(
            blk_hat_instance,
            hexstrike_url,
            hexstrike_endpoint,
            normalized_input_mode,
            results_only,
            confirm_pentest_tools,
        )
    else:
        _old_loop(
            blk_hat_instance,
            hexstrike_url,
            hexstrike_endpoint,
            normalized_input_mode,
            results_only,
            confirm_pentest_tools,
        )


def _wait_for_port(base_url: str, timeout_seconds: int) -> bool:
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


def _start_hexstrike_server(repo_path: Path, python_exe: str):
    server_script = repo_path / "hexstrike_server.py"
    if not server_script.exists():
        raise typer.BadParameter(
            f"Hexstrike server script not found at {server_script}"
        )

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    server_env = os.environ.copy()
    server_env.setdefault("PYTHONUTF8", "1")
    server_env.setdefault("PYTHONIOENCODING", "utf-8")
    subprocess.Popen(
        [python_exe, "-X", "utf8", str(server_script)],
        cwd=str(repo_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=server_env,
        creationflags=creationflags,
    )


def _assert_hexstrike_available(
    base_url: str,
    auto_start: bool,
    repo_path: Path,
    python_exe: str,
    timeout_seconds: int,
):
    if _wait_for_port(base_url, timeout_seconds=2):
        return

    if auto_start:
        _start_hexstrike_server(repo_path, python_exe)
        if _wait_for_port(base_url, timeout_seconds=timeout_seconds):
            return
        raise typer.BadParameter(
            f"Hexstrike server did not start in time at {base_url}. Check logs in {repo_path}."
        )

    try:
        response = requests.get(base_url.rstrip("/") + "/health", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise typer.BadParameter(
            f"Cannot reach Hexstrike server at {base_url}. Start it first and retry."
        ) from exc


def _send_to_hexstrike(model_output: str, base_url: str, endpoint: str):
    url = base_url.rstrip("/") + endpoint
    if endpoint.strip() == "/api/command":
        payload = {"command": model_output, "use_cache": True}
    else:
        payload = {"target": model_output}
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        print(f"\n[Hexstrike Error] Request failed: {exc}")
        return None
    except ValueError:
        print("\n[Hexstrike Error] Non-JSON response received.")
        return None


def _print_hexstrike_response(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _build_hexstrike_input(user_message: str, assistant_message: str, input_mode: str) -> str:
    if input_mode == "assistant":
        return assistant_message
    if input_mode == "both":
        return f"User request:\n{user_message}\n\nAssistant response:\n{assistant_message}"
    return user_message


def _derive_platform_command(user_message: str) -> str | None:
    text = (user_message or "").lower()
    is_windows = os.name == "nt"

    if "open port" in text and ("process" in text or "pid" in text):
        return "netstat -ano & tasklist" if is_windows else "ss -tulpn && ps aux"
    if "open port" in text or "ports" in text:
        return "netstat -ano" if is_windows else "ss -tulpn"
    if "running process" in text or "processes" in text:
        return "tasklist" if is_windows else "ps aux"
    return None


def _clean_assistant_command(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return stripped

    stripped = (
        stripped
        .replace("```bash", "")
        .replace("```sh", "")
        .replace("```cmd", "")
        .replace("```powershell", "")
        .replace("```ps1", "")
        .replace("```", "")
        .strip()
    )

    known_cmd_heads = {
        "netstat", "tasklist", "wmic", "ipconfig", "systeminfo", "findstr",
        "powershell", "pwsh", "Get-NetTCPConnection", "Get-Process", "Get-Service",
        "Get-ChildItem", "curl", "nmap", "ss", "lsof", "ps",
    }
    non_command_starts = {
        "sure", "here", "to", "you", "this", "run", "use", "try", "i", "we", "let",
        "the", "a", "an", "first", "then", "note", "please",
    }

    candidates = []
    for raw_line in stripped.splitlines():
        line = raw_line.strip().strip("`").strip()
        if not line:
            continue
        if line.startswith(("-", "*")):
            line = line[1:].strip()
        if len(line) > 3 and line[0].isdigit() and line[1] in {".", ")"}:
            line = line[2:].strip()
        if ":" in line:
            left, right = line.split(":", 1)
            if left.strip().lower() in {"command", "cmd", "powershell", "bash", "sh"} and right.strip():
                line = right.strip()
        candidates.append(line)

    for line in candidates:
        token = line.split()[0] if line.split() else ""
        if token in known_cmd_heads:
            return line

    for line in candidates:
        words = line.split()
        if not words:
            continue
        first = words[0].lower().rstrip(",.:;")
        if first in non_command_starts:
            continue
        if len(words) >= 2 and first == "for" and words[1].lower() in {"example", "instance"}:
            continue
        return line

    return candidates[0] if candidates else stripped


def _prepare_execution_payload(
    user_message: str,
    assistant_message: str,
    hexstrike_endpoint: str,
    hexstrike_input_mode: str,
) -> str:
    if hexstrike_endpoint.strip() == "/api/command":
        mapped = _derive_platform_command(user_message)
        if mapped:
            return mapped
    return _build_hexstrike_input(user_message, assistant_message, hexstrike_input_mode)


def _normalize_head_token(token: str) -> str:
    out = token.lower().strip("`'\"(),")
    if out.endswith(".exe"):
        out = out[:-4]
    return out


def _extract_command_heads(command_text: str) -> list[str]:
    normalized = (command_text or "")
    for sep in ["\r", "\n", "|", ";", "&&", "||"]:
        normalized = normalized.replace(sep, "&")

    segments = [seg.strip() for seg in normalized.split("&") if seg.strip()]
    heads: list[str] = []
    for seg in segments:
        parts = [p for p in seg.split() if p]
        if not parts:
            continue

        first = _normalize_head_token(parts[0])
        if first == "cmd" and len(parts) >= 3 and _normalize_head_token(parts[1]) == "/c":
            first = _normalize_head_token(parts[2])
        elif first in {"powershell", "pwsh"} and len(parts) >= 2:
            # keep powershell as the executable head itself
            first = _normalize_head_token(parts[0])

        heads.append(first)
    return heads


def _requires_user_approval(command_text: str) -> bool:
    safe_heads = SAFE_COMMAND_HEADS if os.name == "nt" else SAFE_COMMAND_HEADS_POSIX
    heads = _extract_command_heads(command_text)
    if not heads:
        return True
    if any(head in PENTEST_TOOL_HEADS for head in heads):
        return True
    if STRICT_APPROVAL_FOR_NONSAFE_COMMANDS:
        return any(head not in safe_heads for head in heads)
    return False


def _confirm_command_execution(command_text: str) -> bool:
    answer = input(f"Approve command execution? [{command_text}] (y/N): ").strip().lower()
    return answer in {"y", "yes"}


def _old_loop(
    blk_hat_instance,
    hexstrike_url: str,
    hexstrike_endpoint: str,
    hexstrike_input_mode: str,
    results_only: bool,
    confirm_pentest_tools: bool,
):
    while True:
        message = input("> ")

        # Check if special command and take action
        if message in SPECIAL_COMMANDS:
            SPECIAL_COMMANDS[message](MESSAGES)
            continue

        # if regular message, append to messages
        MESSAGES.append({"role": "user", "content": message})

        # execute chat completion and ignore the full response since 
        # we are outputting it incrementally
        full_response = blk_hat_instance.chat_completion(
            MESSAGES,
            # preferential kwargs for chat ux
            n_past=0,
            n_predict=200,
            top_k=40,
            top_p=0.9,
            min_p=0.0,
            temp=0.9,
            n_batch=9,
            repeat_penalty=1.1,
            repeat_last_n=64,
            context_erase=0.0,
            # required kwargs for cli ux (incremental response)
            verbose=False,
            streaming=True,
        )
        # record assistant's response to messages
        response_message = full_response.get("choices")[0].get("message")
        MESSAGES.append(response_message)
        assistant_content = response_message.get("content", "")
        cleaned_assistant_content = _clean_assistant_command(assistant_content)
        if not results_only:
            print(assistant_content)
        hexstrike_payload = _prepare_execution_payload(
            message,
            cleaned_assistant_content,
            hexstrike_endpoint,
            hexstrike_input_mode,
        )
        if (
            hexstrike_endpoint.strip() == "/api/command"
            and confirm_pentest_tools
            and _requires_user_approval(hexstrike_payload)
            and not _confirm_command_execution(hexstrike_payload)
        ):
            print('{"success": false, "cancelled": true, "reason": "User denied command execution"}')
            print()
            continue
        hexstrike_response = _send_to_hexstrike(
            hexstrike_payload,
            hexstrike_url,
            hexstrike_endpoint,
        )
        if (
            hexstrike_endpoint.strip() == "/api/command"
            and isinstance(hexstrike_response, dict)
            and not hexstrike_response.get("success")
            and isinstance(hexstrike_response.get("stderr"), str)
            and "syntax of the command is incorrect" in hexstrike_response["stderr"].lower()
        ):
            mapped_fallback = _derive_platform_command(message)
            if mapped_fallback and mapped_fallback != hexstrike_payload:
                hexstrike_response = _send_to_hexstrike(
                    mapped_fallback,
                    hexstrike_url,
                    hexstrike_endpoint,
                )
        if hexstrike_response is not None:
            _print_hexstrike_response(hexstrike_response)
        print() # newline before next prompt


def _new_loop(
    blk_hat_instance,
    hexstrike_url: str,
    hexstrike_endpoint: str,
    hexstrike_input_mode: str,
    results_only: bool,
    confirm_pentest_tools: bool,
):
    with blk_hat_instance.chat_session():
        while True:
            message = input("> ")

            # Check if special command and take action
            if message in SPECIAL_COMMANDS:
                SPECIAL_COMMANDS[message](MESSAGES)
                continue

            # if regular message, append to messages
            MESSAGES.append({"role": "user", "content": message})

            # execute chat completion and ignore the full response since 
            # we are outputting it incrementally
            response_generator = blk_hat_instance.generate(
                message,
                # preferential kwargs for chat ux
                max_tokens=200,
                temp=0.9,
                top_k=40,
                top_p=0.9,
                min_p=0.0,
                repeat_penalty=1.1,
                repeat_last_n=64,
                n_batch=9,
                # required kwargs for cli ux (incremental response)
                streaming=True,
            )
            response = io.StringIO()
            for token in response_generator:
                if not results_only:
                    print(token, end='', flush=True)
                response.write(token)

            # record assistant's response to messages
            response_message = {'role': 'assistant', 'content': response.getvalue()}
            response.close()
            blk_hat_instance.current_chat_session.append(response_message)
            MESSAGES.append(response_message)
            assistant_content = response_message.get("content", "")
            cleaned_assistant_content = _clean_assistant_command(assistant_content)
            hexstrike_payload = _prepare_execution_payload(
                message,
                cleaned_assistant_content,
                hexstrike_endpoint,
                hexstrike_input_mode,
            )
            if (
                hexstrike_endpoint.strip() == "/api/command"
                and confirm_pentest_tools
                and _requires_user_approval(hexstrike_payload)
                and not _confirm_command_execution(hexstrike_payload)
            ):
                print('{"success": false, "cancelled": true, "reason": "User denied command execution"}')
                print()
                continue
            hexstrike_response = _send_to_hexstrike(
                hexstrike_payload,
                hexstrike_url,
                hexstrike_endpoint,
            )
            if (
                hexstrike_endpoint.strip() == "/api/command"
                and isinstance(hexstrike_response, dict)
                and not hexstrike_response.get("success")
                and isinstance(hexstrike_response.get("stderr"), str)
                and "syntax of the command is incorrect" in hexstrike_response["stderr"].lower()
            ):
                mapped_fallback = _derive_platform_command(message)
                if mapped_fallback and mapped_fallback != hexstrike_payload:
                    hexstrike_response = _send_to_hexstrike(
                        mapped_fallback,
                        hexstrike_url,
                        hexstrike_endpoint,
                    )
            if hexstrike_response is not None:
                _print_hexstrike_response(hexstrike_response)
            print() # newline before next prompt


@app.command()
def version():
    """The CLI version command."""
    print(f"blk-hat-cli v{VERSION}")


if __name__ == "__main__":
    app()


