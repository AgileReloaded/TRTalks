"""Real SMTP-over-TLS on loopback only, with an isolated certificate and mailbox sink."""
from email import policy
from email.parser import BytesParser
from pathlib import Path
import shutil
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from common import DEFAULT_CONFIG, atomic_json, digest
import send_document


class SMTPIntegrationTests(unittest.TestCase):
    def test_tls_login_status_and_frozen_attachment_without_external_email(self):
        if not shutil.which("openssl"):
            self.skipTest("openssl necessario per il certificato TLS locale di test")
        with tempfile.TemporaryDirectory(prefix="trtalks-tls-test-") as temp:
            root = Path(temp)
            cert, key = root / "cert.pem", root / "key.pem"
            result = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                                     "-keyout", str(key), "-out", str(cert), "-days", "1",
                                     "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1"],
                                    capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_context.load_cert_chain(str(cert), str(key))
            client_context = ssl.create_default_context(cafile=str(cert))
            received = []
            commands = []

            class Handler(socketserver.StreamRequestHandler):
                def reply(self, value):
                    self.wfile.write(value + b"\r\n")
                    self.wfile.flush()

                def handle(self):
                    self.connection.settimeout(5)
                    self.reply(b"220 localhost local test sink")
                    while True:
                        line = self.rfile.readline()
                        verb = line.split(b" ", 1)[0].strip().upper()
                        if not line:
                            return
                        commands.append(verb)  # Never retain AUTH arguments.
                        if verb == b"EHLO":
                            self.reply(b"250-localhost\r\n250 AUTH PLAIN")
                        elif verb == b"AUTH":
                            self.reply(b"235 Authentication successful (local fixture)")
                        elif verb in (b"NOOP", b"MAIL", b"RCPT"):
                            self.reply(b"250 OK")
                        elif verb == b"DATA":
                            self.reply(b"354 End with dot")
                            raw = bytearray()
                            while True:
                                part = self.rfile.readline()
                                if part == b".\r\n":
                                    break
                                if not part:
                                    return
                                raw.extend(part[1:] if part.startswith(b"..") else part)
                            received.append(bytes(raw))
                            self.reply(b"250 Stored only in local test memory")
                        elif verb == b"QUIT":
                            self.reply(b"221 Bye")
                            return
                        else:
                            self.reply(b"500 Unsupported local test command")

            class Server(socketserver.TCPServer):
                allow_reuse_address = True
                def get_request(self):
                    connection, address = super().get_request()
                    return server_context.wrap_socket(connection, server_side=True), address

            try:
                server = Server(("127.0.0.1", 0), Handler)
            except PermissionError:
                self.skipTest("L'ambiente non consente socket di loopback")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config = dict(DEFAULT_CONFIG, smtp_host="127.0.0.1", smtp_port=server.server_address[1],
                              smtp_password="synthetic-loopback-secret", sender_name="Prova locale", send_enabled=True)
                atomic_json(root / ".trtalks/config.local.json", config)
                draft = root / "prova-locale.md"
                raw = '# Prova fittizia\r\n\r\nCittà e caffè.\r\n'.encode()
                draft.write_bytes(raw)
                with patch("delivery.ssl.create_default_context", return_value=client_context):
                    status = send_document.status(root)
                    self.assertTrue(status["verified"], status)
                    self.assertEqual(received, [])
                    result = send_document.send(root, draft, digest(raw), "Test esclusivamente locale")
                    self.assertTrue(result["smtp_accepted"], result)
                    cached = send_document.send(root, draft, digest(raw), "Test esclusivamente locale")
                    self.assertTrue(cached["cached"])
                self.assertEqual(commands.count(b"DATA"), 1)
                self.assertEqual(len(received), 1)
                message = BytesParser(policy=policy.default).parsebytes(received[0])
                self.assertEqual(next(message.iter_attachments()).get_payload(decode=True), raw)
                self.assertEqual(message["Message-ID"], result["message_id"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
