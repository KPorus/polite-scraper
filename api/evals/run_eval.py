#!/usr/bin/env python3
"""Run the hand-labelled enrich eval set against a live API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "cases.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    passed = 0
    failures: list[str] = []

    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        for case in cases:
            cid = case["id"]
            try:
                res = client.post("/enrich", json={"query": case["query"]})
            except httpx.HTTPError as exc:
                failures.append(f"{cid}: request error {exc}")
                print(f"FAIL {cid}: request error {exc}", flush=True)
                continue

            if res.status_code != 200:
                failures.append(f"{cid}: HTTP {res.status_code} {res.text[:200]}")
                print(f"FAIL {cid}: HTTP {res.status_code}", flush=True)
                continue

            body = res.json()
            expect = case["expect"]
            ok = True
            reasons: list[str] = []
            for key, want in expect.items():
                got = body.get(key)
                if got != want:
                    ok = False
                    reasons.append(f"{key} want={want!r} got={got!r}")
            max_conf = case.get("max_confidence")
            if max_conf is not None and float(body.get("confidence", 1)) > max_conf:
                ok = False
                reasons.append(f"confidence {body.get('confidence')} > {max_conf}")

            if ok:
                passed += 1
                print(f"PASS {cid}: category={body.get('category')} book_type={body.get('book_type')}", flush=True)
            else:
                msg = "; ".join(reasons)
                failures.append(f"{cid}: {msg}")
                print(f"FAIL {cid}: {msg}", flush=True)

    total = len(cases)
    print(f"\nScore: {passed}/{total} ({100.0 * passed / total:.0f}%) on key fields category+book_type", flush=True)
    if failures:
        print("Failures:")
        for f in failures:
            print(f"  - {f}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
