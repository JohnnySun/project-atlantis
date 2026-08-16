"""Execute bounded runtime cases over one mGBA GDB remote connection."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from ..gdbstub_client import GdbClient, REG_NAMES, parse_stop_watch
from ..render_oam import composite_oam, load_obj_palette
from ..render_vram import load_palette, render_bg_tilemap, render_mode3
from .manifest import ManifestError, integer
from .result import Report


KEYINPUT = 0x04000130
IO_REGISTERS = {
    "DISPCNT": (0x04000000, 2),
    "VCOUNT": (0x04000006, 2),
    "BG0CNT": (0x04000008, 2),
    "BG1CNT": (0x0400000A, 2),
    "BG2CNT": (0x0400000C, 2),
    "BG3CNT": (0x0400000E, 2),
    "KEYINPUT": (KEYINPUT, 2),
}
KEY_BITS = {
    "A": 0,
    "B": 1,
    "SELECT": 2,
    "START": 3,
    "RIGHT": 4,
    "LEFT": 5,
    "UP": 6,
    "DOWN": 7,
    "R": 8,
    "L": 9,
}
KNOWN_CAPABILITIES = {
    "gdb-remote",
    "register-read",
    "register-write",
    "memory-read",
    "memory-write",
    "breakpoint",
    "watchpoint",
    "keyinput-consumer-hook",
    "render-bg",
    "render-oam",
    "render-mode3",
    "savestate-load-at-launch",
}


class RetryingGdbClient(GdbClient):
    """Retry only initial connection; never reconnect after a session drops."""

    def __init__(self, *args: Any, connect_timeout_seconds: float = 8.0, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.connect_timeout_seconds = connect_timeout_seconds
        self.connect_attempts = 0

    def connect(self) -> None:
        deadline = time.monotonic() + self.connect_timeout_seconds
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            self.connect_attempts += 1
            try:
                super().connect()
                return
            except OSError as exc:
                last_error = exc
                self.close()
                time.sleep(0.25)
        if last_error is not None:
            raise last_error
        raise TimeoutError("mGBA GDB stub did not become ready")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _summary(data: bytes, address: int) -> dict[str, Any]:
    return {
        "address": f"0x{address:08X}",
        "length": len(data),
        "sha256": _sha(data),
        "nonzero_bytes": sum(value != 0 for value in data),
    }


def _rgb_hash(pixels: list[list[tuple[int, int, int]]]) -> tuple[str, int, int, int]:
    height = len(pixels)
    width = len(pixels[0]) if pixels else 0
    raw = bytes(channel for row in pixels for pixel in row for channel in pixel)
    nonzero = sum(value != 0 for value in raw)
    return _sha(raw), width, height, nonzero


def _pixel_receipt(
    pixels: list[list[tuple[int, int, int]]],
    row: dict[str, Any],
    field: str,
) -> dict[str, Any]:
    digest, width, height, nonzero = _rgb_hash(pixels)
    receipt: dict[str, Any] = {
        "sha256": digest,
        "width": width,
        "height": height,
        "nonzero_rgb_bytes": nonzero,
    }
    guard = row.get("clip_guard")
    if guard is None:
        return receipt
    if not isinstance(guard, dict):
        raise ManifestError(f"{field}.clip_guard must be an object")
    x = integer(guard.get("x"), f"{field}.clip_guard.x")
    y = integer(guard.get("y"), f"{field}.clip_guard.y")
    guard_width = integer(guard.get("width"), f"{field}.clip_guard.width")
    guard_height = integer(guard.get("height"), f"{field}.clip_guard.height")
    background = guard.get("background_rgb")
    if (
        not isinstance(background, list)
        or len(background) != 3
        or any(not isinstance(value, int) or not 0 <= value <= 255 for value in background)
    ):
        raise ManifestError(f"{field}.clip_guard.background_rgb must be three bytes")
    if x < 0 or y < 0 or guard_width < 2 or guard_height < 2 or x + guard_width > width or y + guard_height > height:
        raise ManifestError(f"{field}.clip_guard rectangle is outside render bounds")
    background_pixel = tuple(background)
    border = []
    for pixel_x in range(x, x + guard_width):
        border.append(pixels[y][pixel_x])
        border.append(pixels[y + guard_height - 1][pixel_x])
    for pixel_y in range(y + 1, y + guard_height - 1):
        border.append(pixels[pixel_y][x])
        border.append(pixels[pixel_y][x + guard_width - 1])
    receipt["clip_guard"] = {
        "x": x,
        "y": y,
        "width": guard_width,
        "height": guard_height,
        "background_rgb": background,
        "border_non_background_pixels": sum(pixel != background_pixel for pixel in border),
        "policy": "zero means content did not touch the declared clipping boundary",
    }
    return receipt


def _io(client: GdbClient) -> dict[str, Any]:
    return {
        name: {
            "address": f"0x{address:08X}",
            "value": int.from_bytes(client.read_memory(address, length), "little"),
        }
        for name, (address, length) in IO_REGISTERS.items()
    }


def _register_snapshot(client: GdbClient) -> dict[str, str]:
    return {name: f"0x{value:08X}" for name, value in client.read_registers().items()}


def _render(client: GdbClient, row: dict[str, Any], field: str) -> dict[str, Any]:
    kind = row.get("kind")
    vram = client.read_memory(0x06000000, 0x18000)
    if kind == "mode3":
        pixels = render_mode3(vram)
        return {"kind": kind, **_pixel_receipt(pixels, row, field)}
    palette_raw = client.read_memory(0x05000000, 0x400)
    palette = load_palette(palette_raw)
    if kind == "bg":
        bg = integer(row.get("bg"), f"{field}.bg")
        if bg not in range(4):
            raise ManifestError(f"{field}.bg must be 0..3")
        bgcnt = int.from_bytes(client.read_memory(0x04000008 + bg * 2, 2), "little")
        charbase = ((bgcnt >> 2) & 0x3) * 0x4000
        screenbase = ((bgcnt >> 8) & 0x1F) * 0x800
        bpp = 8 if bgcnt & 0x80 else 4
        map_width = integer(row.get("map_width", 32), f"{field}.map_width")
        map_height = integer(row.get("map_height", 32), f"{field}.map_height")
        pixels = render_bg_tilemap(
            vram,
            palette,
            charbase=charbase,
            screenbase=screenbase,
            bpp=bpp,
            map_width=map_width,
            map_height=map_height,
        )
        return {
            "kind": kind,
            "bg": bg,
            "bgcnt": f"0x{bgcnt:04X}",
            "charbase": f"0x{charbase:X}",
            "screenbase": f"0x{screenbase:X}",
            "bpp": bpp,
            **_pixel_receipt(pixels, row, field),
        }
    if kind == "oam":
        oam = client.read_memory(0x07000000, 0x400)
        dispcnt = int.from_bytes(client.read_memory(0x04000000, 2), "little")
        mapping = row.get("mapping", "auto")
        if mapping == "auto":
            mapping = "1d" if dispcnt & 0x40 else "2d"
        if mapping not in ("1d", "2d"):
            raise ManifestError(f"{field}.mapping must be auto, 1d, or 2d")
        obj_palette = load_obj_palette(palette_raw)
        pixels, visible_objects = composite_oam(vram, obj_palette, oam, mapping_1d=mapping == "1d")
        return {
            "kind": kind,
            "mapping": mapping,
            "visible_objects": visible_objects,
            **_pixel_receipt(pixels, row, field),
        }
    raise ManifestError(f"{field}.kind is unsupported: {kind!r}")


def _capture(client: GdbClient, action: dict[str, Any], field: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "registers": _register_snapshot(client),
        "io": _io(client),
        "regions": {},
        "renders": {},
    }
    for index, row in enumerate(action.get("regions", [])):
        if not isinstance(row, dict):
            raise ManifestError(f"{field}.regions[{index}] must be an object")
        region_id = str(row.get("id", f"region-{index}"))
        address = integer(row.get("address"), f"{field}.regions[{index}].address")
        length = integer(row.get("length"), f"{field}.regions[{index}].length")
        if length <= 0 or length > 0x40000:
            raise ManifestError(f"{field}.regions[{index}].length must be 1..0x40000")
        snapshot["regions"][region_id] = _summary(client.read_memory(address, length), address)
    for index, row in enumerate(action.get("renders", [])):
        if not isinstance(row, dict):
            raise ManifestError(f"{field}.renders[{index}] must be an object")
        render_id = str(row.get("id", f"render-{index}"))
        snapshot["renders"][render_id] = _render(client, row, f"{field}.renders[{index}]")
    return snapshot


def _key_value(keys: list[Any]) -> int:
    value = 0x3FF
    for raw in keys:
        name = str(raw).upper()
        if name not in KEY_BITS:
            raise ManifestError(f"unknown GBA key: {raw!r}")
        value &= ~(1 << KEY_BITS[name])
    return value


def _press_keys(client: GdbClient, action: dict[str, Any], field: str) -> dict[str, Any]:
    register_name = str(action.get("destination_register"))
    if register_name not in REG_NAMES:
        raise ManifestError(f"{field}.destination_register is invalid")
    register_number = REG_NAMES.index(register_name)
    hold_reads = integer(action.get("hold_reads", 1), f"{field}.hold_reads")
    release_reads = integer(action.get("release_reads", 1), f"{field}.release_reads")
    timeout = float(action.get("per_read_timeout_seconds", 5.0))
    pressed = _key_value(action.get("keys", []))
    events: list[dict[str, Any]] = []
    client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
    try:
        for index in range(hold_reads + release_reads):
            stop = client.continue_until_stop(timeout)
            watch_kind, address = parse_stop_watch(stop)
            if address is None or not KEYINPUT <= address < KEYINPUT + 2:
                raise RuntimeError(f"input hook stopped outside KEYINPUT: {stop!r}")
            value = pressed if index < hold_reads else 0x3FF
            registers = client.read_registers()
            client.write_register(register_number, value)
            events.append({
                "read_index": index,
                "phase": "hold" if index < hold_reads else "release",
                "stop_kind": watch_kind,
                "stop_address": f"0x{address:08X}",
                "pc": f"0x{registers['pc']:08X}",
                "injected_register": register_name,
                "active_low_value": f"0x{value:03X}",
            })
    finally:
        client.remove_watchpoint(KEYINPUT, kind=2, watch_type=3)
    return {
        "method": "keyinput-consumer-hook",
        "keys": [str(key).upper() for key in action.get("keys", [])],
        "hold_reads": hold_reads,
        "release_reads": release_reads,
        "events": events,
    }


def _condition_value(client: GdbClient, condition: dict[str, Any], field: str) -> tuple[int, int, int]:
    kind = condition.get("kind", "memory-equals")
    if kind != "memory-equals":
        raise ManifestError(f"{field}.kind only supports memory-equals")
    address = integer(condition.get("address"), f"{field}.address")
    length = integer(condition.get("length", 2), f"{field}.length")
    if length not in (1, 2, 4):
        raise ManifestError(f"{field}.length must be 1, 2, or 4")
    expected = integer(condition.get("value"), f"{field}.value")
    mask = integer(condition.get("mask", (1 << (length * 8)) - 1), f"{field}.mask")
    actual = int.from_bytes(client.read_memory(address, length), "little")
    return actual, expected, mask


def _wait_until(client: GdbClient, action: dict[str, Any], field: str) -> dict[str, Any]:
    timeout = float(action.get("timeout_seconds", 10.0))
    slice_seconds = float(action.get("slice_seconds", 0.25))
    if timeout <= 0 or slice_seconds <= 0:
        raise ManifestError(f"{field} timeout and slice must be positive")
    deadline = time.monotonic() + timeout
    samples: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        client.continue_and_interrupt(min(slice_seconds, max(0.01, deadline - time.monotonic())))
        actual, expected, mask = _condition_value(client, action.get("condition", {}), f"{field}.condition")
        samples.append({"actual": f"0x{actual:X}", "masked": f"0x{actual & mask:X}"})
        if actual & mask == expected & mask:
            return {"matched": True, "expected": f"0x{expected:X}", "mask": f"0x{mask:X}", "samples": samples}
    return {"matched": False, "expected": f"0x{expected:X}", "mask": f"0x{mask:X}", "samples": samples}


def _allowed_write(address: int, length: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= address and address + length - 1 <= end for start, end in ranges)


def _write_ranges(runtime: dict[str, Any]) -> list[tuple[int, int]]:
    output = []
    for index, row in enumerate(runtime.get("controlled_write_ranges", [])):
        if not isinstance(row, list) or len(row) != 2:
            raise ManifestError(f"runtime.controlled_write_ranges[{index}] must be [start,end]")
        output.append((integer(row[0], "controlled write start"), integer(row[1], "controlled write end")))
    return output


def _path(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def _assertions(report: Report, snapshots: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows):
        kind = row.get("kind")
        assertion_id = str(row.get("id", f"assertion-{index}"))
        try:
            if kind in ("changed", "unchanged"):
                before = _path(snapshots[row["before"]], str(row["path"]))
                after = _path(snapshots[row["after"]], str(row["path"]))
                matched = (before != after) if kind == "changed" else (before == after)
                report.add(
                    "pass" if matched else "fail",
                    f"runtime.assertion.{kind}",
                    f"assertion {assertion_id} passed" if matched else f"assertion {assertion_id} failed",
                    assertion=assertion_id,
                    before=before,
                    after=after,
                )
            elif kind == "equals":
                actual = _path(snapshots[row["snapshot"]], str(row["path"]))
                expected = row.get("value")
                if isinstance(actual, int):
                    expected = integer(expected, f"runtime.assertions[{index}].value")
                matched = actual == expected
                report.add(
                    "pass" if matched else "fail",
                    "runtime.assertion.equals",
                    f"assertion {assertion_id} passed" if matched else f"assertion {assertion_id} failed",
                    assertion=assertion_id,
                    actual=actual,
                    expected=expected,
                )
            elif kind == "positive":
                actual = _path(snapshots[row["snapshot"]], str(row["path"]))
                matched = isinstance(actual, int) and actual > 0
                report.add(
                    "pass" if matched else "fail",
                    "runtime.assertion.positive",
                    f"assertion {assertion_id} passed" if matched else f"assertion {assertion_id} failed",
                    assertion=assertion_id,
                    actual=actual,
                )
            else:
                report.add("unknown", "runtime.assertion.unsupported", f"assertion {assertion_id} uses unsupported kind", kind=kind)
        except (KeyError, TypeError, ManifestError, ValueError) as exc:
            report.add("unknown", "runtime.assertion.missing_evidence", f"assertion {assertion_id} could not be evaluated", error=str(exc))


def run_runtime(
    manifest: dict[str, Any],
    host: str,
    port: int,
    rom_path: Path | None = None,
) -> Report:
    report = Report("runtime")
    runtime = manifest.get("runtime", {})
    required = runtime.get("required_capabilities", [])
    unknown_capabilities = sorted(set(required) - KNOWN_CAPABILITIES)
    for capability in unknown_capabilities:
        report.add("unknown", "runtime.capability.unknown", f"unknown required capability: {capability}")
    snapshots: dict[str, Any] = {}
    actions_evidence: list[dict[str, Any]] = []
    exercised = set()
    target_stopped = True
    try:
        if rom_path is not None:
            rom_data = rom_path.read_bytes()
            expected_hash = manifest["rom"]["sha256"]
            actual_hash = _sha(rom_data)
            expected_size = manifest["rom"].get("size")
            size_matches = expected_size is None or len(rom_data) == integer(expected_size, "rom.size")
            report.evidence["rom"] = {
                "path": str(rom_path),
                "sha256": actual_hash,
                "size": len(rom_data),
                "game_code_hex": rom_data[0xAC:0xB0].hex() if len(rom_data) >= 0xB0 else None,
            }
            if actual_hash != expected_hash or not size_matches:
                report.add(
                    "fail",
                    "runtime.rom.identity",
                    "runtime ROM does not match manifest; connection skipped",
                    expected_sha256=expected_hash,
                    actual_sha256=actual_hash,
                    size_matches=size_matches,
                )
                report.evidence["actions"] = []
                report.evidence["snapshots"] = {}
                return report
            report.add("pass", "runtime.rom.identity", "runtime ROM identity matches manifest")
        ranges = _write_ranges(runtime)
        with RetryingGdbClient(
            host=host,
            port=port,
            timeout=float(runtime.get("gdb_timeout_seconds", 8.0)),
            connect_timeout_seconds=float(runtime.get("connect_timeout_seconds", 8.0)),
        ) as client:
            supported = client.request("qSupported:multiprocess+")
            initial_stop = client.request("?")
            report.evidence["connection"] = {
                "host": host,
                "port": port,
                "q_supported": supported,
                "initial_stop": initial_stop,
                "single_connection": True,
                "connect_attempts": client.connect_attempts,
            }
            report.add("pass", "runtime.capability.gdb_remote", "connected to one mGBA GDB remote session")
            exercised.add("gdb-remote")
            initial_registers = client.read_registers()
            initial_dispcnt = client.read_memory(0x04000000, 2)
            report.evidence["capability_probe"] = {
                "register_count": len(initial_registers),
                "dispcnt_hex": initial_dispcnt.hex(),
            }
            exercised.update({"register-read", "memory-read"})
            for index, action in enumerate(runtime.get("actions", [])):
                if not isinstance(action, dict):
                    raise ManifestError(f"runtime.actions[{index}] must be an object")
                field = f"runtime.actions[{index}]"
                op = action.get("op")
                action_id = str(action.get("id", f"action-{index}"))
                row: dict[str, Any] = {"id": action_id, "op": op}
                if op == "wait_until":
                    result = _wait_until(client, action, field)
                    row["result"] = result
                    report.add(
                        "pass" if result["matched"] else "fail",
                        "runtime.wait_until",
                        f"condition {action_id} matched" if result["matched"] else f"condition {action_id} timed out",
                    )
                elif op == "run":
                    seconds = float(action.get("seconds", 0.1))
                    if seconds <= 0:
                        raise ManifestError(f"{field}.seconds must be positive")
                    row["stop"] = client.continue_and_interrupt(seconds)
                elif op == "keys":
                    row["result"] = _press_keys(client, action, field)
                    exercised.update({"register-write", "watchpoint", "keyinput-consumer-hook"})
                    report.add("pass", "runtime.input.keyinput_hook", f"input action {action_id} injected through observed KEYINPUT reads")
                elif op == "capture":
                    snapshot = _capture(client, action, field)
                    exercised.update({"register-read", "memory-read"})
                    for render in action.get("renders", []):
                        exercised.add(f"render-{render.get('kind')}")
                    snapshots[action_id] = snapshot
                    row["snapshot"] = snapshot
                elif op == "breakpoint":
                    address = integer(action.get("address"), f"{field}.address")
                    client.set_breakpoint(address)
                    try:
                        stop = client.continue_until_stop(float(action.get("timeout_seconds", 10.0)))
                        register_values = client.read_registers()
                        registers = {name: f"0x{value:08X}" for name, value in register_values.items()}
                    finally:
                        client.remove_breakpoint(address)
                    row.update({"address": f"0x{address:08X}", "stop": stop, "registers": registers})
                    register_regions = []
                    for region_index, region in enumerate(action.get("register_regions", [])):
                        region_field = f"{field}.register_regions[{region_index}]"
                        if not isinstance(region, dict):
                            raise ManifestError(f"{region_field} must be an object")
                        register_name = str(region.get("register"))
                        if register_name not in register_values:
                            raise ManifestError(f"{region_field}.register is invalid")
                        region_offset = integer(region.get("offset", 0), f"{region_field}.offset")
                        region_length = integer(region.get("length"), f"{region_field}.length")
                        if region_length <= 0 or region_length > 0x40000:
                            raise ManifestError(f"{region_field}.length must be 1..0x40000")
                        region_address = register_values[register_name] + region_offset
                        register_regions.append({
                            "id": str(region.get("id", f"register-region-{region_index}")),
                            "register": register_name,
                            **_summary(client.read_memory(region_address, region_length), region_address),
                        })
                    if register_regions:
                        row["register_regions"] = register_regions
                    report.add("pass", "runtime.breakpoint.hit", f"breakpoint {action_id} was observed")
                    exercised.add("breakpoint")
                elif op == "watchpoint":
                    address = integer(action.get("address"), f"{field}.address")
                    length = integer(action.get("length", 1), f"{field}.length")
                    watch_type = integer(action.get("watch_type", 2), f"{field}.watch_type")
                    client.set_watchpoint(address, kind=length, watch_type=watch_type)
                    try:
                        stop = client.continue_until_stop(float(action.get("timeout_seconds", 10.0)))
                        watch_kind, stop_address = parse_stop_watch(stop)
                        registers = _register_snapshot(client)
                    finally:
                        client.remove_watchpoint(address, kind=length, watch_type=watch_type)
                    row.update({
                        "requested_address": f"0x{address:08X}",
                        "stop": stop,
                        "stop_kind": watch_kind,
                        "stop_address": None if stop_address is None else f"0x{stop_address:08X}",
                        "registers": registers,
                    })
                    report.add(
                        "pass" if stop_address is not None else "unknown",
                        "runtime.watchpoint.hit",
                        f"watchpoint {action_id} was observed" if stop_address is not None else f"watchpoint {action_id} stop was not classifiable",
                    )
                    exercised.add("watchpoint")
                elif op == "step":
                    row["stop"] = client.request("s")
                elif op == "write_register":
                    if action.get("controlled") is not True:
                        raise ManifestError(f"{field} must set controlled=true")
                    name = str(action.get("register"))
                    if name not in REG_NAMES:
                        raise ManifestError(f"{field}.register is invalid")
                    value = integer(action.get("value"), f"{field}.value")
                    client.write_register(REG_NAMES.index(name), value)
                    exercised.add("register-write")
                    row.update({"provenance": "controlled-register-injection", "register": name, "value": f"0x{value:08X}"})
                    report.add("pass", "runtime.controlled.register_write", f"controlled register injection {action_id} completed")
                elif op == "write_memory":
                    if action.get("controlled") is not True:
                        raise ManifestError(f"{field} must set controlled=true")
                    address = integer(action.get("address"), f"{field}.address")
                    try:
                        data = bytes.fromhex(str(action.get("data_hex", "")))
                    except ValueError as exc:
                        raise ManifestError(f"{field}.data_hex is invalid") from exc
                    if not data or not _allowed_write(address, len(data), ranges):
                        raise ManifestError(f"{field} write is outside controlled_write_ranges")
                    before = client.read_memory(address, len(data))
                    client.write_memory(address, data)
                    exercised.add("memory-write")
                    after = client.read_memory(address, len(data))
                    row.update({
                        "provenance": "controlled-memory-injection",
                        "address": f"0x{address:08X}",
                        "length": len(data),
                        "before_sha256": _sha(before),
                        "after_sha256": _sha(after),
                        "readback_matches": after == data,
                    })
                    report.add(
                        "pass" if after == data else "fail",
                        "runtime.controlled.memory_write",
                        f"controlled memory injection {action_id} read back" if after == data else f"controlled memory injection {action_id} readback mismatch",
                    )
                else:
                    report.add("unknown", "runtime.action.unsupported", f"action {action_id} uses unsupported op", op=op)
                actions_evidence.append(row)
            _assertions(report, snapshots, runtime.get("assertions", []))
    except (OSError, TimeoutError, ConnectionError, RuntimeError, ManifestError, ValueError) as exc:
        report.add("unknown", "runtime.execution", str(exc), target_stopped=target_stopped)
    for capability in sorted(set(required) - exercised - set(unknown_capabilities)):
        report.add(
            "unknown",
            "runtime.capability.unproven",
            f"required capability was not exercised: {capability}",
        )
    report.evidence["capabilities"] = {
        "required": required,
        "exercised": sorted(exercised),
        "unproven": sorted(set(required) - exercised),
    }
    report.evidence["actions"] = actions_evidence
    report.evidence["snapshots"] = snapshots
    return report
