#!/usr/bin/env python3
"""Small, credential-free pass/fail loop for the live usage reader."""

import argparse
import json
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="read both Usage pages if not paused")
    args = parser.parse_args()
    config = json.loads((Path.home() / ".config/limity-ai-widget/config.json").read_text())
    base = f"http://127.0.0.1:{config['port']}"

    def call(path, method="GET"):
        request = urllib.request.Request(
            base + path, method=method, headers={"X-Limity-Token": config["token"]}
        )
        with urllib.request.urlopen(request, timeout=4) as response:
            return json.load(response)

    state = call("/status")
    if args.refresh:
        if state["paused"] or not state.get("fullscreenKnown", True):
            print("RED: odczyt wstrzymany przez stan pełnego ekranu")
            raise SystemExit(1)
        if state["browserOpen"]:
            print("RED: przeglądarka logowania jest nadal otwarta")
            raise SystemExit(1)
        call("/refresh", "POST")
        time.sleep(0.3)  # Let the Qt action queue start the new read.
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            state = call("/status")
            if not state["busy"] and all(state[name]["state"] != "checking" for name in ("chatgpt", "claude")):
                break
            time.sleep(0.5)

    found = {
        name: {
            "state": state[name]["state"],
            "session": state[name]["session"]["remaining"],
            "weekly": state[name]["weekly"]["remaining"],
        }
        for name in ("chatgpt", "claude")
    }
    print(json.dumps({"paused": state["paused"], "fullscreenKnown": state.get("fullscreenKnown"), "browserOpen": state["browserOpen"], "limits": found}, ensure_ascii=False))
    required = [found["chatgpt"]["weekly"], found["claude"]["session"], found["claude"]["weekly"]]
    if all(value is not None for value in required):
        print("GREEN: dostępne są trzy wymagane procenty")
    else:
        print("RED: brakuje co najmniej jednego wymaganego procentu")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
