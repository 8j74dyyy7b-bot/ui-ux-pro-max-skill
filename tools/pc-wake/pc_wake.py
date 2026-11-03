#!/usr/bin/env python3
"""PC Wake - turn on a PC remotely via Wake-on-LAN.

Runs on any always-on device in the same home network as the PC
(Raspberry Pi, NAS, old laptop). Python 3 standard library only.

  python3 pc_wake.py wake AA:BB:CC:DD:EE:FF        # send one magic packet now
  python3 pc_wake.py serve --mac AA:BB:CC:DD:EE:FF --pin 1234 [--port 8080]
                                                   # phone-friendly web page
"""
import argparse
import hmac
import html
import re
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]?){5}[0-9A-Fa-f]{2}$")


def parse_mac(mac: str) -> bytes:
    if not MAC_RE.match(mac.strip()):
        raise ValueError(f"Ungueltige MAC-Adresse: {mac}")
    return bytes.fromhex(re.sub(r"[:-]", "", mac.strip()))


def send_magic_packet(mac: str, broadcast: str = "255.255.255.255", port: int = 9) -> None:
    """Magic packet = 6x 0xFF followed by the MAC 16 times, sent as UDP broadcast."""
    packet = b"\xff" * 6 + parse_mac(mac) * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for p in {port, 7}:  # some network cards listen on 7, most on 9
            s.sendto(packet, (broadcast, p))


def is_online(host: str) -> bool:
    if not host:
        return False
    flag = "-n" if sys.platform.startswith("win") else "-c"
    try:
        return subprocess.run(["ping", flag, "1", host], capture_output=True, timeout=3).returncode == 0
    except Exception:
        return False


PAGE = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PC einschalten</title><style>
:root{{--bg:#f4f5f7;--card:#fff;--fg:#1a1c20;--muted:#5f6670;--accent:#2563eb;--ok:#15803d;--err:#b91c1c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1115;--card:#1a1d23;--fg:#e8eaed;--muted:#9aa1ab;--accent:#3b82f6;--ok:#4ade80;--err:#f87171}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);
color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:16px}}
main{{width:100%;max-width:380px;background:var(--card);border-radius:16px;padding:28px;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
h1{{margin:0 0 4px;font-size:22px}}p{{margin:0 0 20px;color:var(--muted)}}
input,button{{width:100%;font:inherit;padding:14px;border-radius:10px;min-height:48px}}
input{{border:1px solid var(--muted);background:transparent;color:var(--fg);margin-bottom:12px}}
button{{border:0;background:var(--accent);color:#fff;font-weight:600;cursor:pointer}}
.msg{{margin-top:16px;font-weight:600}}.ok{{color:var(--ok)}}.err{{color:var(--err)}}
</style></head><body><main>
<h1>{name}</h1><p>Status: {status}</p>
<form method="post"><input type="password" name="pin" inputmode="numeric" placeholder="PIN"
autocomplete="current-password" required aria-label="PIN"><button type="submit">PC einschalten</button></form>
{msg}</main></body></html>"""


def make_handler(cfg):
    attempts = {}

    class Handler(BaseHTTPRequestHandler):
        def _page(self, msg="", code=200):
            status = "online" if is_online(cfg.host) else ("offline" if cfg.host else "unbekannt")
            body = PAGE.format(name=html.escape(cfg.name), status=status, msg=msg).encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._page()

        def do_POST(self):
            ip = self.client_address[0]
            now = time.time()
            recent = [t for t in attempts.get(ip, []) if now - t < 300]
            if len(recent) >= 5:  # simple brute-force protection
                return self._page('<div class="msg err">Zu viele Versuche. Bitte 5 Minuten warten.</div>', 429)
            length = min(int(self.headers.get("Content-Length", 0)), 1024)
            pin = parse_qs(self.rfile.read(length).decode()).get("pin", [""])[0]
            if not hmac.compare_digest(pin.encode(), cfg.pin.encode()):
                attempts[ip] = recent + [now]
                return self._page('<div class="msg err">Falsche PIN.</div>', 403)
            attempts.pop(ip, None)
            send_magic_packet(cfg.mac, cfg.broadcast)
            self._page('<div class="msg ok">Signal gesendet. Der PC startet in ca. 30 Sekunden.</div>')

        def log_message(self, fmt, *args):
            sys.stderr.write(f"[{self.log_date_time_string()}] {self.client_address[0]} {fmt % args}\n")

    return Handler


def main():
    ap = argparse.ArgumentParser(description="PC per Wake-on-LAN einschalten")
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("wake", help="Magic Packet sofort senden")
    w.add_argument("mac")
    w.add_argument("--broadcast", default="255.255.255.255")

    s = sub.add_parser("serve", help="Weboberflaeche starten")
    s.add_argument("--mac", required=True)
    s.add_argument("--pin", required=True)
    s.add_argument("--host", default="", help="IP des PCs fuer Online-Anzeige (optional)")
    s.add_argument("--name", default="Mein PC")
    s.add_argument("--broadcast", default="255.255.255.255")
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--bind", default="0.0.0.0")

    args = ap.parse_args()
    parse_mac(args.mac)
    if args.cmd == "wake":
        send_magic_packet(args.mac, args.broadcast)
        print(f"Magic Packet an {args.mac} gesendet.")
    else:
        if len(args.pin) < 4:
            ap.error("PIN muss mindestens 4 Zeichen haben")
        print(f"Web-Oberflaeche laeuft auf http://{args.bind}:{args.port}")
        ThreadingHTTPServer((args.bind, args.port), make_handler(args)).serve_forever()


if __name__ == "__main__":
    main()
