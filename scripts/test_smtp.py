#!/usr/bin/env python3
"""Invia una sola email di prova; richiede Python 3.9 o successivo."""

import argparse
import getpass
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


HOST = "mail.techreloaded.it"
PORT = 465
SENDER = "trtalks@techreloaded.it"
RECIPIENT = "giovannipuliti@gmail.com"


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Invia una email di prova da trtalks@techreloaded.it a "
            "giovannipuliti@gmail.com via SMTP SSL sulla porta 465. "
            "Chiede la password senza mostrarla e non la salva. "
            "Ogni esecuzione invia un nuovo messaggio, senza ritentativi automatici."
        )
    )
    parser.parse_args()
    if not sys.stdin.isatty():
        print("Esegui lo script in un terminale interattivo per inserire la password.", file=sys.stderr)
        return 1

    print(f"Server: {HOST}:{PORT} (SSL/TLS con verifica del certificato)")
    print(f"Mittente: {SENDER}\nDestinatario: {RECIPIENT}")
    password = getpass.getpass(f"Password SMTP per {SENDER}: ")
    if not password:
        print("Password vuota: nessun invio.", file=sys.stderr)
        return 1

    message = EmailMessage()
    message["From"] = SENDER
    message["To"] = RECIPIENT
    message["Subject"] = "TRTalks — prova invio SMTP"
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="techreloaded.it")
    message.set_content(
        "Questa è una email di prova inviata dallo script locale TRTalks.\n"
        "Il messaggio contiene esclusivamente testo fittizio.\n"
    )

    client = None
    submission_started = False
    try:
        client = smtplib.SMTP_SSL(
            HOST, PORT, timeout=30, context=ssl.create_default_context()
        )
        client.login(SENDER, password)
        password = None
        submission_started = True
        client.send_message(message, from_addr=SENDER, to_addrs=[RECIPIENT])
    except smtplib.SMTPAuthenticationError:
        print("Autenticazione SMTP rifiutata: verifica utente e password. Nessun invio.", file=sys.stderr)
        return 1
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as exc:
        print(f"Messaggio rifiutato dal server SMTP: {exc}", file=sys.stderr)
        return 1
    except (OSError, smtplib.SMTPException) as exc:
        outcome = (
            "Esito dell'invio non determinato: verifica la casella prima di riprovare."
            if submission_started else "Messaggio non inviato."
        )
        print(f"Errore SMTP: {exc}\n{outcome}", file=sys.stderr)
        return 1
    finally:
        password = None
        if client is not None:
            client.close()

    print(f"Messaggio accettato dal server SMTP per {RECIPIENT}.")
    print(f"Message-ID: {message['Message-ID']}")
    print("La ricezione nella casella del destinatario non è ancora confermata.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nOperazione interrotta; non ripetere automaticamente un eventuale invio.", file=sys.stderr)
        sys.exit(130)
