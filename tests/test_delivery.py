"""Local contract tests. Synthetic fixtures do not prove remote connectivity."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "runtime/delivery.py"
spec = importlib.util.spec_from_file_location("delivery", SCRIPT)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class ProbeTests(unittest.TestCase):
    def receipt(self, payload=None, **changes):
        value = dict(ok=True, service=delivery.SERVICE, email_sent=False, stored=False,
                     status="ready" if payload is None else "received")
        if payload is not None:
            value.update(payload, bytes=len(payload["markdown"].encode("utf-8")),
                         sha256=hashlib.sha256(payload["markdown"].encode("utf-8")).hexdigest())
        value.update(changes)
        return dict(http_status=200, content_type="application/json", body_truncated=False,
                    body=json.dumps(value))

    def test_utf8_verified_and_corruption_rejected(self):
        payload = {"request_id": "probe-" + "a" * 32, "markdown": delivery.MARKDOWN}
        self.assertEqual(delivery.verify(self.receipt(payload), payload)["markdown"], delivery.MARKDOWN)
        for changes in ({"sha256": "0" * 64}, {"bytes": 1}, {"markdown": "changed"},
                        {"request_id": "other"}, {"bytes": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                delivery.verify(self.receipt(payload, **changes), payload)

    def test_not_ready_or_email_capable_service_rejected(self):
        for changes in ({"email_sent": True}, {"stored": True}, {"service": "other"},
                        {"ok": False}, {"status": "accepted"}, {"email_sent": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                delivery.verify(self.receipt(**changes))

    def test_http_and_non_json_errors_are_not_success(self):
        for changes in ({"http_status": 302}, {"http_status": 500}, {"body_truncated": True},
                        {"content_type": "text/html"}, {"body": "<html>failure</html>"}):
            exchange = self.receipt()
            exchange.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                delivery.verify(exchange)

    def test_same_saved_request_and_draft_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            first = delivery.prepare(Path(temp))
            self.assertEqual(first, delivery.prepare(Path(temp)))
            self.assertEqual(first[0].read_bytes(), delivery.MARKDOWN.encode("utf-8"))

    def test_existing_interview_never_overwritten_or_sent_as_probe(self):
        with tempfile.TemporaryDirectory() as temp:
            draft = Path(temp) / "prova-http.md"
            draft.write_text("Risposte riservate", encoding="utf-8")
            with self.assertRaises(ValueError):
                delivery.prepare(Path(temp))
            self.assertEqual(draft.read_text(encoding="utf-8"), "Risposte riservate")
            self.assertFalse((Path(temp) / "probe-request.json").exists())

    def test_saved_request_cannot_be_repurposed(self):
        with tempfile.TemporaryDirectory() as temp:
            delivery.prepare(Path(temp))
            state = Path(temp) / "probe-request.json"
            payload = json.loads(state.read_text())
            payload["markdown"] = "intervista reale"
            state.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                delivery.prepare(Path(temp))


if __name__ == "__main__":
    unittest.main()
