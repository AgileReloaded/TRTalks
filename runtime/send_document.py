#!/usr/bin/env python3
"""Deliver approved Markdown via the existing HTTP JSON-RPC contract."""
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import sys
import uuid

from common import atomic_json, canonical, digest, fetch, load_config, locked, now, plain_path, response_json


def rpc_body(name, arguments, request_id):
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
            "params": {"name": name, "arguments": arguments}}


def rpc_result(exchange, request_id):
    body = response_json(exchange)
    if body.get("jsonrpc") != "2.0" or body.get("id") != request_id:
        raise ValueError("Risposta JSON-RPC non correlata alla richiesta")
    if "error" in body:
        raise ValueError("Errore JSON-RPC: " + json.dumps(body["error"], ensure_ascii=False))
    result = body.get("result")
    if not isinstance(result, dict) or type(result.get("isError")) is not bool:
        raise ValueError("Risultato JSON-RPC non valido")
    blocks = result.get("content")
    if not (isinstance(blocks, list) and len(blocks) == 1 and isinstance(blocks[0], dict)
            and blocks[0].get("type") == "text" and isinstance(blocks[0].get("text"), str)):
        raise ValueError("Contenuto JSON-RPC inatteso")
    value = json.loads(blocks[0]["text"])
    if not isinstance(value, dict):
        raise ValueError("Ricevuta applicativa non valida")
    return value, result["isError"]


def status(root, transport=None):
    config = load_config(root)
    request_id = "status-" + uuid.uuid4().hex
    exchange = (transport or fetch)(config["endpoint"], rpc_body("connection-status", {}, request_id))
    receipt, failed = rpc_result(exchange, request_id)
    return {"verified": not failed and receipt.get("ready") is True,
            "email_delivery": "not_requested", "exchange": exchange, "receipt": receipt}


