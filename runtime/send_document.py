#!/usr/bin/env python3
"""Deliver approved Markdown by local SMTP, retaining drafts and safe retry state."""
import argparse
import base64
from email import policy
from email.message import EmailMessage
from email.utils import formataddr, formatdate
import json
from pathlib import Path
import re
import sys
import uuid

from common import atomic_json, canonical, digest, email_address, load_config, locked, now, plain_path
from delivery import DeliveryError, smtp_transport


def route(config):
    # Passwords stay exclusively in config.local.json; not even their hash is stored.
    return {key: config[key] for key in
            ("smtp_host", "smtp_port", "smtp_username", "smtp_from", "recipient")}


def status(root, transport=None):
    config = load_config(root)
    result = {"verified": False, "operation": "smtp-status", "transport": "smtp",
              "smtp_host": config["smtp_host"], "smtp_port": config["smtp_port"],
              "recipient": config["recipient"], "email_delivery": "not_requested"}
    try:
        receipt = (transport or smtp_transport)(config)
        result.update(verified=receipt.get("authenticated") is True
                      and receipt.get("smtp_code") == 250
                      and receipt.get("email_sent") is False, receipt=receipt)
    except DeliveryError as error:
        result.update(error=str(error), smtp_code=error.code)
    return result


def validated_document(file, config, name=None, email=None):
    file = plain_path(Path(file))
    if not file.is_file():
        raise ValueError("La bozza deve essere un file regolare")
    with file.open("rb") as stream:
        raw = stream.read(262145)
    text = raw.decode("utf-8")
    if not text.strip() or len(raw) > 262144 or b"\0" in raw:
        raise ValueError("Markdown vuoto, troppo grande o contenente NUL")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}\.md", file.name):
        raise ValueError("Nome file non valido: usare lettere, numeri, _ o - e .md")
    name = config["sender_name"] if name is None else name
    email = config["reply_to"] if email is None else email
    if (not isinstance(name, str) or not name.strip() or len(name.encode("utf-8")) > 200
            or re.search(r"[\x00-\x1f\x7f]", name)):
        raise ValueError("Nome mittente obbligatorio e valido, massimo 200 byte UTF-8")
    if not isinstance(email, str) or (email and not email_address(email)):
        raise ValueError("Reply-To non valido")
    return {"name": name, "email": email, "filename": file.name, "markdown": text}, digest(raw)


def dry_run(root, file, name=None, email=None):
    config = load_config(root)
    args, sha = validated_document(file, config, name, email)
    return {"network_called": False, "email_delivery": "not_requested", "sha256": sha,
            "bytes": len(args["markdown"].encode("utf-8")), "filename": args["filename"],
            "recipient": config["recipient"], "smtp_from": config["smtp_from"],
            "send_enabled": config["send_enabled"], "smtp_password_configured": bool(config["smtp_password"])}


def probe(root):
    """Create a fixed synthetic draft locally. Never contacts any server."""
    target = plain_path(Path(root) / "artifacts/prova-smtp.md")
    raw = "# Prova TRTalks\n\nDocumento fittizio per verificare il formato.\n".encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        if target.read_bytes() != raw:
            raise ValueError("Il documento di prova esiste con altro contenuto; non sovrascritto")
    return {"verified": True, "network_called": False, "email_delivery": "not_requested",
            "draft_path": str(target), "sha256": digest(raw), "bytes": len(raw)}


def message_bytes(args, delivery_route, request_id, date):
    message = EmailMessage(policy=policy.SMTP)
    message["From"] = formataddr((args["name"], delivery_route["smtp_from"]))
    message["To"] = delivery_route["recipient"]
    if args["email"]:
        message["Reply-To"] = args["email"]
    message["Subject"] = "TRTalks — " + args["filename"]
    message["Date"] = date
    message["Message-ID"] = "<" + request_id + "@" + delivery_route["smtp_from"].split("@", 1)[1] + ">"
    message["X-TRTalks-Request-ID"] = request_id
    message.set_content("Resoconto TRTalks preparato da " + args["name"] + ".\n"
                        "Il documento Markdown completo è allegato.\n")
    # Base64 attachment retains the exact authorized UTF-8 bytes, including CRLF.
    message.add_attachment(args["markdown"].encode("utf-8"), maintype="text", subtype="markdown",
                           filename=args["filename"], cte="base64")
    message.set_boundary("trtalks-" + request_id)
    return message.as_bytes()


def transmit(root, record_path, record, config, transport=None):
    record["status"] = "pending"
    record["last_attempt_at"] = now()
    atomic_json(record_path, record)  # Crash from here onward requires review, never a new ID.
    outcome = {"request_id": record["request_id"], "message_id": record["message_id"],
               "smtp_accepted": None, "email_delivery": "unconfirmed", "cached": False,
               "recipient": record["route"]["recipient"]}
    try:
        raw = base64.b64decode(record["message_base64"], validate=True)
        envelope = {"from": record["route"]["smtp_from"], "to": record["route"]["recipient"]}
        receipt = (transport or smtp_transport)(config, envelope, raw)
        if (receipt.get("smtp_accepted") is not True or receipt.get("smtp_code") != 250
                or receipt.get("recipient") != envelope["to"]):
            raise DeliveryError("Ricevuta SMTP inattesa", uncertain=True)
        record["status"] = "accepted"
        outcome.update(smtp_accepted=True, receipt=receipt)
    except DeliveryError as error:
        record["status"] = "uncertain" if error.uncertain else "failed_safe"
        outcome.update(smtp_accepted=None if error.uncertain else False,
                       error=str(error), smtp_code=error.code,
                       email_delivery="unconfirmed" if error.uncertain else "not_sent")
    except (OSError, ValueError, TypeError, KeyError):
        # Unexpected failures after entering a transport are ambiguous; no raw secrets in output.
        record["status"] = "uncertain"
        outcome["error"] = "Errore durante il tentativo SMTP; esito non determinato"
    record.setdefault("attempts", []).append({"at": now(), "outcome": outcome})
    record["outcome"] = outcome
    try:
        atomic_json(record_path, record)
    except OSError:
        return dict(outcome, local_status="pending", state_saved=False, state_file=str(record_path),
                    state_error="Ricevuta non salvata: conservare questo esito e verificare manualmente; nessun reinvio")
    return dict(outcome, local_status=record["status"], state_saved=True, state_file=str(record_path))


