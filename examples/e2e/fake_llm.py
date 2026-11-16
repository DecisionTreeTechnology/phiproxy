"""A fake OpenAI-compatible provider for end-to-end tests.

It records every request body it receives (to prove what would have left your
network) and replies by echoing the last user message, so the reply contains
whatever tokens the provider saw.

    python fake_llm.py --port 4010 --record received.jsonl
"""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def last_user_text(body: dict) -> str:
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") == "user":
            c = msg.get("content")
            if isinstance(c, str):
                return c
            return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


class Handler(BaseHTTPRequestHandler):
    record_path = "received.jsonl"

    def log_message(self, *args):  # quiet
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        with open(self.record_path, "a") as f:
            f.write(json.dumps(body) + "\n")
        reply = f"Echo: {last_user_text(body)}"
        created = int(time.time())
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            # Split into small pieces so tokens get cut across chunks.
            for i in range(0, len(reply), 3):
                chunk = {"id": "c1", "object": "chat.completion.chunk", "created": created, "model": "fake",
                         "choices": [{"index": 0, "delta": {"content": reply[i : i + 3]}, "finish_reason": None}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            done = {"id": "c1", "object": "chat.completion.chunk", "created": created, "model": "fake",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            self.wfile.write(f"data: {json.dumps(done)}\n\ndata: [DONE]\n\n".encode())
            return
        out = {
            "id": "c1", "object": "chat.completion", "created": created, "model": "fake",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4010)
    ap.add_argument("--record", default="received.jsonl")
    a = ap.parse_args()
    Handler.record_path = a.record
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
