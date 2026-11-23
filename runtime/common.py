"""Shared standard-library helpers for the macOS/Linux TRTalks runtime."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_CONFIG = {
    "schema": 1,
    "endpoint": "https://techreloaded.it/shared/php/trdocument-mcp.php",
    "recipient": "info@techreloaded.it",
    "sender_name": "",
    "reply_to": "",
    "send_enabled": False,
}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def https_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or parsed.query):
        raise ValueError("Serve un URL HTTPS senza credenziali, query o frammento")
    return url


def plain_path(path):
    path = Path(path)
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("Percorso simbolico non ammesso: " + str(item))
    return path


def atomic_json(path, value):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("File di stato simbolico: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(path):
    path = plain_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Un'altra operazione è in corso; nessun secondo invio avviato")
        yield
    finally:
        os.close(fd)


def load_config(root):
    path = plain_path(Path(root) / ".trtalks" / "config.local.json")
    value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(value, dict) or value.get("schema", 1) != 1:
        raise ValueError("Configurazione locale non valida")
    result = dict(DEFAULT_CONFIG, **value)
    https_url(result["endpoint"])
    if result["recipient"] != DEFAULT_CONFIG["recipient"]:
        raise ValueError("Il backend esistente invia soltanto a info@techreloaded.it")
    if type(result["send_enabled"]) is not bool:
        raise ValueError("send_enabled deve essere booleano")
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, payload=None, limit=65536):
    https_url(url)
    req = urllib.request.Request(url, data=None if payload is None else canonical(payload),
        method="GET" if payload is None else "POST", headers={
            "Accept": "application/json", "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "TRTalks/0.2"})
    try:
        response = urllib.request.build_opener(NoRedirect()).open(req, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(limit + 1)
        return {"http_status": response.code, "content_type": response.headers.get_content_type(),
                "body": raw[:limit].decode("utf-8", errors="replace"),
                "body_truncated": len(raw) > limit}


def response_json(exchange):
    if (exchange["http_status"] != 200 or exchange["content_type"] != "application/json"
            or exchange["body_truncated"]):
        raise ValueError("Risposta HTTP inattesa; vedere ricevuta, esito email non determinato")
    result = json.loads(exchange["body"])
    if not isinstance(result, dict):
        raise ValueError("Risposta JSON non valida")
    return result
