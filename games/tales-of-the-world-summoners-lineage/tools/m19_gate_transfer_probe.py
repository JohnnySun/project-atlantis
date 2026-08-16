#!/usr/bin/env python3
"""M1.9 strict keyboard-gate and one-transfer probe for A9PJ.

This is deliberately smaller than the M1.8 exploratory probe.  A run uses
one fresh mGBA process and one GDB connection.  The transport is serialized,
the shared GDB parser still owns packet ACKs, and malformed/short responses
abort the run instead of being interpreted as a queued answer.

``--mode gate`` only watches KEYINPUT while replaying a bounded START path and
records BG1 metadata plus hashes.  ``--mode transfer`` replays the already
observed number of START presses, arms one 32-byte write watch at the first
keyboard tile, and records at most one CPU/BIOS writer receipt.  It does not
write game state, tilemap, or VRAM.  Reports contain metadata and hashes only;
raw emulator output belongs in an ignored/private directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_DIR))

from capture_runtime import capture  # noqa: E402
from gdbstub_client import GdbClient, REG_NAMES, parse_stop_watch  # noqa: E402
from m15_navigate_probe import (  # noqa: E402
    KEYINPUT,
    NO_KEY,
    button_value,
    identity,
    parse_sequence,
)
from m16_name_entry_probe import read_display_maps  # noqa: E402


TILE1 = 0x06004020
TILE2 = 0x06004040
TILE_BYTES = 0x20
DMA3_SOURCE = 0x040000D4
DMA3_DESTINATION = 0x040000D8
DMA3_COUNT = 0x040000DC
DMA3_CONTROL = 0x040000DE
DISPCNT = 0x04000000
BG1CNT = 0x0400000A
KNOWN_TILE1_SHA256 = "b5ae44407e13c9f6c085af00c74f47811dff6afe93020f068bdc33b8c1ff39c2"
KNOWN_TILE2_SHA256 = "924e28947f080def610d22c48b729b3bd86957983b679572aeb6d9da293c19f7"
RESET_TILE1_SHA256 = "02d449a31fbb267c8f352e9968a79e3e5fc95c1bbeaa502fd6454ebde5a4bedc"

EWRAM = (0x02000000, 0x02040000)
IWRAM = (0x03000000, 0x03008000)
ROM = (0x08000000, 0x0A000000)


class ProtocolBoundary(RuntimeError):
    """A response cannot be safely associated with the outstanding request."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def response_kind(response: str) -> str:
    if response == "OK":
        return "ok"
    if response.startswith(("S", "T")):
        return "stop"
    if response.startswith("E"):
        return "error"
    if response and len(response) % 2 == 0:
        try:
            bytes.fromhex(response)
        except ValueError:
            pass
        else:
            return "hex"
    return "other"


