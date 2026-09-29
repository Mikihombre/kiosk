import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .db import default_db_path, initialize
from .service import InputError, create_order, demo_pay, products


STATIC = Path(__file__).resolve().parent.parent / "static"
FILES = {"/": ("index.html", "text/html; charset=utf-8"),
         "/app.css": ("app.css", "text/css; charset=utf-8"),
         "/app.js": ("app.js", "text/javascript; charset=utf-8")}


def handler_for(db_path):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, body):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/health":
                return self.respond(200, {"status": "ok", "app": "kiosk-mvp", "mode": "demo", "products": len(products(db_path))})
            if path == "/api/products":
                return self.respond(200, {"products": products(db_path)})
            if path not in FILES:
                return self.respond(404, {"error": "Nie znaleziono."})
            filename, content_type = FILES[path]
            data = (STATIC / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            path = urlsplit(self.path).path
            if path != "/api/orders" and path != "/api/orders/demo-pay":
                return self.respond(404, {"error": "Nie znaleziono."})
            # Local demo still restricts request sizes and accepts JSON only.
            if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                return self.respond(415, {"error": "Wymagany format JSON."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 16384:
                    return self.respond(413, {"error": "Nieprawidłowy rozmiar żądania."})
                payload = json.loads(self.rfile.read(length))
                result = create_order(db_path, payload) if path == "/api/orders" else demo_pay(
                    db_path, payload.get("order_id") if isinstance(payload, dict) else None
                )
                self.respond(200 if path.endswith("demo-pay") else 201, {"order": result})
            except (ValueError, json.JSONDecodeError, InputError) as exc:
                self.respond(400, {"error": str(exc)})

    return Handler


def main():
    port = int(os.environ.get("KIOSK_PORT", "8765"))
    db_path = default_db_path()
    initialize(db_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(db_path))
    print(f"Kiosk demo: http://127.0.0.1:{port} (baza: {db_path})")
    stop_file = Path(os.environ["KIOSK_STOP_FILE"]) if os.environ.get("KIOSK_STOP_FILE") else None
    try:
        if stop_file:
            server.timeout = 0.5
            while not stop_file.exists():
                server.handle_request()
        else:
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if stop_file:
            stop_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
