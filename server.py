#!/usr/bin/env python3
"""Statischer Webserver für Escargozzled plus Highscore-API (scores.json).

Start:  python3 server.py [port]
Dann:   http://localhost:8000 im Chrome öffnen (Web Bluetooth braucht localhost/https).
"""
import json
import os
import socket
import sys
import tempfile
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCORES_FILE = os.path.join(BASE_DIR, "scores.json")
MAX_LEVEL = 15
TOP_N = 10

lock = threading.Lock()


def load_scores():
    if not os.path.exists(SCORES_FILE):
        return []
    with open(SCORES_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_scores(scores):
    # Atomar schreiben, damit scores.json bei Absturz nicht kaputtgeht
    fd, tmp = tempfile.mkstemp(dir=BASE_DIR, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SCORES_FILE)


def ranked(scores):
    # Höchster Score zuerst, bei Gleichstand kürzere Zeit, dann früherer Eintrag
    return sorted(scores, key=lambda s: (-s["score"], s["durationSec"], s["date"]))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/scores":
            with lock:
                scores = ranked(load_scores())
            self.send_json(200, {"total": len(scores), "top": scores[:TOP_N]})
            return
        if self.path.split("?")[0] == "/scores.json":
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/scores":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(min(length, 10_000)))
            entry = {
                "name": (str(data.get("name", "")).strip() or "Anonym")[:30],
                "score": int(data["score"]),
                "level": max(1, min(MAX_LEVEL, int(data["level"]))),
                "durationSec": max(0, int(data.get("durationSec", 0))),
                "date": datetime.now().isoformat(timespec="seconds"),
            }
        except (ValueError, KeyError, TypeError) as e:
            self.send_json(400, {"error": f"Ungültige Daten: {e}"})
            return

        with lock:
            scores = load_scores()
            scores.append(entry)
            save_scores(scores)
            order = ranked(scores)

        rank = next(i for i, s in enumerate(order, 1) if s is entry)
        self.send_json(200, {"rank": rank, "total": len(order), "entry": entry, "top": order[:TOP_N]})


def port_in_use(port):
    # Chrome löst "localhost" oft auf ::1 auf – ein anderer Server dort würde die API verdecken
    for family, addr in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex((addr, port)) == 0:
                    return addr
        except OSError:
            pass
    return None


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    busy = port_in_use(port)
    if busy:
        sys.exit(f"❌ Port {port} ist bereits belegt ({busy}). Alten Server beenden, z. B.: lsof -nP -iTCP:{port} -sTCP:LISTEN")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"🐌 Escargozzled läuft auf http://127.0.0.1:{port}  (Scores: {SCORES_FILE})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
