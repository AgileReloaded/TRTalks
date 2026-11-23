#!/usr/bin/env python3
"""TRTalks HTTP probe: fixed synthetic Markdown only, no email operation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
import uuid

ENDPOINT = "https://techreloaded.it/shared/php/trdocument-http-test.php"
SERVICE = "trinterview-http-test"
MARKDOWN = ('# Prova HTTP TRTalks\n\n'
            'Documento fittizio per verificare il trasporto HTTP.\n'
            'Non contiene risposte di intervista e non deve generare email.\n\n'
            'UTF-8: caffè, città, "virgolette", & e +, 🚲.\n')
MAX_RESPONSE = 65536


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(method, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=data, method=method, headers={
        "Accept": "application/json", "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "TRTalks-Probe/0.1.0"})
    try:
        response = urllib.request.build_opener(NoRedirect()).open(req, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(MAX_RESPONSE + 1)
        exchange = {"method": method, "http_status": response.code,
                    "content_type": response.headers.get_content_type(),
                    "body": raw[:MAX_RESPONSE].decode("utf-8", errors="replace"),
                    "body_truncated": len(raw) > MAX_RESPONSE}
    return exchange


def verify(exchange, payload=None):
    if (exchange["http_status"] != 200 or exchange["content_type"] != "application/json"
            or exchange["body_truncated"]):
        raise ValueError("unexpected_http_response")
    receipt = json.loads(exchange["body"])
    if not (isinstance(receipt, dict) and receipt.get("ok") is True
            and receipt.get("service") == SERVICE and receipt.get("email_sent") is False
            and receipt.get("stored") is False):
        raise ValueError("unexpected_service_receipt")
    if payload is None:
        if receipt.get("status") != "ready":
            raise ValueError("service_not_ready")
    elif not (receipt.get("status") == "received"
              and receipt.get("request_id") == payload["request_id"]
              and receipt.get("markdown") == payload["markdown"]
              and type(receipt.get("bytes")) is int
              and receipt["bytes"] == len(payload["markdown"].encode("utf-8"))
              and receipt.get("sha256") == hashlib.sha256(payload["markdown"].encode("utf-8")).hexdigest()):
        raise ValueError("document_echo_mismatch")
    return receipt


def exclusive_write(path, value):
    # No shell, no replacement of existing files or symlink targets.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=True)
    draft = directory / "prova-http.md"
    if draft.is_symlink():
        raise ValueError("draft_is_symlink")
    try:
        exclusive_write(draft, MARKDOWN)
    except FileExistsError:
        if draft.read_bytes() != MARKDOWN.encode("utf-8"):
            raise ValueError("existing_draft_differs_use_another_output_directory")
    state = directory / "probe-request.json"
    if state.is_symlink():
        raise ValueError("request_state_is_symlink")
    payload = {"request_id": "probe-" + uuid.uuid4().hex, "markdown": MARKDOWN}
    try:
        exclusive_write(state, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError:
        payload = json.loads(state.read_text(encoding="utf-8"))
    if not (isinstance(payload, dict) and set(payload) == {"request_id", "markdown"}
            and isinstance(payload["request_id"], str)
            and re.fullmatch(r"probe-[a-f0-9]{32}", payload["request_id"])
            and payload["markdown"] == MARKDOWN):
        raise ValueError("invalid_saved_probe_request")
    return draft, payload


def run(mode, directory):
    result = {"verified": False, "mode": mode, "endpoint": ENDPOINT,
              "timestamp": datetime.now(timezone.utc).isoformat(),
              "production_endpoint_called": False, "exchanges": []}
    try:
        payload = None
        if mode == "probe":
            draft, payload = prepare(directory)
            result.update(draft=str(draft.resolve()), request_id=payload["request_id"])
        result["stage"] = "GET"
        exchange = request("GET")
        result["exchanges"].append(exchange)
        receipt = verify(exchange)
        if payload is not None:
            result["stage"] = "POST"
            exchange = request("POST", payload)
            result["exchanges"].append(exchange)
            receipt = verify(exchange, payload)
        result.update(verified=True, receipt=receipt)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        result.update(error="network_or_filesystem_error", detail=str(error))
    except (ValueError, UnicodeError, TypeError) as error:
        result.update(error="validation_error", detail=str(error))
    return result


def main_with_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["status", "probe"])
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    args = parser.parse_args(argv)
    if sys.version_info < (3, 9):
        parser.error("Serve Python 3.9 o successivo")
    result = run(args.mode, args.output_dir)
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        log = args.output_dir / ("http-attempt-" + uuid.uuid4().hex + ".json")
        exclusive_write(log, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        result["evidence_file"] = str(log.resolve())
    except OSError as error:
        result["evidence_save_error"] = str(error)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verified"] and "evidence_save_error" not in result else 1


def main():
    return main_with_args()


if __name__ == "__main__":
    sys.exit(main())
