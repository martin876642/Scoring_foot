"""
serve.py — Serveur de développement local (sans cache)
=======================================================
Lance un serveur HTTP sur http://localhost:8000 qui sert
maquette_site/ avec des headers no-cache sur tous les fichiers.

Usage :
    python serve.py
    python serve.py 8080   # port personnalisé
"""

import sys
import os
import webbrowser
from http.server import SimpleHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
DIRECTORY = os.path.join(os.path.dirname(__file__), "maquette_site")


class NoCacheHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        # Log uniquement les erreurs (4xx/5xx) pour ne pas polluer le terminal
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(format, *args)


if __name__ == "__main__":
    os.chdir(DIRECTORY)
    server = HTTPServer(("", PORT), NoCacheHandler)
    url = f"http://localhost:{PORT}/Scouting.html"
    print(f"\n  FootScout — serveur de développement")
    print(f"  URL     : {url}")
    print(f"  Dossier : {DIRECTORY}")
    print(f"  Arrêter : Ctrl+C\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Serveur arrêté.")
