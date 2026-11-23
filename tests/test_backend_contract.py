"""Optional real PHP contract tests over CLI, with mail() disabled.

Set TRTALKS_BACKEND_SOURCE to the actual backend source. No HTTP server, remote
request or email is used. php://input alone is adapted to stdin in memory.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from common import DEFAULT_CONFIG, atomic_json, canonical, digest
import send_document as sender

HARNESS = r"""
$_SERVER = json_decode($argv[2], true, 16, JSON_THROW_ON_ERROR);
$source = file_get_contents($argv[1]);
if (substr_count($source, "'php://input'") !== 1) { throw new RuntimeException('Review input adapter'); }
$source = str_replace("'php://input'", "'php://stdin'", $source);
ob_start();
register_shutdown_function(static function () {
    $body = ob_get_clean();
    echo json_encode(['http_status' => http_response_code() ?: 200, 'body' => $body,
                     'content_type' => 'application/json', 'body_truncated' => false]);
});
eval(substr($source, 5));
"""


class BackendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = os.environ.get("TRTALKS_BACKEND_SOURCE")
        if not source or not shutil.which("php"):
            raise unittest.SkipTest("Set TRTALKS_BACKEND_SOURCE and install PHP for the local backend contract test")
        cls.source = Path(source).resolve(strict=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="trtalks-php-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.web = self.root / "public_html"
        self.web.mkdir()
        self.server_state = self.root / "server-state"
        self.server_state.mkdir()
        self.config = self.root / "server-config.php"
        self.config.write_text("<?php return ['state_dir' => __DIR__ . '/server-state'];\n")
        atomic_json(self.root / ".trtalks/config.local.json", dict(DEFAULT_CONFIG, sender_name="Prova", send_enabled=True))
        self.file = self.root / "intervista-fittizia.md"
        self.file.write_text("# Fittizio\n\nCaffè e città, 🚲.\n", encoding="utf-8")

    def php_transport(self, endpoint, payload):
        env = dict(os.environ, TRCONNECTOR_CONFIG_PATH=str(self.config))
        server = dict(REQUEST_METHOD="POST", CONTENT_TYPE="application/json", DOCUMENT_ROOT=str(self.web))
        completed = subprocess.run(["php", "-n", "-d", "disable_functions=mail", "-d",
            "sendmail_path=/usr/bin/false", "-r", HARNESS, str(self.source), json.dumps(server)],
            input=canonical(payload).decode("utf-8"), text=True, capture_output=True, env=env, timeout=5)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_real_backend_status_does_not_send(self):
        result = sender.status(self.root, self.php_transport)
        self.assertFalse(result["verified"])  # mail() is intentionally disabled.
        self.assertIs(result["receipt"]["email_sent"], False)
        self.assertEqual(list(self.server_state.iterdir()), [])

    def test_real_backend_pending_attempt_requires_review_without_email(self):
        first = sender.send(self.root, self.file, digest(self.file.read_bytes()), "Autorizzazione del test locale",
                            transport=self.php_transport)
        self.assertIsNone(first["backend_accepted"])
        self.assertEqual(first["local_status"], "uncertain")
        # The PHP writes pending, then fails because mail() cannot be called.
        second = sender.retry(self.root, first["request_id"], self.php_transport)
        self.assertEqual(second["local_status"], "review_required")
        self.assertEqual(second["receipt"]["submission"]["error"], "previous_attempt_requires_review")

    def test_real_backend_seeded_duplicate_is_parsed_without_mail(self):
        def transport(endpoint, payload):
            args = payload["params"]["arguments"]
            # Explicit local fixture: accepted state is seeded, not an actual delivery.
            encoded = json.dumps([args["name"], args["email"], args["filename"], args["markdown"]],
                                 ensure_ascii=True, separators=(",", ":")).replace("/", "\\/")
            key = hashlib.sha256(args["request_id"].encode()).hexdigest()
            atomic_json(self.server_state / (key + ".json"), {
                "digest": hashlib.sha256(encoded.encode()).hexdigest(), "status": "accepted",
                "updated_at": "2026-11-23T00:00:00Z"})
            return self.php_transport(endpoint, payload)
        result = sender.send(self.root, self.file, digest(self.file.read_bytes()), "Test con stato locale precompilato", transport=transport)
        self.assertIs(result["backend_accepted"], True)
        self.assertIs(result["receipt"]["submission"]["duplicate"], True)
        self.assertEqual(result["email_delivery"], "unconfirmed")


if __name__ == "__main__":
    unittest.main()
