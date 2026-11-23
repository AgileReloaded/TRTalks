"""SMTP delivery state tests with explicit local transports; never sends email."""
from contextlib import redirect_stdout
from email import policy
from email.parser import BytesParser
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from common import DEFAULT_CONFIG, atomic_json, digest, locked
from delivery import DeliveryError
import send_document as sender


class SendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="trtalks-smtp-state-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = dict(DEFAULT_CONFIG, sender_name="Nome di prova", smtp_password="synthetic-local-secret", send_enabled=True)
        atomic_json(self.root / ".trtalks/config.local.json", self.config)
        self.file = self.root / "intervista-prova.md"
        self.raw = '# Fittizio\r\n\r\nCaffè e città, 🚲.\r\n'.encode()
        self.file.write_bytes(self.raw)
        self.sha = digest(self.raw)
        self.calls = []

    def transport(self, config, envelope=None, message=None):
        self.calls.append((dict(envelope) if envelope else None, message))
        if message is None:
            return {"authenticated": True, "smtp_code": 250, "email_sent": False}
        return {"smtp_accepted": True, "smtp_code": 250, "recipient": envelope["to"]}

    def send(self, **kwargs):
        return sender.send(self.root, self.file, self.sha, "Autorizzo il documento fittizio", transport=self.transport, **kwargs)

    def state(self):
        path = next((self.root / ".trtalks/deliveries").glob("trtalks-*.json"))
        return path, json.loads(path.read_text())

    def test_exact_attachment_and_acceptance_does_not_claim_delivery(self):
        result = self.send()
        self.assertTrue(result["smtp_accepted"])
        self.assertEqual(result["email_delivery"], "unconfirmed")
        envelope, raw = self.calls[0]
        self.assertEqual(envelope, {"from": "trtalks@techreloaded.it", "to": "trtalks@techreloaded.it"})
        message = BytesParser(policy=policy.default).parsebytes(raw)
        attachment = next(message.iter_attachments())
        self.assertEqual(attachment.get_payload(decode=True), self.raw)
        self.assertEqual(attachment.get_filename(), self.file.name)
        self.assertEqual(message["Message-ID"], result["message_id"])
        self.assertEqual(self.file.read_bytes(), self.raw)
        path, record = self.state()
        self.assertNotIn(self.config["smtp_password"], path.read_text())
        self.assertNotIn("smtp_password", path.read_text())
        self.assertEqual(base64.b64decode(record["message_base64"]), raw)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_accepted_document_and_retry_use_cached_receipt(self):
        first = self.send()
        second = self.send()
        self.assertEqual(first["request_id"], second["request_id"])
        self.assertTrue(second["cached"])
        self.assertTrue(sender.retry(self.root, first["request_id"], self.transport)["cached"])
        self.assertEqual(len(self.calls), 1)

    def test_changed_metadata_or_recipient_blocks_second_id(self):
        self.send()
        with self.assertRaises(ValueError):
            self.send(name="Altro nome")
        atomic_json(self.root / ".trtalks/config.local.json", dict(self.config, recipient="info@techreloaded.it"))
        with self.assertRaises(ValueError):
            self.send()
        self.assertEqual(len(self.calls), 1)

    def test_authorization_hash_and_disabled_prevent_network(self):
        for sha, approval in (("0" * 64, "sì"), (self.sha, "")):
            with self.assertRaises(ValueError):
                sender.send(self.root, self.file, sha, approval, transport=self.transport)
        self.assertFalse((self.root / ".trtalks/deliveries").exists())
        atomic_json(self.root / ".trtalks/config.local.json", dict(self.config, send_enabled=False))
        with self.assertRaises(ValueError):
            self.send()
        self.assertFalse(sender.dry_run(self.root, self.file)["network_called"])
        self.assertEqual(self.calls, [])

    def test_uncertain_and_crashed_pending_attempts_cannot_retry(self):
        def uncertain(*args):
            raise DeliveryError("Test disconnessione dopo DATA", uncertain=True)
        result = sender.send(self.root, self.file, self.sha, "sì", transport=uncertain)
        self.assertEqual(result["local_status"], "uncertain")
        self.assertIsNone(result["smtp_accepted"])
        with self.assertRaisesRegex(ValueError, "SMTP non deduplica"):
            sender.retry(self.root, result["request_id"], self.transport)
        with self.assertRaises(ValueError):
            self.send()
        path, record = self.state()
        record["status"] = "pending"
        atomic_json(path, record)
        with self.assertRaises(ValueError):
            sender.retry(self.root, result["request_id"], self.transport)
        self.assertEqual(self.calls, [])

    def test_safe_retry_uses_same_id_and_exact_message_after_password_change(self):
        captured = []
        def refused(config, envelope, raw):
            captured.append(raw)
            raise DeliveryError("Autenticazione rifiutata", code=535)
        first = sender.send(self.root, self.file, self.sha, "sì", transport=refused)
        self.assertEqual(first["local_status"], "failed_safe")
        self.assertEqual(first["email_delivery"], "not_sent")
        self.file.write_bytes(b"Bozza cambiata successivamente")
        atomic_json(self.root / ".trtalks/config.local.json", dict(self.config, smtp_password="rotated-local-secret"))
        result = sender.retry(self.root, first["request_id"], self.transport)
        self.assertEqual(first["request_id"], result["request_id"])
        self.assertEqual(captured[0], self.calls[0][1])
        self.assertEqual(self.file.read_bytes(), b"Bozza cambiata successivamente")

    def test_tampered_message_and_changed_route_block_retry(self):
        def refusal(*args):
            raise DeliveryError("Rifiuto sicuro", code=550)
        first = sender.send(self.root, self.file, self.sha, "sì", transport=refusal)
        path, record = self.state()
        record["message_base64"] = base64.b64encode(b"altered").decode()
        atomic_json(path, record)
        with self.assertRaises(ValueError):
            sender.retry(self.root, first["request_id"], self.transport)
        atomic_json(self.root / ".trtalks/config.local.json", dict(self.config, smtp_host="other.test"))
        with self.assertRaises(ValueError):
            sender.retry(self.root, first["request_id"], self.transport)
        self.assertEqual(self.calls, [])

    def test_legacy_http_records_never_convert_to_new_mail(self):
        request_id = "trtalks-" + "a" * 32
        atomic_json(self.root / ".trtalks/deliveries" / (request_id + ".json"),
                    {"schema": 1, "request_id": request_id, "document_sha256": self.sha, "status": "accepted"})
        with self.assertRaisesRegex(ValueError, "precedente flusso HTTP"):
            self.send()
        with self.assertRaises(ValueError):
            sender.retry(self.root, request_id, self.transport)
        self.assertEqual(self.calls, [])

    def test_status_is_authenticated_noop_and_no_document(self):
        result = sender.status(self.root, self.transport)
        self.assertTrue(result["verified"])
        self.assertEqual(result["email_delivery"], "not_requested")
        self.assertEqual(self.calls, [(None, None)])
        self.assertNotIn(self.config["smtp_password"], json.dumps(result))
        self.assertFalse((self.root / ".trtalks/deliveries").exists())

    def test_probe_preserves_existing_documents_and_never_uses_transport(self):
        result = sender.probe(self.root)
        self.assertFalse(result["network_called"])
        path = Path(result["draft_path"])
        self.assertEqual(digest(path.read_bytes()), result["sha256"])
        self.assertEqual(result, sender.probe(self.root))
        path.write_text("Documento personale")
        with self.assertRaises(ValueError):
            sender.probe(self.root)
        self.assertEqual(path.read_text(), "Documento personale")
        self.assertEqual(self.calls, [])

    def test_lock_and_unsaved_state_prevent_transport(self):
        with locked(self.root / ".trtalks/delivery.lock"):
            with self.assertRaises(ValueError):
                self.send()
        from unittest.mock import patch
        with patch("send_document.atomic_json", side_effect=OSError("Test disco pieno")):
            with self.assertRaises(OSError):
                self.send()
        self.assertEqual(self.calls, [])

    def test_config_error_does_not_imply_mail_attempt(self):
        (self.root / ".trtalks/config.local.json").write_text("invalid JSON")
        output = io.StringIO()
        with redirect_stdout(output):
            code = sender.main(["--root", str(self.root), "status"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["email_delivery"], "not_requested")

    def test_receipt_write_failure_retains_real_acceptance_and_blocks_resend(self):
        from unittest.mock import patch
        writes = []
        def write(path, value):
            writes.append(path)
            if len(writes) == 3:
                raise OSError("Test disco pieno dopo accettazione")
            atomic_json(path, value)
        with patch("send_document.atomic_json", side_effect=write):
            result = self.send()
        self.assertTrue(result["smtp_accepted"])
        self.assertFalse(result["state_saved"])
        self.assertEqual(result["local_status"], "pending")
        with self.assertRaises(ValueError):
            sender.retry(self.root, result["request_id"], self.transport)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
