"""End-to-end check through a real LiteLLM proxy.

Starts the fake provider and `litellm --config config.yaml`, sends requests that
contain PHI, then checks two things:
  1. what the provider received contains none of the PHI, and
  2. what the client got back has the PHI restored.

    pip install "phiproxy[litellm]" "litellm[proxy]"
    python examples/e2e/run_e2e.py
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
PROXY = "http://127.0.0.1:4011"
MASTER_KEY = "sk-" + secrets.token_hex(24)  # throwaway key for this run
PHI = ["Sarah Chen", "sarah", "416-555-0142", "416 555 0142", "1990-03-05", "1234-567-890"]


def post(path: str, body: dict, stream: bool = False) -> tuple[int, str]:
    req = urllib.request.Request(
        PROXY + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {MASTER_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            if not stream:
                return r.status, json.loads(raw)["choices"][0]["message"]["content"]
            text = ""
            for line in raw.splitlines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    for ch in json.loads(line[6:]).get("choices", []):
                        text += (ch.get("delta") or {}).get("content") or ""
            return r.status, text
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def wait_for(url: str, timeout: float = 90) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except urllib.error.HTTPError:
            return  # server is up, route may 401/404
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not come up")


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    record = tmp / "received.jsonl"
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "LITELLM_MASTER_KEY": MASTER_KEY}
    fake = subprocess.Popen([sys.executable, str(HERE / "fake_llm.py"), "--port", "4010", "--record", str(record)])
    litellm_bin = Path(sys.executable).with_name("litellm")
    proxy_log = open(tmp / "proxy.log", "w")
    proxy = subprocess.Popen(
        [str(litellm_bin), "--config", str(HERE / "config.yaml"), "--port", "4011"],
        stdout=proxy_log, stderr=subprocess.STDOUT, env=env,
    )
    failures: list[str] = []
    try:
        wait_for("http://127.0.0.1:4010/")
        wait_for(PROXY + "/health/liveliness")
        msg = "Hi, this is Sarah Chen, DOB 1990-03-05, OHIP 1234-567-890-AB. Call me at 416-555-0142."
        known = {"names": ["Sarah Chen"], "phones": ["416-555-0142"], "dates_of_birth": ["1990-03-05"]}
        base = {"model": "fake", "messages": [{"role": "user", "content": msg}],
                "metadata": {"session_id": "e2e-1", "phiproxy_known": known}}

        status, reply = post("/v1/chat/completions", base)
        check(failures, status == 200, f"non-stream status {status}: {reply}")
        check(failures, reply == f"Echo: {msg}", f"non-stream reply not restored: {reply!r}")

        status, reply = post("/v1/chat/completions", {**base, "stream": True}, stream=True)
        check(failures, status == 200, f"stream status {status}")
        check(failures, reply == f"Echo: {msg}", f"stream reply not restored: {reply!r}")

        optout = {**base, "metadata": {**base["metadata"], "disable_global_guardrail": True}}
        post("/v1/chat/completions", optout)

        n_before = count_lines(record)
        img = {"model": "fake", "messages": [{"role": "user", "content": [
            {"type": "text", "text": "see my scan"},
            {"type": "image_url", "image_url": {"url": "https://example.com/scan.png"}}]}]}
        status, body = post("/v1/chat/completions", img)
        check(failures, status >= 400, f"image request was not rejected (status {status})")
        check(failures, count_lines(record) == n_before, "image request reached the provider")

        received = record.read_text() if record.exists() else ""
        check(failures, received.count("\n") >= 3, "provider did not receive the expected requests")
        for s in PHI:
            check(failures, s.lower() not in received.lower(), f"provider received PHI: {s!r}")
        check(failures, "[NAME_1]" in received and "[PHONE_1]" in received, "provider did not get tokens")
        check(failures, "phiproxy_known" not in received, "known-entity list was forwarded to the provider")
    finally:
        proxy.terminate()
        fake.terminate()
        proxy.wait(10)
        fake.wait(10)
    if failures:
        print("FAIL")
        for f in failures:
            print("  -", f)
        print(f"proxy log: {tmp / 'proxy.log'}\nprovider record: {record}")
        return 1
    print("PASS: provider saw tokens only; client got PHI back (plain + streaming); image blocked; opt-out ignored")
    print(f"provider record: {record}")
    return 0


def count_lines(p: Path) -> int:
    return p.read_text().count("\n") if p.exists() else 0


def check(failures: list[str], ok: bool, msg: str) -> None:
    if not ok:
        failures.append(msg)


if __name__ == "__main__":
    sys.exit(main())