class StrictGdbClient(GdbClient):
    """Serial GDB client with exact response checks and bounded retry policy.

    ``GdbClient._read_packet`` sends the protocol ACK after validating the
    checksum.  The inherited request has exactly one timeout retry; response
    shape checks below do not retry.  Continue/interrupt are implemented
    separately so a stopped packet is counted and never passed through the
    request retry path.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.protocol = {
            "packet_delay_seconds": self.packet_delay,
            "timeout_seconds": self.timeout,
            "timeout_retry_limit": 1,
            "serialized": True,
            "requests": 0,
            "responses": 0,
            "continues": 0,
            "interrupts": 0,
            "timeouts": 0,
            "response_kinds": {},
        }
        self._inflight = False

    def _record(self, operation: str, response: str) -> None:
        kind = response_kind(response)
        self.protocol["responses"] = int(self.protocol["responses"]) + 1
        kinds = self.protocol["response_kinds"]
        assert isinstance(kinds, dict)
        kinds[kind] = int(kinds.get(kind, 0)) + 1
        # A digest is enough to identify a repeated response without putting
        # raw GDB packets in the tracked report.
        self.protocol.setdefault("response_digests", []).append(
            {
                "operation": operation,
                "kind": kind,
                "length": len(response),
                "sha256": digest(response.encode("ascii", errors="replace")),
            }
        )

    def request(self, payload: str) -> str:
        if self._inflight:
            raise ProtocolBoundary("concurrent GDB request")
        self._inflight = True
        try:
            self.protocol["requests"] = int(self.protocol["requests"]) + 1
            try:
                response = super().request(payload)
            except (TimeoutError, socket.timeout):
                self.protocol["timeouts"] = int(self.protocol["timeouts"]) + 1
                raise
            self._record(payload.split(",", 1)[0][:12], response)
            return response
        finally:
            self._inflight = False

    def read_registers(self) -> dict[str, int]:
        response = self.request("g")
        if len(response) != len(REG_NAMES) * 8:
            raise ProtocolBoundary(
                f"register response length {len(response)} != {len(REG_NAMES) * 8}"
            )
        try:
            raw_values = [
                int.from_bytes(bytes.fromhex(response[index:index + 8]), "little")
                for index in range(0, len(response), 8)
            ]
        except ValueError as exc:
            raise ProtocolBoundary("register response is not hexadecimal") from exc
        return dict(zip(REG_NAMES, raw_values))

    def read_memory(self, address: int, length: int, chunk_size: int = 0x200) -> bytes:
        output = bytearray()
        for offset in range(0, length, chunk_size):
            size = min(chunk_size, length - offset)
            response = self.request(f"m{address + offset:x},{size:x}")
            if response.startswith("E"):
                raise ProtocolBoundary(
                    f"memory read error at 0x{address + offset:08X}"
                )
            if len(response) != size * 2:
                raise ProtocolBoundary(
                    f"memory response length {len(response)} != {size * 2}"
                )
            try:
                output.extend(bytes.fromhex(response))
            except ValueError as exc:
                raise ProtocolBoundary("memory response is not hexadecimal") from exc
        return bytes(output)

    def write_register(self, register_number: int, value: int) -> None:
        raw = (value & 0xFFFFFFFF).to_bytes(4, "little").hex()
        if self.request(f"P{register_number:x}={raw}") != "OK":
            raise ProtocolBoundary("KEYINPUT register write did not return OK")

    def continue_until_stop(self, timeout: float = 30.0) -> str:
        sock = self._require_socket()
        old_timeout = sock.gettimeout()
        sock.settimeout(timeout)
        self.protocol["continues"] = int(self.protocol["continues"]) + 1
        try:
            self.continue_running()
            response = self._read_packet().decode("ascii", errors="replace")
            self._record("continue", response)
            return response
        except socket.timeout as exc:
            self.protocol["timeouts"] = int(self.protocol["timeouts"]) + 1
            raise TimeoutError("target did not stop before strict timeout") from exc
        finally:
            sock.settimeout(old_timeout)

    def continue_and_interrupt(self, seconds: float = 0.5) -> str:
        self.continue_running()
        time.sleep(seconds)
        self.protocol["interrupts"] = int(self.protocol["interrupts"]) + 1
        response = self.interrupt(timeout=self.timeout)
        self._record("interrupt", response)
        return response


def snapshot_registers(registers: dict[str, int]) -> dict[str, str]:
    names = {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11", "r12", "sp", "lr", "pc", "cpsr"}
    return {name: f"0x{value:08X}" for name, value in registers.items() if name in names}


def screen_metadata(client: StrictGdbClient) -> dict[str, object]:
    screen, _bg0, _bg1 = read_display_maps(client)
    screen["bg1cnt_direct"] = f"0x{int.from_bytes(client.read_memory(BG1CNT, 2), 'little'):04X}"
    screen["keyboard_tile_hashes"] = {
        "tile1": digest(client.read_memory(TILE1, TILE_BYTES)),
        "tile2": digest(client.read_memory(TILE2, TILE_BYTES)),
    }
    keyboard = screen["keyboard_layout"]
    assert isinstance(keyboard, dict)
    screen["gate_confirmed"] = bool(keyboard["confirmed"])
    screen["tile_hashes_match_known"] = (
        screen["keyboard_tile_hashes"]["tile1"] == KNOWN_TILE1_SHA256
        and screen["keyboard_tile_hashes"]["tile2"] == KNOWN_TILE2_SHA256
    )
    return screen


def gate_status(screen: dict[str, object]) -> bool:
    return bool(screen.get("gate_confirmed")) and bool(screen.get("tile_hashes_match_known"))


def dma_tile_window(
    source: int,
    destination: int,
    count: int,
    control: int,
    *,
    channel: int = 3,
) -> dict[str, int | None]:
    """Decode one DMA setup and locate TILE1 inside its destination window."""

    width = 4 if control & 0x0400 else 2
    units = count or (0x10000 if channel == 3 else 0x4000)
    byte_count = units * width
    offset = None
    source_tile = None
    if destination <= TILE1 and TILE1 + TILE_BYTES <= destination + byte_count:
        offset = TILE1 - destination
        source_tile = source + offset
    return {
        "transfer_width": width,
        "transfer_units": units,
        "byte_count": byte_count,
        "tile_offset": offset,
        "source_tile_address": source_tile,
    }


def interrupt_after_timeout(client: StrictGdbClient) -> dict[str, object]:
    try:
        stop = client.interrupt(timeout=2.0)
        return {"termination": "interrupted", "stop_kind": response_kind(stop)}
    except (TimeoutError, OSError, ConnectionError) as exc:
        return {"termination": "interrupt-failed", "error": type(exc).__name__}


def read_dma3_state(client: StrictGdbClient) -> dict[str, int]:
    return {
        "source": int.from_bytes(client.read_memory(DMA3_SOURCE, 4), "little"),
        "destination": int.from_bytes(client.read_memory(DMA3_DESTINATION, 4), "little"),
        "count": int.from_bytes(client.read_memory(DMA3_COUNT, 2), "little"),
        "control": int.from_bytes(client.read_memory(DMA3_CONTROL, 2), "little"),
    }


def press_button(
    client: StrictGdbClient,
    button: str,
    *,
    event_timeout: float,
    hold_events: int,
    release_events: int,
    transfer: dict[str, object] | None = None,
) -> dict[str, object]:
    """Inject one button, accepting only KEYINPUT or the one target watch."""

    desired = button_value(button)
    events: list[dict[str, object]] = []
    termination = "completed"
    key_armed = False
    target_armed = False
    client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
    key_armed = True
    if transfer is not None and bool(transfer.get("active")):
        client.set_watchpoint(
            int(transfer["watch_address"]),
            kind=int(transfer["watch_kind"]),
            watch_type=2,
        )
        target_armed = True
    try:
        for index in range(hold_events + release_events):
            try:
                stop = client.continue_until_stop(event_timeout)
            except TimeoutError as exc:
                termination = "strict-watch-timeout"
                events.append({"index": index, "error": str(exc), **interrupt_after_timeout(client)})
                break
            kind, address = parse_stop_watch(stop)
            target_address = None if transfer is None else int(transfer["watch_address"])
            dma_setup_addresses = {DMA3_COUNT, DMA3_CONTROL}
            target_hit = (
                address == target_address
                or (
                    transfer is not None
                    and transfer.get("mode") == "dma3"
                    and address in dma_setup_addresses
                )
            )
            if target_hit and transfer is not None and bool(transfer.get("active")):
                # Remove the target before any diagnostic reads: this is the
                # only asset transfer cohort in the run.
                client.remove_watchpoint(
                    target_address,
                    kind=int(transfer["watch_kind"]),
                    watch_type=2,
                )
                target_armed = False
                registers = client.read_registers()
                at_stop = client.read_memory(TILE1, TILE_BYTES)
                transfer["event"] = transfer_receipt(
                    client,
                    registers,
                    at_stop,
                    stop,
                    mode=str(transfer["mode"]),
                )
                transfer["active"] = False
                # Finish the stopped instruction without rearming the target.
                step_response = client.request("s")
                transfer["event"]["post_watch_step_response_kind"] = response_kind(step_response)
                transfer["event"]["tile_sha256_after_step"] = digest(
                    client.read_memory(TILE1, TILE_BYTES)
                )
                if transfer.get("mode") == "dma3":
                    transfer["event"]["dma_state_after_step"] = {
                        key: f"0x{value:08X}" if key in ("source", "destination") else f"0x{value:04X}"
                        for key, value in read_dma3_state(client).items()
                    }
                finalize_transfer_receipt(
                    transfer["event"],
                    transfer["event"]["tile_sha256_after_step"],
                )
                events.append({
                    "index": index,
                    "role": "asset-transfer",
                    "stop_kind": kind,
                    "stop_address": f"0x{address:08X}",
                })
                continue
            if address != KEYINPUT:
                termination = "unexpected-watch-stop"
                events.append({
                    "index": index,
                    "stop_kind": kind,
                    "stop_address": None if address is None else f"0x{address:08X}",
                })
                break
            registers = client.read_registers()
            value = desired if index < hold_events else NO_KEY
            events.append({
                "index": index,
                "role": "keyinput",
                "requested_keyinput": f"0x{value:04X}",
                "stop_kind": kind,
                "stop_address": f"0x{address:08X}",
                "registers": snapshot_registers(registers),
            })
            client.write_register(1, value)
    finally:
        if target_armed:
            assert transfer is not None
            client.remove_watchpoint(
                int(transfer["watch_address"]),
                kind=int(transfer["watch_kind"]),
                watch_type=2,
            )
        if key_armed:
            client.remove_watchpoint(KEYINPUT, kind=2, watch_type=3)
    return {
        "button": button,
        "hold_events": hold_events,
        "release_events": release_events,
        "termination": termination,
        "events": events,
    }


def region(address: int) -> str | None:
    for label, (start, end) in (("rom", ROM), ("ewram", EWRAM), ("iwram", IWRAM)):
        if start <= address < end and address + TILE_BYTES <= end:
            return label
    return None


def transfer_receipt(
    client: StrictGdbClient,
    registers: dict[str, int],
    at_stop: bytes,
    stop: str,
    *,
    mode: str,
) -> dict[str, object]:
    if mode == "dma3":
        state = read_dma3_state(client)
        source = state["source"]
        destination = state["destination"]
        count = state["count"]
        control = state["control"]
        window = dma_tile_window(source, destination, count, control)
        source_tile_address = window["source_tile_address"]
        source_region = None if source_tile_address is None else region(source_tile_address)
        source_hash = None
        if source_tile_address is not None and source_region is not None:
            try:
                source_hash = digest(client.read_memory(source_tile_address, TILE_BYTES))
            except (ProtocolBoundary, RuntimeError, ValueError):
                source_hash = None
        return {
            "mechanism": "DMA3-control-write-watch",
            "watch_address": f"0x{DMA3_CONTROL:08X}",
            "destination": f"0x{destination:08X}",
            "source_pointer": f"0x{source:08X}",
            "count_units": count,
            "control": f"0x{control:04X}",
            "transfer_width": window["transfer_width"],
            "byte_count": window["byte_count"],
            "tile_offset": window["tile_offset"],
            "source_tile_address": (
                None
                if source_tile_address is None
                else f"0x{source_tile_address:08X}"
            ),
            "source_region": source_region,
            "source_tile_sha256": source_hash,
            "tile_sha256_at_stop": digest(at_stop),
            "tile_sha256_after_step": None,
            "writer_pc": f"0x{registers['pc']:08X}",
            "caller_lr": f"0x{registers['lr']:08X}",
            "stop_kind": parse_stop_watch(stop)[0],
            "reset_stage_hash": RESET_TILE1_SHA256,
            "is_reset_stage_hash": digest(at_stop) == RESET_TILE1_SHA256,
            "source_candidates": [],
            "byte_identical_source_matches": [],
            "source_match_count": 0,
            "source_status": "pending-after-step-hash",
            "enable_at_watch": bool(control & 0x8000),
        }
    tile_hash = digest(at_stop)
    candidates: list[dict[str, object]] = []
    for register, value in registers.items():
        address = value & ~1
        region_name = region(address)
        if region_name is None:
            continue
        try:
            source = client.read_memory(address, TILE_BYTES)
        except (ProtocolBoundary, RuntimeError, ValueError):
            continue
        source_hash = digest(source)
        candidates.append({
            "register": register,
            "address": f"0x{address:08X}",
            "region": region_name,
            "sha256": source_hash,
            "byte_identical_to_destination": source_hash == tile_hash,
        })
    matches = [item for item in candidates if item["byte_identical_to_destination"]]
    return {
        "mechanism": "CPU-or-BIOS-write-watch",
        "destination": f"0x{TILE1:08X}",
        "byte_count": TILE_BYTES,
        "writer_pc": f"0x{registers['pc']:08X}",
        "caller_lr": f"0x{registers['lr']:08X}",
        "stop_kind": parse_stop_watch(stop)[0],
        "tile_sha256_at_stop": tile_hash,
        "tile_sha256_after_step": None,
        "reset_stage_hash": RESET_TILE1_SHA256,
        "is_reset_stage_hash": tile_hash == RESET_TILE1_SHA256,
        "source_candidates": candidates,
        "byte_identical_source_matches": matches,
        "source_match_count": len(matches),
        "source_status": "byte-identical-candidate" if matches else "unknown",
    }


def finalize_transfer_receipt(event: dict[str, object], after_hash: object) -> None:
    """Compare the source slice against the completed VRAM tile exactly once."""

    if not isinstance(after_hash, str):
        return
    event["tile_sha256_after_step"] = after_hash
    source_hash = event.get("source_tile_sha256")
    if source_hash is not None and source_hash == after_hash:
        event["byte_identical_source_matches"] = [
            {
                "source_tile_address": event.get("source_tile_address"),
                "source_region": event.get("source_region"),
                "sha256": source_hash,
            }
        ]
        event["source_match_count"] = 1
        event["source_status"] = "byte-identical-to-vram-after-step"
    elif source_hash is not None:
        event["source_status"] = "source-hash-differs-from-vram-after-step"


def refresh_dma3_receipt(
    client: StrictGdbClient,
    event: dict[str, object],
    tile_hash: str,
) -> None:
    """Record post-settle DMA state without rearming any watchpoint."""

    state = read_dma3_state(client)
    window = dma_tile_window(
        state["source"],
        state["destination"],
        state["count"],
        state["control"],
    )
    source_tile = window["source_tile_address"]
    source_hash = None
    source_region = None if source_tile is None else region(source_tile)
    if source_tile is not None and source_region is not None:
        try:
            source_hash = digest(client.read_memory(source_tile, TILE_BYTES))
        except (ProtocolBoundary, RuntimeError, ValueError):
            source_hash = None
    event["dma_state_after_settle"] = {
        key: f"0x{value:08X}" if key in ("source", "destination") else f"0x{value:04X}"
        for key, value in state.items()
    }
    event["tile_sha256_after_settle"] = tile_hash
    event["source_tile_address_after_settle"] = (
        None if source_tile is None else f"0x{source_tile:08X}"
    )
    event["source_tile_sha256_after_settle"] = source_hash
    event["enable_after_settle"] = bool(state["control"] & 0x8000)
    if source_hash is not None and source_hash == tile_hash and bool(state["control"] & 0x8000):
        event["byte_identical_source_matches"] = [{
            "source_tile_address": event["source_tile_address_after_settle"],
            "source_region": source_region,
            "sha256": source_hash,
        }]
        event["source_match_count"] = 1
        event["source_status"] = "byte-identical-to-vram-after-settle"


def attach_capture(report: dict[str, object], client: StrictGdbClient, dump_dir: Path) -> None:
    try:
        report["core_capture"] = capture(
            client,
            run_seconds=0.05,
            breakpoint=None,
            breakpoint_timeout=1.0,
            watchpoint=None,
            watch_length=4,
            watch_type=2,
            watch_timeout=1.0,
            dump_dir=dump_dir,
        )
    except (ProtocolBoundary, RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
        report["core_capture"] = {"status": "not-collected", "error": type(exc).__name__}


def common_report(args: argparse.Namespace) -> dict[str, object]:
    return {
        "format": "m19-gate-transfer-v1",
        "mode": args.mode,
        "rom": identity(args.rom),
        "port": args.port,
        "navigation_sequence": args.navigation,
        "single_connection": True,
        "cohort_policy": "KEYINPUT only for gate; KEYINPUT plus one TILE1 write watch only for final transfer",
        "reset_tile1_sha256": RESET_TILE1_SHA256,
        "known_keyboard_tile1_sha256": KNOWN_TILE1_SHA256,
        "known_keyboard_tile2_sha256": KNOWN_TILE2_SHA256,
    }


def run_gate(args: argparse.Namespace) -> dict[str, object]:
    report = common_report(args)
    report["max_navigation_steps"] = args.max_steps
    report["clean_protocol"] = False
    client = StrictGdbClient(
        args.host,
        args.port,
        timeout=args.timeout,
        packet_delay=args.packet_delay,
        retry_delay=args.retry_delay,
    )
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop_kind"] = response_kind(client.request("?"))
        report["initial_registers"] = snapshot_registers(client.read_registers())
        report["settle_stop_kind"] = response_kind(client.continue_and_interrupt(args.settle_seconds))
        screens: list[dict[str, object]] = [screen_metadata(client)]
        starts: list[dict[str, object]] = []
        for _index, button in enumerate(args.navigation[:args.max_steps]):
            step = press_button(
                client,
                button,
                event_timeout=args.event_timeout,
                hold_events=args.hold_events,
                release_events=args.release_events,
            )
            step["settle_stop_kind"] = response_kind(
                client.continue_and_interrupt(args.step_settle_seconds)
            )
            step["screen"] = screen_metadata(client)
            starts.append(step)
            screens.append(step["screen"])
            if gate_status(step["screen"]):
                break
        confirmed_index = next(
            (index for index, screen in enumerate(screens) if gate_status(screen)),
            None,
        )
        report["pre_and_start_screens"] = screens
        report["starts"] = starts
        report["gate_confirmed"] = confirmed_index is not None
        gate_step_index = None if confirmed_index is None else confirmed_index - 1
        report["gate_step_index"] = gate_step_index
        report["gate_button"] = (
            None
            if gate_step_index is None
            else args.navigation[gate_step_index]
        )
        report["start_count"] = (
            None
            if gate_step_index is None
            else sum(button == "start" for button in args.navigation[:gate_step_index + 1])
        )
        report["clean_protocol"] = True
        if report["gate_confirmed"]:
            attach_capture(report, client, args.dump_dir)
    except (ProtocolBoundary, RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
        report["termination"] = type(exc).__name__
        report["error"] = str(exc)
    finally:
        report["protocol"] = client.protocol
        client.close()
    return report


def run_transfer(args: argparse.Namespace) -> dict[str, object]:
    report = common_report(args)
    report["transfer_index"] = args.transfer_index
    report["asset_watch"] = args.asset_watch
    report["clean_protocol"] = False
    if args.asset_watch == "tile1":
        watch_address = TILE1
        watch_kind = TILE_BYTES
    else:
        watch_address = DMA3_CONTROL
        watch_kind = 2
    transfer: dict[str, object] = {
        "active": False,
        "event": None,
        "mode": args.asset_watch,
        "watch_address": watch_address,
        "watch_kind": watch_kind,
    }
    client = StrictGdbClient(
        args.host,
        args.port,
        timeout=args.timeout,
        packet_delay=args.packet_delay,
        retry_delay=args.retry_delay,
    )
    try:
        if not 0 <= args.transfer_index < len(args.navigation):
            raise ValueError("transfer-index must select a button in the bounded sequence")
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop_kind"] = response_kind(client.request("?"))
        report["initial_registers"] = snapshot_registers(client.read_registers())
        report["settle_stop_kind"] = response_kind(client.continue_and_interrupt(args.settle_seconds))
        report["pre_screen"] = screen_metadata(client)
        steps: list[dict[str, object]] = []
        for index, button in enumerate(args.navigation[:args.transfer_index + 1]):
            final_transition = index == args.transfer_index
            if final_transition:
                transfer["active"] = True
            step = press_button(
                client,
                button,
                event_timeout=args.event_timeout,
                hold_events=args.hold_events,
                release_events=args.release_events,
                transfer=transfer if final_transition else None,
            )
            step["final_transition"] = final_transition
            step["settle_stop_kind"] = response_kind(
                client.continue_and_interrupt(args.step_settle_seconds)
            )
            if final_transition and transfer.get("mode") == "dma3" and isinstance(transfer.get("event"), dict):
                transfer_event = transfer["event"]
                assert isinstance(transfer_event, dict)
                refresh_dma3_receipt(
                    client,
                    transfer_event,
                    digest(client.read_memory(TILE1, TILE_BYTES)),
                )
            if final_transition:
                if bool(transfer.get("active")):
                    client.remove_watchpoint(
                        int(transfer["watch_address"]),
                        kind=int(transfer["watch_kind"]),
                        watch_type=2,
                    )
                    transfer["active"] = False
                step["screen"] = screen_metadata(client)
            else:
                step["screen"] = screen_metadata(client)
            steps.append(step)
        report["steps"] = steps
        report["transfer"] = transfer
        final_screen = steps[-1]["screen"]
        report["gate_confirmed"] = gate_status(final_screen)
        event = transfer.get("event")
        report["confirmed_transfer"] = bool(
            report["gate_confirmed"]
            and isinstance(event, dict)
            and event.get("tile_sha256_after_step") == KNOWN_TILE1_SHA256
            and int(event.get("source_match_count", 0)) > 0
        )
        report["clean_protocol"] = True
        if report["gate_confirmed"]:
            attach_capture(report, client, args.dump_dir)
    except (ProtocolBoundary, RuntimeError, TimeoutError, OSError, ConnectionError, ValueError) as exc:
        report["termination"] = type(exc).__name__
        report["error"] = str(exc)
    finally:
        report["protocol"] = client.protocol
        client.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--mode", choices=("gate", "transfer"), default="gate")
    parser.add_argument("--transfer-index", type=int, default=2)
    parser.add_argument("--asset-watch", choices=("tile1", "dma3"), default="tile1")
    parser.add_argument("--sequence", default="start,start,a")
    parser.add_argument("--max-steps", type=int, default=3)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--packet-delay", type=float, default=0.12)
    parser.add_argument("--retry-delay", type=float, default=0.5)
    parser.add_argument("--settle-seconds", type=float, default=5.0)
    parser.add_argument("--step-settle-seconds", type=float, default=1.0)
    parser.add_argument("--event-timeout", type=float, default=3.0)
    parser.add_argument("--hold-events", type=int, default=18)
    parser.add_argument("--release-events", type=int, default=6)
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        args.navigation = parse_sequence(args.sequence)
    except ValueError as exc:
        parser.error(str(exc))
    if args.max_steps < 0 or args.max_steps > 3:
        parser.error("max-steps must be between 0 and 3")
    if args.mode == "transfer" and not 0 <= args.transfer_index < len(args.navigation):
        parser.error("transfer-index must select a button in the bounded sequence")
    report: dict[str, object]
    try:
        report = run_gate(args) if args.mode == "gate" else run_transfer(args)
    except (ValueError, OSError, RuntimeError) as exc:
        report = {"format": "m19-gate-transfer-v1", "mode": args.mode, "termination": type(exc).__name__, "error": str(exc)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "mode": args.mode,
        "clean_protocol": report.get("clean_protocol", False),
        "gate_confirmed": report.get("gate_confirmed", False),
        "confirmed_transfer": report.get("confirmed_transfer", False),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
