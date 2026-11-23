"""Local credential configuration, redaction and backwards-compatible settings."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from common import DEFAULT_CONFIG, atomic_json, load_config
import trtalks


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="trtalks-config-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / ".trtalks/config.local.json"

    def test_prompted_password_is_saved_privately_and_not_printed(self):
        output = io.StringIO()
        with patch.object(sys.stdin, "isatty", return_value=True), patch("trtalks.getpass.getpass", return_value="synthetic-config-secret"), redirect_stdout(output):
            code = trtalks.main(["--root", str(self.root), "configure", "--name", "Prova", "--smtp-password", "--enable-send"])
        self.assertEqual(code, 0, output.getvalue())
        config = load_config(self.root)
        self.assertEqual(config["smtp_password"], "synthetic-config-secret")
        self.assertTrue(config["send_enabled"])
        self.assertEqual(config["smtp_username"], "trtalks@techreloaded.it")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("synthetic-config-secret", output.getvalue())
        self.assertTrue(json.loads(output.getvalue())["smtp_password_configured"])

    def test_legacy_config_and_unknown_keys_preserved(self):
        original = {"schema": 1, "endpoint": "https://old.example.test/mcp", "recipient": "info@techreloaded.it",
                    "sender_name": "Prova", "custom_setting": "keep", "send_enabled": False}
        atomic_json(self.path, original)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(trtalks.main(["--root", str(self.root), "configure", "--recipient", "giovannipuliti@gmail.com"]), 0)
        current = load_config(self.root)
        self.assertEqual(current["endpoint"], original["endpoint"])
        self.assertEqual(current["custom_setting"], "keep")
        self.assertEqual(current["transport"], "smtp")

    def test_invalid_change_does_not_overwrite_credentials(self):
        atomic_json(self.path, dict(DEFAULT_CONFIG, smtp_password="synthetic-local-secret"))
        before = self.path.read_bytes()
        for args in (["--recipient", "bad\r\nBcc: person@example.test"], ["--smtp-port", "0"], ["--name", "bad\nheader"]):
            with redirect_stdout(io.StringIO()):
                code = trtalks.main(["--root", str(self.root), "configure", *args])
            self.assertEqual(code, 1)
            self.assertEqual(self.path.read_bytes(), before)

    def test_no_terminal_or_no_echo_prevents_password_storage(self):
        with patch.object(sys.stdin, "isatty", return_value=False), redirect_stdout(io.StringIO()):
            code = trtalks.main(["--root", str(self.root), "configure", "--smtp-password"])
        self.assertEqual(code, 1)
        self.assertFalse(self.path.exists())
        import warnings
        def no_echo(*args):
            warnings.warn("No echo control", trtalks.getpass.GetPassWarning)
        with patch.object(sys.stdin, "isatty", return_value=True), patch("trtalks.getpass.getpass", side_effect=no_echo), redirect_stdout(io.StringIO()):
            code = trtalks.main(["--root", str(self.root), "configure", "--smtp-password"])
        self.assertEqual(code, 1)
        self.assertFalse(self.path.exists())

    def test_readable_password_file_is_rejected(self):
        atomic_json(self.path, dict(DEFAULT_CONFIG, smtp_password="synthetic-local-secret"))
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "permessi 600"):
            load_config(self.root)

    def run_init(self, answers, password="synthetic-init-secret"):
        output = io.StringIO()
        with patch.object(sys.stdin, "isatty", return_value=True), patch("builtins.input", side_effect=answers), patch("trtalks.getpass.getpass", return_value=password), redirect_stdout(output):
            code = trtalks.main(["--root", str(self.root), "init"])
        return code, output.getvalue()

    def test_init_defaults_create_ready_private_config_without_network(self):
        # Same placeholder config that the installer creates on first installation.
        atomic_json(self.path, DEFAULT_CONFIG)
        with patch("delivery.smtplib.SMTP_SSL") as smtp:
            code, output = self.run_init([""] * 8)
        self.assertEqual(code, 0, output)
        config = load_config(self.root)
        self.assertEqual(config["smtp_from"], "trtalks@techreloaded.it")
        self.assertEqual(config["recipient"], "trtalks@techreloaded.it")
        self.assertEqual(config["sender_name"], "TRTalks")
        self.assertEqual(config["smtp_host"], "mail.techreloaded.it")
        self.assertEqual(config["smtp_port"], 465)
        self.assertTrue(config["send_enabled"])
        self.assertEqual(config["smtp_password"], "synthetic-init-secret")
        self.assertNotIn("synthetic-init-secret", output)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        smtp.assert_not_called()

    def test_init_keeps_existing_password_and_unknown_settings(self):
        original = dict(DEFAULT_CONFIG, recipient="info@techreloaded.it", sender_name="Prova",
                        smtp_password="synthetic-retained-secret", custom_local="keep")
        atomic_json(self.path, original)
        code, output = self.run_init([""] * 8, password="")
        self.assertEqual(code, 0, output)
        self.assertEqual(load_config(self.root), original)
        self.assertNotIn("synthetic-retained-secret", output)

    def test_init_validates_and_reprompts_invalid_settings(self):
        answers = ["bad-address", "sender@example.test", "to@example.test", "Nome Prova",
                   "smtp.example.test", "not-a-port", "0", "465", "login@example.test", "", "no"]
        code, output = self.run_init(answers)
        self.assertEqual(code, 0, output)
        config = load_config(self.root)
        self.assertEqual(config["smtp_from"], "sender@example.test")
        self.assertEqual(config["recipient"], "to@example.test")
        self.assertFalse(config["send_enabled"])

    def test_init_abort_keeps_existing_file_untouched(self):
        atomic_json(self.path, dict(DEFAULT_CONFIG, smtp_password="synthetic-retained-secret"))
        before = self.path.read_bytes()
        code, output = self.run_init(["", KeyboardInterrupt()])
        self.assertEqual(code, 1)
        self.assertIn("annullata", output)
        self.assertEqual(self.path.read_bytes(), before)

    def test_init_requires_password_when_account_changes_and_can_clear_reply_to(self):
        atomic_json(self.path, dict(DEFAULT_CONFIG, smtp_password="synthetic-old-secret", reply_to="old@example.test"))
        with patch.object(sys.stdin, "isatty", return_value=True), patch("builtins.input", side_effect=["new@example.test", "", "", "", "", "", "-", "s"]), patch("trtalks.getpass.getpass", side_effect=["", "synthetic-new-secret"]) as prompt, redirect_stdout(io.StringIO()):
            code = trtalks.main(["--root", str(self.root), "init"])
        self.assertEqual(code, 0)
        config = load_config(self.root)
        self.assertEqual(config["smtp_username"], "new@example.test")
        self.assertEqual(config["smtp_password"], "synthetic-new-secret")
        self.assertEqual(config["reply_to"], "")
        self.assertEqual(prompt.call_count, 2)


if __name__ == "__main__":
    unittest.main()
