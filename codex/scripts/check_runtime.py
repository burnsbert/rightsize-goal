#!/usr/bin/env python3
"""Check skill discovery in an isolated Codex app server without calling a model."""

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading


def main():
    package = Path(__file__).resolve().parents[1]
    executable = shutil.which("codex.cmd" if os.name == "nt" else "codex")
    if executable is None:
        raise SystemExit("Codex CLI is not on PATH.")
    with tempfile.TemporaryDirectory(prefix="rightsize-runtime-") as directory:
        root = Path(directory)
        codex_home = root / ".codex"
        subprocess.run([sys.executable, str(package / "install.py"),
                        "--codex-dir", str(codex_home),
                        "--skills-dir", str(root / ".agents/skills")], check=True)
        environment = dict(os.environ, CODEX_HOME=str(codex_home))
        # No auth files are copied; only local discovery is requested.
        process = subprocess.Popen([executable, "app-server", "--stdio"],
                                   cwd=root, env=environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, encoding="utf-8")
        messages = queue.Queue()

        def read_output():
            for line in process.stdout:
                try:
                    messages.put(json.loads(line))
                except json.JSONDecodeError:
                    pass
            messages.put(None)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()

        def send(message):
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()

        def response(identifier):
            import time
            deadline = time.monotonic() + 20
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("Codex discovery timed out")
                message = messages.get(timeout=remaining)
                if message is None:
                    raise RuntimeError("Codex exited before discovery completed")
                if message.get("id") == identifier:
                    if "error" in message:
                        raise RuntimeError(str(message["error"]))
                    return message["result"]

        try:
            send({"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "rightsize-release-check", "version": "0.1"}}})
            response(1)
            send({"method": "initialized", "params": {}})
            send({"id": 2, "method": "skills/list", "params": {
                "cwds": [str(root)], "forceReload": True}})
            result = response(2)
            matches = [skill for group in result["data"] for skill in group["skills"]
                       if skill["name"] == "rightsize-goal"]
            expected = root / ".agents/skills/rightsize-goal/SKILL.md"
            if not any(Path(skill["path"]).resolve() == expected.resolve() for skill in matches):
                raise RuntimeError("Installed skill was not discovered at its expected path")
            print("PASS: Codex discovered the freshly installed skill; no model turn started.")
            print("Custom-agent loading, model access, and native goal execution need a live smoke test.")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            process.stdin.close()
            reader.join(timeout=5)
            process.stdout.close()


if __name__ == "__main__":
    main()
