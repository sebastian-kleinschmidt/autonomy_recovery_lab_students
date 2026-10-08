from __future__ import annotations

import argparse
import errno
import json
import mimetypes
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .agent_contract import AgentPolicy
from .agent_loader import load_agent
from .dynamics import Control
from .engine import SimulationEngine
from .scenario import GUARDRAILS, PERCEPTION_MODELS, with_guardrails, Scenario, load_scenario, with_perception_model, with_vla_mode


WEB_ROOT = Path(__file__).with_name("web")
VEHICLE_ROOT = Path(__file__).with_name("vehicles")


def resolve_static_path(request_path: str) -> Path | None:
    if request_path.startswith("/vehicles/"):
        root = VEHICLE_ROOT.resolve()
        relative = request_path.removeprefix("/vehicles/")
    else:
        root = WEB_ROOT.resolve()
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
    candidate = (root / relative).resolve()
    if candidate.parent != root or not candidate.is_file():
        return None
    return candidate


class LiveSimulation:
    def __init__(
        self,
        scenario: Scenario,
        agent: AgentPolicy | None = None,
        *,
        agent_name: str = "none",
    ):
        self.scenario = scenario
        self.agent = agent
        self.agent_name = agent_name
        self.engine = self._new_engine()
        self.control = Control()
        self.paused = True
        self.speed_factor = 1.0
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _new_engine(self) -> SimulationEngine:
        # Ohne angeschlossenen Agenten uebernimmt die Recovery Console der Oberflaeche die Sitzung.
        return SimulationEngine(
            self.scenario,
            agent=self.agent,
            agent_name=self.agent_name,
            console=self.agent is None,
        )

    def start_worker(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="autonomy-recovery-sim-loop")
        self._thread.start()

    def stop_worker(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        next_tick = time.monotonic()
        while not self._stop.is_set():
            delay = next_tick - time.monotonic()
            if delay > 0:
                # Kurze Wartescheiben halten Stop und Bedienung reaktionsfaehig; geschritten
                # wird erst, wenn der Takt wirklich erreicht ist (sonst wirkt Zeitlupe nicht).
                self._stop.wait(min(delay, 0.1))
                continue
            with self._lock:
                paused = self.paused
                factor = self.speed_factor
                if not paused and not self.engine.done:
                    self.engine.step(self.control)
            next_tick += self.scenario.dt_s / max(0.25, factor)
            if next_tick < time.monotonic():
                next_tick = time.monotonic()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            result = self.engine.snapshot()
            result["paused"] = self.paused
            result["speed_factor"] = self.speed_factor
            return result

    def command(self, payload: dict[str, Any]) -> dict[str, object]:
        with self._lock:
            action = str(payload.get("action", ""))
            if action == "start":
                if self.engine.done:
                    self.engine = self._new_engine()
                    self.control = Control()
                self.paused = False
            elif action == "pause":
                self.paused = True
            elif action == "toggle":
                self.paused = not self.paused
            elif action == "reset":
                self.engine = self._new_engine()
                self.control = Control()
                self.paused = True
            elif action == "step":
                if not self.engine.done:
                    self.engine.step(self.control)
            elif action == "console_tool":
                arguments = payload.get("arguments", {})
                if not isinstance(arguments, dict):
                    raise ValueError("arguments muss ein Objekt sein")
                self.engine.console_tool(str(payload.get("name", "")), arguments)
            elif action == "console_evidence":
                self.engine.console_gather_evidence()
            elif action == "console_submit":
                submitted = payload.get("payload", {})
                if not isinstance(submitted, dict):
                    raise ValueError("payload muss ein Objekt sein")
                self.engine.console_submit(submitted)
            elif action and action != "control":
                raise ValueError(f"Unbekannte Aktion: {action}")

            if "mode" in payload:
                self.engine.set_mode(str(payload["mode"]))
            if any(key in payload for key in ("throttle", "brake", "steering")):
                self.control = Control(
                    throttle=float(payload.get("throttle", self.control.throttle)),
                    brake=float(payload.get("brake", self.control.brake)),
                    steering=float(payload.get("steering", self.control.steering)),
                ).clamped()
            if "speed_factor" in payload:
                self.speed_factor = min(4.0, max(0.25, float(payload["speed_factor"])))
            return self.snapshot()


def _handler_for(live: LiveSimulation) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AutonomyRecoverySim/0.3"

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/state":
                self._send_json(live.snapshot())
                return
            candidate = resolve_static_path(path)
            if candidate is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = candidate.read_bytes()
            mime, _ = mimetypes.guess_type(candidate.name)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{mime or 'application/octet-stream'}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            # The live UI is developed as a tightly coupled HTML/JS/CSS bundle.
            # Prevent mixed cached versions, which can leave controls attached
            # to stale markup after a simulator update.
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/command":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("JSON-Objekt erwartet")
                self._send_json(live.command(payload))
            except (ValueError, json.JSONDecodeError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    return Handler


def create_server(live: LiveSimulation, host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _handler_for(live))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live-2D-Oberflaeche fuer AutonomyRecoverySim")
    parser.add_argument(
        "--scenario",
        type=Path,
        default=Path("autonomy_recovery_sim/scenarios/hannover_frei.json"),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--agent",
        default="none",
        help="none, baseline, llm oder python_modul:funktion (Standard: none)",
    )
    parser.add_argument("--vla", action="store_true", help="Szenario mit VLA-Fahrstack ausfuehren")
    parser.add_argument(
        "--perception",
        choices=PERCEPTION_MODELS,
        help="Wahrnehmungsmodell erzwingen (tracked: Objektliste mit Messunsicherheit)",
    )
    parser.add_argument(
        "--guardrails",
        choices=GUARDRAILS,
        help="Pruefmodus erzwingen (off: keine vorausschauenden Abbrueche, Unfaelle moeglich)",
    )
    args = parser.parse_args(argv)

    try:
        loaded_agent = load_agent(args.agent)
    except ValueError as exc:
        parser.error(str(exc))

    scenario = load_scenario(args.scenario)
    if args.perception:
        scenario = with_perception_model(scenario, args.perception)
    if args.guardrails:
        scenario = with_guardrails(scenario, args.guardrails)
    live = LiveSimulation(
        with_vla_mode(scenario) if args.vla else scenario,
        agent=loaded_agent.policy,
        agent_name=loaded_agent.name,
    )
    try:
        server = create_server(live, args.host, args.port)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            print(f"Port {args.port} ist bereits belegt.")
            print(f"Pruefe http://{args.host}:{args.port} oder starte mit --port {args.port + 1}.")
            return 2
        raise
    live.start_worker()
    print(f"AutonomyRecoverySim laeuft auf http://{args.host}:{server.server_port}")
    print(f"Agent: {loaded_agent.name}")
    print("Beenden mit Ctrl+C")
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nAutonomyRecoverySim beendet")
    finally:
        server.server_close()
        live.stop_worker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
