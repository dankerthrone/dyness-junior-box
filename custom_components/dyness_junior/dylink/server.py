"""Asyncio-Server, der die Dyness-Junior-Box lokal bedient (Dylink TCP 5005).

Verhaltensweise (Reverse Engineering 2026-10-31, siehe docs/ROADMAP.md):
- login   → Banner + Login-ACK
- bind    → BindACK (frisches Token) + Zeitsync-Push
- config-report → 99 71 01
- Telemetrie-Frames → 99 04 01
- config-ack (91 87) → (nichts)
Die Box reconnectet im ~14-s-Zyklus; bei vielen Fehlversuchen geht sie in
Backoff (Power-Cycle hilft). Zustandsloser Spiegel — robust gegen jede
Frame-Reihenfolge der Box.

WICHTIG (gemessen 2026-10-31, Live-Relay zur echten Cloud): Der echte Server
(NLB) beendet die Verbindung nach ~10-12 s Inaktivitaet. Die Box schickt ihre
Daten (Config-Report + periodische Telemetrie) NUR im Rahmen des Reconnect-
Zyklus. Haelt der Server die Verbindung offen, sitzt die Box in einer leeren
Session und es fliessen KEINE Daten. Deshalb: Verbindungen nach ~12 s ohne
eingehende Frames schliessen (TIME_IDLE_CLOSE_S), damit die Box im natuerlichen
Zyklus bleibt. Verifiziert: damit ist der ~14-s-Reconnect-Normalbetrieb
wiederhergestellt, Firmware/SOC/SOH/Register aktualisieren sich von selbst.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from . import frames
from . import parser

_LOGGER = logging.getLogger(__name__)

MAX_FRAME = 8192

# Wie der echte Cloud-Server: Verbindung nach dieser Inaktivitaet (s) schliessen.
TIME_IDLE_CLOSE_S = 12.0


class DylinkServer:
    def __init__(self, serial: str, host: str = "0.0.0.0", port: int = 5005):
        self._serial = serial
        self._host = host
        self._port = port
        self._server: asyncio.Server | None = None
        self._clients: set[asyncio.StreamWriter] = set()
        self._client_count = 0
        self.client_connected = False
        # Callbacks (werden von HA gesetzt)
        self.on_state: Callable[[dict], None] | None = None
        self.on_telemetry: Callable[[bytes], None] | None = None
        self.on_registers: Callable[[dict], None] | None = None
        self.on_report: Callable[[dict], None] | None = None

    # --- Lifecycle -----------------------------------------------------
    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self._host, self._port
        )
        _LOGGER.info("Dylink-Server lauscht auf %s:%s (S/N %s)", self._host, self._port, self._serial)

    async def stop(self) -> None:
        for w in list(self._clients):
            w.close()
        self._clients.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._set_connected(False)

    # --- Steuerung --------------------------------------------------------
    def inject(self, frame: bytes) -> bool:
        """Befehl an die aktuell verbundene Box senden (00-78-Steuerung)."""
        if not self._clients:
            return False
        for w in list(self._clients):
            try:
                w.write(frame)
            except Exception:  # noqa: BLE001
                continue
        return True

    # --- Intern ------------------------------------------------------------
    def _set_connected(self, value: bool) -> None:
        if value != self.client_connected:
            self.client_connected = value
            if self.on_state:
                self.on_state({"connected": value})

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._client_count += 1
        self._clients.add(writer)
        self._set_connected(True)
        buf = b""
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(reader.read(65536), timeout=TIME_IDLE_CLOSE_S)
                except asyncio.TimeoutError:
                    # wie der echte Server: Leerlauf beendet die Verbindung ->
                    # Box reconnectet und pusht frische Daten (Config/Telemetrie)
                    break
                if not chunk:
                    break
                buf += chunk
                while len(buf) >= 4:
                    ln = int.from_bytes(buf[:4], "big")
                    if not 0 < ln <= MAX_FRAME:
                        _LOGGER.warning("kaputtes Frame (len %s) — Verbindung beendet", ln)
                        return
                    if len(buf) < 4 + ln:
                        break
                    payload = buf[4:4 + ln]
                    buf = buf[4 + ln:]
                    await self._process(self._serial, payload, writer)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Client-Fehler: %s", exc)
        finally:
            self._clients.discard(writer)
            writer.close()
            if not self._clients:
                self._set_connected(False)
            _LOGGER.debug("Verbindung beendet (insgesamt %s)", self._client_count)

    async def _process(self, serial: str, p: bytes, writer: asyncio.StreamWriter) -> None:
        ln = len(p)
        tag = p[17:19] if ln > 19 else p
        try:
            if ln >= 2 and p[0] == 0x10 and b"\x91\x00" in p[:24] and ln < 100:
                # Login
                writer.write(frames.BANNER)
                writer.write(frames.build_login_ack(serial))
                await writer.drain()
            elif ln > 400 and tag == b"\x91\x71":
                writer.write(frames.build_ack_cfgrep(serial))
                await writer.drain()
                if self.on_report:
                    self.on_report(parser.parse_config_report(p))
            elif ln > 100:
                # Telemetrie/Register
                writer.write(frames.build_ack_telem(serial))
                await writer.drain()
                if self.on_registers:
                    self.on_registers(parser.parse_registers(p))
                if self.on_telemetry:
                    self.on_telemetry(p)
            elif tag == b"\x91\x22":
                writer.write(frames.build_bind_ack(serial))
                writer.write(frames.build_time_push(serial))
                await writer.drain()
            elif tag == b"\x91\x87":
                pass  # config-ack der Box — keine Antwort nötig
            elif tag == b"\x91\x78":
                _LOGGER.info(">>> 91-78-ACK der Box (Befehl ausgefuehrt)")
            else:
                _LOGGER.debug("unbekanntes Frame (%sB %s)", ln, tag.hex())
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Frame-Verarbeitung: %s", exc)

    @property
    def port(self) -> int:
        return self._port

    @property
    def connected(self) -> bool:
        return self.client_connected