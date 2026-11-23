"""SMTP protocol boundary tests. All SMTP clients here are local test doubles."""
from pathlib import Path
import smtplib
import ssl
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from common import DEFAULT_CONFIG
from delivery import DeliveryError, smtp_transport


class SMTPTransportTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(DEFAULT_CONFIG, smtp_password="synthetic-test-password")
        self.client = MagicMock()
        self.client.noop.return_value = (250, b"ok")
        self.client.mail.return_value = (250, b"ok")
        self.client.rcpt.return_value = (250, b"ok")
        self.client.data.return_value = (250, b"queued")
        self.envelope = {"from": self.config["smtp_from"], "to": self.config["recipient"]}
        self.patcher = patch("delivery.smtplib.SMTP_SSL", return_value=self.client)
        self.connect = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_tls_validation_and_status_never_send(self):
        result = smtp_transport(self.config)
        self.assertTrue(result["authenticated"])
        self.assertFalse(result["email_sent"])
        self.assertEqual(self.connect.call_args.args, ("mail.techreloaded.it", 465))
        context = self.connect.call_args.kwargs["context"]
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.client.login.assert_called_once_with("trtalks@techreloaded.it", "synthetic-test-password")
        self.client.mail.assert_not_called()
        self.client.data.assert_not_called()

    def test_actual_data_reply_is_required_and_quit_failure_does_not_undo_acceptance(self):
        self.client.quit.side_effect = smtplib.SMTPServerDisconnected()
        result = smtp_transport(self.config, self.envelope, b"message\r\n")
        self.assertEqual(result["smtp_code"], 250)
        self.assertTrue(result["smtp_accepted"])
        self.client.data.assert_called_once_with(b"message\r\n")

    def test_auth_rejection_does_not_copy_server_text_or_password(self):
        self.client.login.side_effect = smtplib.SMTPAuthenticationError(535, b"synthetic-test-password echoed")
        with self.assertRaises(DeliveryError) as caught:
            smtp_transport(self.config, self.envelope, b"message")
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(caught.exception.code, 535)
        self.assertNotIn(self.config["smtp_password"], str(caught.exception))
        self.client.mail.assert_not_called()

    def test_rcpt_rejection_never_enters_data(self):
        self.client.rcpt.return_value = (550, b"no")
        with self.assertRaises(DeliveryError) as caught:
            smtp_transport(self.config, self.envelope, b"message")
        self.assertFalse(caught.exception.uncertain)
        self.client.data.assert_not_called()

    def test_disconnect_before_and_during_data_have_distinct_outcomes(self):
        self.client.mail.side_effect = smtplib.SMTPServerDisconnected()
        with self.assertRaises(DeliveryError) as caught:
            smtp_transport(self.config, self.envelope, b"message")
        self.assertFalse(caught.exception.uncertain)
        self.client.mail.side_effect = None
        self.client.data.side_effect = smtplib.SMTPServerDisconnected()
        with self.assertRaises(DeliveryError) as caught:
            smtp_transport(self.config, self.envelope, b"message")
        self.assertTrue(caught.exception.uncertain)

    def test_explicit_data_rejection_is_safe_to_retry(self):
        self.client.data.return_value = (451, b"no queue")
        with self.assertRaises(DeliveryError) as caught:
            smtp_transport(self.config, self.envelope, b"message")
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(caught.exception.code, 451)

    def test_missing_password_prevents_connection(self):
        with self.assertRaises(DeliveryError):
            smtp_transport(dict(self.config, smtp_password=""))
        self.connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
