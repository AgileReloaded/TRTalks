#!/usr/bin/env python3
"""TRTalks command line entry point; works without third-party packages."""
import argparse
import getpass
import json
from pathlib import Path
import sys
import warnings

import manage
import send_document
from common import atomic_json, load_config, locked, plain_path, validate_config
from catalog import load_catalog

APPLICATION = Path(__file__).resolve().parent.parent


def ask_setting(config, key, label, default=None, optional=False):
    default = config[key] if default is None else default
    while True:
        hint = " (- per svuotare)" if optional else ""
        value = input(f"{label}{hint} [{default}]: ").strip()
        value = default if not value else ("" if optional and value == "-" else value)
        try:
            if key == "smtp_port":
                value = int(value)
            candidate = dict(config, **{key: value})
            validate_config(candidate)
            if key == "sender_name" and not value.strip():
                raise ValueError("Nome mittente obbligatorio")
        except (ValueError, TypeError):
            print("Valore non valido; riprovare.")
            continue
        config[key] = value
        return


def init(root):
    if not sys.stdin.isatty():
        raise ValueError("Eseguire trtalks init in un terminale interattivo")
    path = plain_path(root / ".trtalks/config.local.json")
    with locked(root / ".trtalks/manage.lock"):
        config = load_config(root)
        previous = dict(config)
        print("Configurazione TRTalks. Premi Invio per mantenere il valore tra parentesi.")
        print("La configurazione non invia email e non effettua connessioni di rete.")
        ask_setting(config, "smtp_from", "Indirizzo mittente")
        ask_setting(config, "recipient", "Destinatario")
        ask_setting(config, "sender_name", "Nome visualizzato del mittente",
                    default=config["sender_name"] or "TRTalks")
        ask_setting(config, "smtp_host", "Server SMTP (TLS implicito)")
        ask_setting(config, "smtp_port", "Porta SMTP")
        username_default = (config["smtp_from"] if previous["smtp_username"] == previous["smtp_from"]
                            else config["smtp_username"])
        ask_setting(config, "smtp_username", "Username SMTP", default=username_default)
        ask_setting(config, "reply_to", "Reply-To facoltativo", optional=True)
        retain_password = bool(config["smtp_password"]) and all(
            config[key] == previous[key] for key in ("smtp_host", "smtp_port", "smtp_username"))
        prompt = ("Password SMTP (Invio mantiene quella salvata): " if retain_password
                  else "Password SMTP: ")
        while True:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass(prompt)
            if password:
                config["smtp_password"] = password
                break
            if retain_password:
                break
            print("La password è obbligatoria; non viene mostrata né salvata nella cronologia.")
        while True:
            enabled_default = previous["send_enabled"] if previous["smtp_password"] else True
            choice = input("Abilitare gli invii autorizzati? [" + ("S/n" if enabled_default else "s/N") + "]: ").strip().lower()
            if choice in ("", "s", "si", "sì", "y", "yes", "n", "no"):
                config["send_enabled"] = enabled_default if not choice else choice not in ("n", "no")
                break
            print("Rispondere sì o no.")
        atomic_json(path, validate_config(config))
    print(f"Configurazione salvata in {path} (permessi 600).")
    print(f"Mittente: {config['smtp_from']} — Destinatario: {config['recipient']}")
    print("Invio " + ("abilitato" if config["send_enabled"] else "disabilitato")
          + ". Nessuna email inviata. Ogni documento richiede la propria autorizzazione alla consegna.")
    print("Per verificare il collegamento senza email: trtalks status")
    return 0


