"""VoiceStudio (github.com/debpalash/VoiceStudio, AGPL-3.0) reached over its HTTP API only; none of its code is here.
The token comes from VOICESTUDIO_TOKEN and is never printed. Routes are found in /openapi.json (prefixes change)."""
import json
import mimetypes
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PRESETS = json.loads((Path(__file__).resolve().parent / "data" / "presets.json").read_text(encoding="utf-8"))


class Fail(Exception):
    """A user-facing failure with an exit code (2 = bad input)."""

    def __init__(self, msg: str, code: int = 1):
        super().__init__(msg)
        self.code = code


class VoiceStudio:
    def __init__(self, url=None, token=None, timeout: float = 600):
        self.url = (url or os.environ.get("VOICESTUDIO_URL") or PRESETS["voicestudio_url"]).rstrip("/")
        self.token = token if token is not None else os.environ.get("VOICESTUDIO_TOKEN")
        self.timeout = timeout
        self._paths = None

    def _req(self, method, path, body=None, ctype=None, timeout=None):
        req = urllib.request.Request(self.url + path, data=body, method=method)
        if ctype:
            req.add_header("Content-Type", ctype)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return r.status, r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            detail = e.read()[:500].decode("utf-8", "replace")
            if e.code in (401, 403):
                raise Fail(f"VoiceStudio refused the call ({e.code}): set VOICESTUDIO_TOKEN to the configured key; {detail}")
            raise Fail(f"VoiceStudio {method} {path} -> HTTP {e.code}: {detail}")
        except (urllib.error.URLError, OSError) as e:
            raise Fail(f"VoiceStudio not reachable at {self.url} ({getattr(e, 'reason', e)}); {PRESETS['install']['voicestudio']}")

    def json(self, method, path, payload=None, timeout=None):
        body = None if payload is None else json.dumps(payload).encode()
        return json.loads(self._req(method, path, body, "application/json" if body else None, timeout)[1] or b"null")

    def health(self) -> dict:
        return self.json("GET", "/health", timeout=4)

    def up(self) -> bool:
        try:
            self.health()
            return True
        except Fail:
            return False

    def path(self, suffix: str, method: str = "post") -> str:
        """The running version's route ending with suffix (shortest wins)."""
        if self._paths is None:
            spec = self.json("GET", "/openapi.json", timeout=15)
            self._paths = [(m.lower(), p) for p, ops in ((spec or {}).get("paths") or {}).items()
                           if isinstance(ops, dict) for m in ops]
        hits = sorted((p for m, p in self._paths if m == method and p.endswith(suffix)), key=len)
        if not hits:
            raise Fail(f"this VoiceStudio version has no {method.upper()} *{suffix} route (checked /openapi.json)")
        return hits[0]

    def multipart(self, path: str, fields: dict, files: dict) -> dict:
        boundary = uuid.uuid4().hex
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                 for k, v in fields.items() if v is not None]
        for k, fp in files.items():
            fp = Path(fp)
            ctype = mimetypes.guess_type(fp.name)[0] or "application/octet-stream"
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fp.name}"\r\n'
                         f"Content-Type: {ctype}\r\n\r\n".encode() + fp.read_bytes() + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        return json.loads(self._req("POST", path, body, f"multipart/form-data; boundary={boundary}")[1] or b"null")

    def voices(self):
        return self.json("GET", "/v1/audio/voices")

    def speak(self, text: str, out: Path, voice=None) -> None:
        payload = {"model": "tts-1", "input": text, "voice": voice or PRESETS["voicestudio_voice"], "response_format": "wav"}
        _, data, ctype = self._req("POST", "/v1/audio/speech", json.dumps(payload).encode(), "application/json")
        if "json" in ctype or not data:
            raise Fail(f"VoiceStudio returned no audio: {data[:300].decode('utf-8', 'replace')}")
        Path(out).write_bytes(data)

    def transcribe(self, audio: Path) -> dict:
        return self.multipart("/v1/audio/transcriptions", {"model": "whisper-1", "response_format": "verbose_json",
                                                          "timestamp_granularities[]": "word"}, {"file": audio})

    def clone(self, ref: Path, name: str, ref_text: str, lang: str) -> dict:
        return self.multipart(self.path("/profiles"), {"name": name, "kind": "clone", "ref_text": ref_text,
                                                       "language": lang}, {"ref_audio": ref})

    def describe(self, description: str) -> dict:
        return self.json("POST", self.path("/design/describe"), {"description": description})

    def design(self, description: str, name: str) -> dict:
        d = self.describe(description)
        if not d.get("matched"):
            raise Fail(f"VoiceStudio mapped no voice attribute from this description (unmatched: {d.get('unmatched')})")
        prof = self.multipart(self.path("/profiles"), {"name": name, "kind": "design", "instruct": d.get("instruct", ""),
                                                       "vd_states": json.dumps(d.get("attrs") or {})}, {})
        return {"describe": d, "profile": prof}
