"""Verified TLS SMTP transport. Credentials never enter receipts or errors."""
import smtplib
import ssl


class DeliveryError(Exception):
    def __init__(self, message, uncertain=False, code=None):
        super().__init__(message)
        self.uncertain = uncertain
        self.code = code


def _close(client):
    if client is not None:
        # QUIT failures after DATA acceptance do not undo a successful submission.
        try:
            client.quit()
        except (OSError, smtplib.SMTPException):
            client.close()


def smtp_transport(config, envelope=None, message=None):
    """Login + NOOP if no message, otherwise one MAIL/RCPT/DATA, no retries."""
    if not config["smtp_password"]:
        raise DeliveryError("Password SMTP mancante: eseguire configure --smtp-password")
    client = None
    data_started = False
    try:
        client = smtplib.SMTP_SSL(config["smtp_host"], config["smtp_port"],
                                 timeout=30, context=ssl.create_default_context())
        client.login(config["smtp_username"], config["smtp_password"])
        if message is None:
            code, _ = client.noop()
            if code != 250:
                raise DeliveryError("Il server non ha confermato NOOP", code=code)
            return {"authenticated": True, "smtp_code": code, "email_sent": False}
        code, _ = client.mail(envelope["from"])
        if code != 250:
            raise DeliveryError("Mittente rifiutato dal server SMTP", code=code)
        code, _ = client.rcpt(envelope["to"])
        if code not in (250, 251):
            raise DeliveryError("Destinatario rifiutato dal server SMTP", code=code)
        # A disconnect during DATA has an ambiguous outcome. SMTP has no idempotency key.
        data_started = True
        code, _ = client.data(message)
        if code != 250:
            raise DeliveryError("Messaggio rifiutato dal server SMTP",
                                uncertain=not 400 <= code <= 599, code=code)
        return {"smtp_accepted": True, "smtp_code": code, "recipient": envelope["to"]}
    except smtplib.SMTPAuthenticationError as error:
        raise DeliveryError("Autenticazione SMTP rifiutata", code=error.smtp_code) from None
    except smtplib.SMTPDataError as error:
        raise DeliveryError("Messaggio rifiutato dal server SMTP",
                            uncertain=not 400 <= error.smtp_code <= 599,
                            code=error.smtp_code) from None
    except ssl.SSLCertVerificationError:
        raise DeliveryError("Certificato TLS del server SMTP non valido") from None
    except (OSError, smtplib.SMTPException):
        # Do not copy server replies: they may contain echoed authentication data.
        raise DeliveryError("Connessione SMTP fallita o interrotta",
                            uncertain=data_started) from None
    finally:
        try:
            _close(client)
        except (OSError, smtplib.SMTPException):
            pass
