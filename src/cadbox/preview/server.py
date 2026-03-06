"""Web application server for cadbox.

Serves the full cadbox UI with REST API endpoints for config management
and container generation. Binds to 0.0.0.0:8085 by default with optional
SSL support (designed for use behind Tailscale HTTPS).
"""

from __future__ import annotations

import json
import ssl
import tempfile
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from . import storage
from .ui import HTML_TEMPLATE

# ---------------------------------------------------------------------------
# Globals for the current model
# ---------------------------------------------------------------------------

_current_stl: Path | None = None
_current_step: Path | None = None
_model_lock = threading.Lock()


def _set_current_stl(path: Path) -> None:
    global _current_stl
    with _model_lock:
        _current_stl = path


def _get_current_stl() -> Path | None:
    with _model_lock:
        return _current_stl


def _set_current_step(path: Path) -> None:
    global _current_step
    with _model_lock:
        _current_step = path


def _get_current_step() -> Path | None:
    with _model_lock:
        return _current_step


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


def _make_handler(initial_stl: Path | None = None) -> type[BaseHTTPRequestHandler]:
    """Return a request handler class with REST API endpoints."""

    if initial_stl:
        _set_current_stl(initial_stl)

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

        # -- Routing --------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]

            if path == "/" or path == "/index.html":
                self._serve_html()
            elif path == "/model.stl":
                self._serve_stl()
            elif path == "/api/configs":
                self._api_list_configs()
            elif path.startswith("/api/configs/"):
                name = unquote(path[len("/api/configs/"):])
                self._api_get_config(name)
            elif path == "/download/step":
                self._serve_download("step")
            elif path == "/download/stl":
                self._serve_download("stl")
            else:
                self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]

            if path == "/api/generate":
                self._api_generate()
            elif path == "/api/validate":
                self._api_validate()
            elif path.startswith("/api/configs/"):
                name = unquote(path[len("/api/configs/"):])
                self._api_save_config(name)
            else:
                self.send_error(404)

        def do_DELETE(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]

            if path.startswith("/api/configs/"):
                name = unquote(path[len("/api/configs/"):])
                self._api_delete_config(name)
            else:
                self.send_error(404)

        # -- Static ---------------------------------------------------------

        def _serve_html(self) -> None:
            body = HTML_TEMPLATE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._common_headers()
            self.end_headers()
            self.wfile.write(body)

        def _serve_stl(self) -> None:
            stl_path = _get_current_stl()
            if stl_path is None or not stl_path.exists():
                self.send_error(404, "No model generated yet")
                return
            data = stl_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "model/stl")
            self.send_header("Content-Length", str(len(data)))
            self._common_headers()
            self.end_headers()
            self.wfile.write(data)

        def _serve_download(self, fmt: str) -> None:
            if fmt == "step":
                fpath = _get_current_step()
                ctype = "application/step"
                ext = "step"
            else:
                fpath = _get_current_stl()
                ctype = "model/stl"
                ext = "stl"
            if fpath is None or not fpath.exists():
                self.send_error(404, f"No {fmt.upper()} file generated yet")
                return
            data = fpath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header(
                "Content-Disposition", f'attachment; filename="cadbox-output.{ext}"'
            )
            self._common_headers()
            self.end_headers()
            self.wfile.write(data)

        # -- Config CRUD API ------------------------------------------------

        def _api_list_configs(self) -> None:
            configs = storage.list_configs()
            self._json_response(configs)

        def _api_get_config(self, name: str) -> None:
            try:
                data = storage.load_config(name)
                self._json_response(data)
            except FileNotFoundError:
                self._json_error(404, f"Config '{name}' not found")

        def _api_save_config(self, name: str) -> None:
            body = self._read_json_body()
            if body is None:
                return
            storage.save_config(name, body)
            self._json_response({"ok": True})

        def _api_delete_config(self, name: str) -> None:
            try:
                storage.delete_config(name)
                self._json_response({"ok": True})
            except FileNotFoundError:
                self._json_error(404, f"Config '{name}' not found")

        # -- Generate API ---------------------------------------------------

        def _api_generate(self) -> None:
            body = self._read_json_body()
            if body is None:
                return

            try:
                from cadbox.config import ConfigError, load_config_from_string
                from cadbox.generator import export_step, export_stl, generate
                from cadbox.packer import PackingError, pack_cavities
                from cadbox.validator import CadboxValidationError, validate_all

                import sys
                print(f"[generate] request body: {json.dumps(body, indent=2)}", flush=True)
                sys.stderr.write(f"[generate] width={body.get('width')} length={body.get('length')} cavities={len(body.get('cavities',[]))}\n")
                sys.stderr.flush()
                config = load_config_from_string(json.dumps(body))
                validate_all(config)
                packing = pack_cavities(config)

                solid = generate(config, packing)

                tmpdir = Path(tempfile.gettempdir())
                stl_path = tmpdir / "cadbox_preview.stl"
                step_path = tmpdir / "cadbox_preview.step"
                export_stl(solid, stl_path)
                export_step(solid, step_path)
                _set_current_stl(stl_path)
                _set_current_step(step_path)

                self._json_response({
                    "ok": True,
                    "placements": len(packing.placements),
                    "utilization": round(packing.utilization * 100, 1),
                })

            except ConfigError as exc:
                self._json_error(400, str(exc))
            except CadboxValidationError as exc:
                self._json_error(400, str(exc))
            except PackingError as exc:
                self._json_error(400, f"{exc.message} Suggestion: {exc.suggestion}")
            except Exception as exc:
                self._json_error(500, f"Generation failed: {exc}\n{traceback.format_exc()}")

        # -- Validate API ---------------------------------------------------

        def _api_validate(self) -> None:
            body = self._read_json_body()
            if body is None:
                return

            try:
                from cadbox.config import ConfigError, load_config_from_string
                from cadbox.validator import CadboxValidationError, validate_all

                config = load_config_from_string(json.dumps(body))
                validate_all(config)
                self._json_response({"valid": True, "errors": []})

            except ConfigError as exc:
                self._json_response({"valid": False, "errors": [str(exc)]})
            except CadboxValidationError as exc:
                self._json_response({
                    "valid": False,
                    "errors": [str(e) for e in exc.errors],
                })
            except Exception as exc:
                self._json_response({"valid": False, "errors": [str(exc)]})

        # -- Helpers --------------------------------------------------------

        def _read_json_body(self) -> dict | None:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                self._json_error(400, "Empty request body")
                return None
            raw = self.rfile.read(length)
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                self._json_error(400, f"Invalid JSON: {exc}")
                return None

        def _json_response(self, data: Any, status: int = 200) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._common_headers()
            self.end_headers()
            self.wfile.write(body)

        def _json_error(self, status: int, message: str) -> None:
            self._json_response({"error": message}, status=status)

        def _common_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")

    return _Handler


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def launch_preview(
    stl_path: str | Path | None = None,
    port: int = 8085,
    host: str = "0.0.0.0",
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    open_browser: bool = True,
) -> None:
    """Start the cadbox web UI server.

    Args:
        stl_path:       Optional initial STL file to display.
        port:           TCP port (default 8085).
        host:           Bind address (default 0.0.0.0 for Tailscale access).
        ssl_certfile:   Path to SSL certificate file (PEM). If provided with
                        ssl_keyfile, the server will use HTTPS.
        ssl_keyfile:    Path to SSL private key file (PEM).
        open_browser:   Whether to auto-open the browser.
    """
    initial_stl = None
    if stl_path is not None:
        initial_stl = Path(stl_path)
        if not initial_stl.exists():
            raise FileNotFoundError(f"Model file not found: {initial_stl}")

    handler_class = _make_handler(initial_stl)

    class _ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True

    server = _ReusableHTTPServer((host, port), handler_class)

    # SSL wrapping (Tailscale provides the actual certificates)
    if ssl_certfile and ssl_keyfile:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=ssl_certfile, keyfile=ssl_keyfile)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    else:
        scheme = "http"

    display_host = "localhost" if host == "0.0.0.0" else host
    url = f"{scheme}://{display_host}:{port}"
    print(f"cadbox server running at {url}  (Ctrl-C to stop)")
    print(f"  Listening on {host}:{port}")
    if ssl_certfile:
        print(f"  SSL enabled (cert: {ssl_certfile})")

    if open_browser:
        timer = threading.Timer(0.4, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
