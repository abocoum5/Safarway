#!/usr/bin/env python3
"""Webhook GitHub → déploiement automatique Goova."""
import hashlib, hmac, json, os, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

SECRET = os.environ.get("WEBHOOK_SECRET", "").encode()
DEPLOY  = "/var/www/goova/deploy/update.sh"

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        # Vérification signature GitHub
        if SECRET:
            sig      = self.headers.get("X-Hub-Signature-256", "")
            expected = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                self._reply(403, "Signature invalide")
                return

        # Seulement les push sur main
        try:
            ref = json.loads(body).get("ref", "")
        except Exception:
            ref = ""

        if ref == "refs/heads/main":
            subprocess.Popen(["bash", DEPLOY])
            self._reply(200, "Déploiement lancé")
        else:
            self._reply(200, "Ignoré")

    def _reply(self, code, msg):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(msg.encode())

    def log_message(self, *_):
        pass

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 9000), Handler).serve_forever()