def version():
    manifest = APPLICATION / "release-manifest.json"
    if manifest.exists():
        return json.loads(manifest.read_text())["version"]
    return (APPLICATION / "VERSION").read_text().strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=version())
    parser.add_argument("--root", type=Path)
    parser.add_argument("command", choices=["init", "update", "uninstall", "configure", "status", "probe",
                                           "dry-run", "send", "retry", "skills", "paths"])
    args, remaining = parser.parse_known_args(argv)
    root = args.root or (APPLICATION.parent.parent if APPLICATION.parent.name == ".trtalks" else Path.cwd())
    root = root.expanduser().resolve()
    if args.command == "init":
        init_parser = argparse.ArgumentParser(prog="trtalks init",
            description="Configura SMTP con domande guidate e password nascosta, senza inviare email.")
        init_parser.parse_args(remaining)
        try:
            return init(root)
        except (EOFError, KeyboardInterrupt):
            print("\nConfigurazione annullata; impostazioni precedenti conservate.")
            return 1
        except (OSError, ValueError, TypeError, getpass.GetPassWarning) as error:
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
            return 1
    if args.command in ("skills", "paths"):
        if remaining:
            parser.error("Argomenti non riconosciuti: " + " ".join(remaining))
        app = root / ".trtalks/app"
        installed = app.exists()
        app = app if installed else APPLICATION
        catalog = load_catalog(app)
        if args.command == "skills":
            result = {"application": "TRTalks", "skills": [
                {"id": entry["id"], "display_name": entry["display_name"],
                 "description": entry["description"], "invoke": "$" + entry["id"]}
                for entry in catalog["skills"]]}
        else:
            result = {"root": str(root), "application": str(app), "runtime": str(app / "runtime"),
                      "shared_references": str(app / "runtime/references"),
                      "skills": {entry["id"]: str((root / ".agents/skills" if installed else app / "skills") / entry["id"])
                                 for entry in catalog["skills"]}}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command in ("update", "uninstall"):
        return manage.main([args.command, "--root", str(root), *remaining])
    if args.command in ("send", "retry", "dry-run", "status", "probe"):
        return send_document.main(["--root", str(root), args.command, *remaining])
    config_parser = argparse.ArgumentParser(prog="trtalks configure")
    config_parser.add_argument("--name")
    config_parser.add_argument("--email")
    config_parser.add_argument("--recipient")
    config_parser.add_argument("--smtp-host")
    config_parser.add_argument("--smtp-port", type=int)
    config_parser.add_argument("--smtp-username")
    config_parser.add_argument("--smtp-from")
    config_parser.add_argument("--smtp-password", action="store_true",
                               help="Chiede la password senza mostrarla e la salva nel file locale")
    enabled = config_parser.add_mutually_exclusive_group()
    enabled.add_argument("--enable-send", action="store_true")
    enabled.add_argument("--disable-send", action="store_true")
    values = config_parser.parse_args(remaining)
    try:
        with locked(root / ".trtalks/manage.lock"):
            path = plain_path(root / ".trtalks/config.local.json")
            # Preserve unknown local keys; validate before committing any change.
            config = load_config(root)
            if values.name is not None:
                config["sender_name"] = values.name
            if values.email is not None:
                config["reply_to"] = values.email
            for key in ("recipient", "smtp_host", "smtp_port", "smtp_username", "smtp_from"):
                value = getattr(values, key)
                if value is not None:
                    config[key] = value
            if values.smtp_password:
                if not sys.stdin.isatty():
                    raise ValueError("Inserire la password da un terminale interattivo")
                with warnings.catch_warnings():
                    warnings.simplefilter("error", getpass.GetPassWarning)
                    config["smtp_password"] = getpass.getpass("Password SMTP (salvata solo nel file locale): ")
                if not config["smtp_password"]:
                    raise ValueError("Password vuota: configurazione non modificata")
            if values.enable_send or values.disable_send:
                config["send_enabled"] = values.enable_send
            config = validate_config(config)
            atomic_json(path, config)
        print(json.dumps({"configured": True, "send_enabled": config["send_enabled"],
                          "transport": "smtp", "recipient": config["recipient"],
                          "smtp_password_configured": bool(config["smtp_password"]),
                          "config_file": str(path), "network_called": False}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, EOFError, getpass.GetPassWarning) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
