"""Client behavior against explicit synthetic responses; never sends email."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "runtime"
sys.path.insert(0, str(SCRIPTS))
from common import DEFAULT_CONFIG, atomic_json, digest, locked
import send_document as sender


def response(payload, submission=None, failed=False, status=202):
    submission = submission or {"ok": True, "status": "accepted", "request_id": payload["id"],
                                "recipient": "info@techreloaded.it"}
    body = {"jsonrpc": "2.0", "id": payload["id"], "result": {"isError": failed,
            "content": [{"type": "text", "text": json.dumps({"http_status": status, "submission": submission})}]}}
    return {"http_status": 200, "content_type": "application/json", "body_truncated": False,
            "body": json.dumps(body)}


class SendTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="trtalks-send-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        atomic_json(self.root / ".trtalks/config.local.json", dict(DEFAULT_CONFIG, sender_name="Prova", send_enabled=True))
        self.file = self.root / "intervista-prova.md"
        self.raw = b'# Fittizio\r\n\r\nRisposta di prova.\r\n'
        self.file.write_bytes(self.raw)
        self.sha = digest(self.raw)
        self.calls = []

    def transport(self, endpoint, payload):
        self.calls.append((endpoint, json.loads(json.dumps(payload))))
        return response(payload)

    def send(self, **kwargs):
        return sender.send(self.root, self.file, self.sha, "Autorizzo questa prova sintetica", transport=self.transport, **kwargs)

    def state(self):
        path = next((self.root / ".trtalks/deliveries").glob("*.json"))
        return path, json.loads(path.read_text())

    def test_acceptance_does_not_claim_email_delivered(self):
        result = self.send()
        self.assertTrue(result["backend_accepted"])
        self.assertEqual(result["email_delivery"], "unconfirmed")
        self.assertEqual(self.calls[0][1]["params"]["arguments"]["markdown"].encode(), self.raw)
        self.assertEqual(self.file.read_bytes(), self.raw)
        self.assertEqual(self.calls[0][1]["method"], "tools/call")
        self.assertEqual(self.calls[0][1]["params"]["name"], "send-document")

    def test_accepted_document_is_not_resent(self):
        first = self.send()
        second = self.send()
        self.assertEqual(first["request_id"], second["request_id"])
        self.assertTrue(second["cached"])
        self.assertEqual(len(self.calls), 1)
        sender.retry(self.root, first["request_id"], self.transport)
        self.assertEqual(len(self.calls), 1)

    def test_changed_metadata_does_not_create_second_id(self):
        self.send()
        with self.assertRaises(ValueError):
            self.send(name="Nome cambiato")
        self.assertEqual(len(self.calls), 1)

    def test_hash_change_and_missing_authorization_prevent_network(self):
        for sha, approval in (("0" * 64, "sì"), (self.sha, "")):
            with self.assertRaises(ValueError):
                sender.send(self.root, self.file, sha, approval, transport=self.transport)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / ".trtalks/deliveries").exists())

    def test_disabled_and_dry_run_never_send(self):
        atomic_json(self.root / ".trtalks/config.local.json", dict(DEFAULT_CONFIG, sender_name="Prova"))
        with self.assertRaises(ValueError):
            self.send()
        result = sender.dry_run(self.root, self.file)
        self.assertFalse(result["network_called"])
        self.assertEqual(self.calls, [])

    def test_timeout_persists_payload_and_retry_uses_same_id(self):
        captured = []
        def timeout(endpoint, payload):
            captured.append(json.loads(json.dumps(payload)))
            raise TimeoutError("synthetic test timeout")
        result = sender.send(self.root, self.file, self.sha, "sì", transport=timeout)
        self.assertEqual(result["local_status"], "uncertain")
        with self.assertRaises(ValueError):
            self.send()
        self.file.write_bytes(b"Bozza modificata dopo il tentativo")
        sender.retry(self.root, result["request_id"], self.transport)
        self.assertEqual(self.calls[0][1], captured[0])
        self.assertEqual(self.file.read_bytes(), b"Bozza modificata dopo il tentativo")

    def test_review_required_stops_further_retry(self):
        def review(endpoint, payload):
            return response(payload, {"ok": False, "error": "previous_attempt_requires_review", "request_id": payload["id"]}, True, 409)
        result = sender.send(self.root, self.file, self.sha, "sì", transport=review)
        self.assertEqual(result["local_status"], "review_required")
        with self.assertRaises(ValueError):
            sender.retry(self.root, result["request_id"], self.transport)
        self.assertEqual(self.calls, [])

    def test_outer_http_200_and_rpc_errors_are_not_acceptance(self):
        def error(endpoint, payload):
            return dict(http_status=200, content_type="application/json", body_truncated=False,
                        body=json.dumps({"jsonrpc": "2.0", "id": payload["id"], "error": {"code": -32603, "message": "test"}}))
        result = sender.send(self.root, self.file, self.sha, "sì", transport=error)
        self.assertFalse(result["backend_accepted"])
        self.assertEqual(result["local_status"], "uncertain")

    def test_old_or_tampered_retry_blocked(self):
        def timeout(endpoint, payload):
            raise TimeoutError("test")
        result = sender.send(self.root, self.file, self.sha, "sì", transport=timeout)
        path, record = self.state()
        record["payload"]["params"]["arguments"]["name"] = "Changed"
        atomic_json(path, record)
        with self.assertRaises(ValueError):
            sender.retry(self.root, result["request_id"], self.transport)
        record["created_at"] = (datetime.now(timezone.utc) - timedelta(days=151)).isoformat()
        atomic_json(path, record)
        with self.assertRaises(ValueError):
            sender.retry(self.root, result["request_id"], self.transport)
        self.assertEqual(self.calls, [])

    def test_lock_prevents_parallel_delivery(self):
        with locked(self.root / ".trtalks/delivery.lock"):
            with self.assertRaises(ValueError):
                self.send()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