def validated_document(file, config, name=None, email=None):
    file = Path(file)
    if file.is_symlink():
        raise ValueError("La bozza deve essere un file regolare")
    # A bounded read also refuses oversized documents without loading them fully.
    with file.open("rb") as stream:
        raw = stream.read(262145)
    text = raw.decode("utf-8")
    if not text.strip() or len(raw) > 262144 or b"\0" in raw:
        raise ValueError("Markdown vuoto, troppo grande o contenente NUL")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}\.md", file.name):
        raise ValueError("Nome file non valido per il backend: usare lettere, numeri, _ o - e .md")
    name = config["sender_name"] if name is None else name
    email = config["reply_to"] if email is None else email
    if (not isinstance(name, str) or not name.strip() or len(name.encode("utf-8")) > 200
            or re.search(r"[\x00-\x1f\x7f]", name)):
        raise ValueError("Nome mittente obbligatorio e valido, massimo 200 byte UTF-8")
    if (not isinstance(email, str) or len(email.encode("utf-8")) > 254
            or (email and not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", email))):
        raise ValueError("Reply-To non valido")
    return {"approved": True, "name": name, "email": email,
            "filename": file.name, "markdown": text}, digest(raw)


def dry_run(root, file, name=None, email=None):
    config = load_config(root)
    args, sha = validated_document(file, config, name, email)
    return {"network_called": False, "email_delivery": "not_requested", "sha256": sha,
            "bytes": len(args["markdown"].encode("utf-8")), "filename": args["filename"],
            "recipient": config["recipient"], "send_enabled": config["send_enabled"]}


def transmit(root, record_path, record, transport=None):
    # Persist before network: a crash must leave an uncertain attempt, never a fresh ID.
    record["status"] = "pending"
    record["last_attempt_at"] = now()
    atomic_json(record_path, record)
    outcome = {"request_id": record["request_id"], "backend_accepted": None,
               "email_delivery": "unconfirmed", "cached": False}
    try:
        exchange = (transport or fetch)(record["endpoint"], record["payload"])
        outcome["exchange"] = exchange
        record.setdefault("attempts", []).append({"at": now(), "exchange": exchange})
        receipt, failed = rpc_result(exchange, record["request_id"])
        status_code = receipt.get("http_status")
        submission = receipt.get("submission", receipt)
        if not isinstance(submission, dict):
            raise ValueError("Ricevuta submission non valida")
        accepted = (not failed and type(status_code) is int and status_code in (200, 202)
                    and submission.get("ok") is True and submission.get("status") == "accepted"
                    and submission.get("request_id") == record["request_id"]
                    and submission.get("recipient", "info@techreloaded.it") == "info@techreloaded.it")
        record["status"] = "accepted" if accepted else "rejected"
        if submission.get("error") in ("previous_attempt_requires_review", "request_id_conflict"):
            record["status"] = "review_required"
        if not accepted and not failed:
            record["status"] = "uncertain"
        outcome.update(backend_accepted=True if accepted else None,
                       request_rejected=failed, receipt=receipt, exchange=exchange)
    except (OSError, ValueError, TypeError) as error:
        record["status"] = "uncertain"
        outcome["error"] = str(error)
        record.setdefault("attempts", []).append({"at": now(), "error": str(error)})
    record["outcome"] = outcome
    atomic_json(record_path, record)
    return dict(outcome, local_status=record["status"], state_file=str(record_path))


def send(root, file, approved_sha256, authorization, name=None, email=None, transport=None):
    root = Path(root).resolve()
    config = load_config(root)
    if config["send_enabled"] is not True:
        raise ValueError("Invio disabilitato nella configurazione locale; nessuna richiesta eseguita")
    args, sha = validated_document(file, config, name, email)
    if approved_sha256 != sha or not authorization or not authorization.strip():
        raise ValueError("Manca l'autorizzazione esplicita o la bozza differisce dalla versione autorizzata")
    with locked(root / ".trtalks" / "delivery.lock"):
        directory = plain_path(root / ".trtalks" / "deliveries")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fingerprint = digest(canonical({"endpoint": config["endpoint"], "arguments": args}))
        for path in directory.glob("trtalks-*.json"):
            record = json.loads(plain_path(path).read_text(encoding="utf-8"))
            if record["document_sha256"] != sha:
                continue
            if record["fingerprint"] != fingerprint:
                raise ValueError("Documento già registrato con altri metadati: verificare prima di creare un altro invio")
            if record["status"] == "accepted":
                return dict(record["outcome"], cached=True, state_file=str(path))
            raise ValueError("Tentativo già registrato: usare retry con lo stesso request_id " + record["request_id"])
        request_id = "trtalks-" + uuid.uuid4().hex
        args["request_id"] = request_id
        record = {"schema": 1, "created_at": now(), "request_id": request_id,
                  "endpoint": config["endpoint"], "document_sha256": sha, "fingerprint": fingerprint,
                  "authorization": authorization, "draft_path": str(Path(file).resolve()),
                  "payload": rpc_body("send-document", args, request_id), "status": "prepared", "attempts": []}
        path = directory / (request_id + ".json")
        atomic_json(path, record)
        return transmit(root, path, record, transport)


def retry(root, request_id, transport=None):
    if not re.fullmatch(r"trtalks-[a-f0-9]{32}", request_id):
        raise ValueError("request_id non valido")
    root = Path(root).resolve()
    config = load_config(root)
    if not config["send_enabled"]:
        raise ValueError("Invio disabilitato")
    with locked(root / ".trtalks" / "delivery.lock"):
        path = plain_path(root / ".trtalks" / "deliveries" / (request_id + ".json"))
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["status"] == "accepted":
            return dict(record["outcome"], cached=True, state_file=str(path))
        if record["status"] == "review_required":
            raise ValueError("Il backend richiede revisione: nessun nuovo tentativo automatico")
        if datetime.now(timezone.utc) - datetime.fromisoformat(record["created_at"]) > timedelta(days=150):
            raise ValueError("Tentativo troppo vecchio per affidarsi alla deduplicazione del backend")
        if config["endpoint"] != record["endpoint"]:
            raise ValueError("Endpoint cambiato: ritentativo bloccato")
        args = dict(record["payload"]["params"]["arguments"])
        if args.pop("request_id") != request_id or digest(args["markdown"].encode("utf-8")) != record["document_sha256"]:
            raise ValueError("Stato del tentativo corrotto")
        if digest(canonical({"endpoint": record["endpoint"], "arguments": args})) != record["fingerprint"]:
            raise ValueError("Payload salvato modificato")
        frozen_args = dict(args, request_id=request_id)
        if record["payload"] != rpc_body("send-document", frozen_args, request_id):
            raise ValueError("Messaggio JSON-RPC salvato modificato")
        return transmit(root, path, record, transport)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    for command in ("dry-run", "send"):
        part = commands.add_parser(command)
        part.add_argument("file", type=Path)
        part.add_argument("--name")
        part.add_argument("--email")
        if command == "send":
            part.add_argument("--approved-sha256", required=True)
            part.add_argument("--authorization", required=True)
    commands.add_parser("retry").add_argument("request_id")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status(args.root)
        elif args.command == "dry-run":
            result = dry_run(args.root, args.file, args.name, args.email)
        elif args.command == "send":
            result = send(args.root, args.file, args.approved_sha256, args.authorization, args.name, args.email)
        else:
            result = retry(args.root, args.request_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("backend_accepted", result.get("verified", result.get("network_called") is False)) else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"ok": False, "error": str(error), "email_delivery": "unconfirmed"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