def send(root, file, approved_sha256, authorization, name=None, email=None, transport=None):
    root = Path(root).resolve()
    config = load_config(root)
    if not config["send_enabled"]:
        raise ValueError("Invio disabilitato nella configurazione locale")
    args, sha = validated_document(file, config, name, email)
    if approved_sha256 != sha or not authorization or not authorization.strip():
        raise ValueError("Manca l'autorizzazione esplicita o la bozza differisce dalla versione autorizzata")
    with locked(root / ".trtalks/delivery.lock"):
        directory = plain_path(root / ".trtalks/deliveries")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        delivery_route = route(config)
        fingerprint = digest(canonical({"route": delivery_route, "arguments": args}))
        for path in directory.glob("trtalks-*.json"):
            record = json.loads(plain_path(path).read_text(encoding="utf-8"))
            if record["document_sha256"] != sha:
                continue
            if record.get("transport") != "smtp":
                raise ValueError("Documento già registrato nel precedente flusso HTTP: revisione manuale, nessun reinvio SMTP")
            if record["fingerprint"] != fingerprint:
                raise ValueError("Documento già registrato con altri metadati o destinatario: verificare prima di un altro invio")
            if record["status"] == "accepted":
                return dict(record["outcome"], cached=True, local_status="accepted", state_file=str(path))
            raise ValueError("Tentativo già registrato: usare retry con lo stesso request_id " + record["request_id"])
        request_id = "trtalks-" + uuid.uuid4().hex
        date = formatdate(localtime=True)
        raw = message_bytes(args, delivery_route, request_id, date)
        record = {"schema": 2, "transport": "smtp", "created_at": now(), "request_id": request_id,
                  "route": delivery_route, "document_sha256": sha, "fingerprint": fingerprint,
                  "authorization": authorization, "draft_path": str(Path(file).resolve()),
                  "arguments": args, "date": date, "message_id": "<" + request_id + "@" + delivery_route["smtp_from"].split("@", 1)[1] + ">",
                  "message_base64": base64.b64encode(raw).decode("ascii"), "message_sha256": digest(raw),
                  "status": "prepared", "attempts": []}
        path = directory / (request_id + ".json")
        atomic_json(path, record)
        return transmit(root, path, record, config, transport)


def retry(root, request_id, transport=None):
    if not re.fullmatch(r"trtalks-[a-f0-9]{32}", request_id):
        raise ValueError("request_id non valido")
    root = Path(root).resolve()
    config = load_config(root)
    if not config["send_enabled"]:
        raise ValueError("Invio disabilitato")
    with locked(root / ".trtalks/delivery.lock"):
        path = plain_path(root / ".trtalks/deliveries" / (request_id + ".json"))
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("transport") != "smtp":
            raise ValueError("Tentativo del precedente flusso HTTP: revisione manuale, nessun reinvio SMTP")
        if record["status"] == "accepted":
            return dict(record["outcome"], cached=True, local_status="accepted", state_file=str(path))
        if record["status"] != "failed_safe":
            raise ValueError("Esito incerto o tentativo interrotto: SMTP non deduplica; reinvio bloccato, verificare manualmente")
        if route(config) != record["route"]:
            raise ValueError("Server, account, mittente o destinatario cambiati: ritentativo bloccato")
        args = record["arguments"]
        raw = base64.b64decode(record["message_base64"], validate=True)
        if (record["request_id"] != request_id or not record.get("authorization")
                or digest(args["markdown"].encode("utf-8")) != record["document_sha256"]
                or digest(canonical({"route": record["route"], "arguments": args})) != record["fingerprint"]
                or digest(raw) != record["message_sha256"]
                or raw != message_bytes(args, record["route"], request_id, record["date"])):
            raise ValueError("Stato del tentativo modificato: nessun reinvio")
        return transmit(root, path, record, config, transport)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("probe")
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
        elif args.command == "probe":
            result = probe(args.root)
        elif args.command == "dry-run":
            result = dry_run(args.root, args.file, args.name, args.email)
        elif args.command == "send":
            result = send(args.root, args.file, args.approved_sha256, args.authorization, args.name, args.email)
        else:
            result = retry(args.root, args.request_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        success = result.get("smtp_accepted", result.get("verified", result.get("network_called") is False))
        return 0 if success and result.get("state_saved", True) else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        delivery = "unconfirmed" if args.command in ("send", "retry") else "not_requested"
        print(json.dumps({"ok": False, "error": str(error), "email_delivery": delivery}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
