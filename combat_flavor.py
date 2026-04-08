from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CombatFrame:
    title: str
    lines: tuple[str, ...]
    tone: str = "cyan"
    delay: float = 0.08


def _lane_label(target: str | None) -> str:
    if not target or target == "---":
        return "route-wide"
    return f"[{str(target).upper()}]"


def _service_hint(enemy, target: str | None) -> str:
    if not target or target == "---":
        return "shared host surface"
    target = str(target).upper()
    if not hasattr(enemy, "subsystems") or target not in enemy.subsystems:
        return "surface unresolved"
    if not getattr(enemy, "topology_revealed", False):
        return "surface unresolved"
    summary = enemy.get_service_summary(target)
    return summary if summary else "surface unresolved"


def _script_tone(kind: str) -> str:
    return {
        "scan": "cyan",
        "brute_force": "yellow",
        "exploit": "magenta",
        "utility": "green",
        "item": "green",
    }.get(kind, "white")


def _flag_flavor_lines(flag_notes: list[str]) -> list[str]:
    lines: list[str] = []
    for note in flag_notes:
        raw = note.split("->", 1)[1].strip() if "->" in note else note.strip()
        raw = raw.rstrip(".")
        lines.append(raw)
    return lines or ["no wrappers armed"]


def _stream_frames(
    title: str,
    header_lines: list[str],
    stream_lines: list[str],
    *,
    tone: str,
    tail_size: int = 12,
    step_delay: float = 0.05,
    final_delay: float = 0.18,
) -> list[CombatFrame]:
    frames: list[CombatFrame] = []
    visible: list[str] = []
    for index, line in enumerate(stream_lines):
        visible.append(line)
        lines = list(header_lines)
        lines.append("")
        lines.extend(visible[-tail_size:])
        frames.append(
            CombatFrame(
                title=title,
                lines=tuple(lines),
                tone=tone,
                delay=final_delay if index == len(stream_lines) - 1 else step_delay,
            )
        )
    return frames


def _wrapper_stream_lines(flag_notes: list[str], target: str | None) -> list[str]:
    lane = _lane_label(target)
    stream: list[str] = []
    for index, note in enumerate(_flag_flavor_lines(flag_notes), start=1):
        stream.extend(
            [
                f"wrapper[{index:02d}] linked :: {lane}",
                f"modifier live :: {note}",
                f"envelope sealed :: wrapper[{index:02d}] ready",
            ]
        )
    return stream


def _script_stream_lines(command_id: str, target: str | None, enemy, meta: dict) -> list[str]:
    lane = _lane_label(target)
    service = _service_hint(enemy, target)
    host = enemy.get_visible_name().split("[")[0].strip().lower().replace(" ", "_")

    library = {
        "ping": [
            "icmp socket up",
            f"echo burst out :: {lane}",
            "latency smear captured",
            "rtt histogram widening",
            "return path indexed",
            "timing mark cached",
            "probe socket closed",
        ],
        "nmap": [
            "syn workers online",
            f"banner sweep :: {service}",
            "port states resolving",
            "dossier cache updated",
            "scan workers down",
        ],
        "enum": [
            "enum workers attached",
            f"runtime scrape :: {lane}",
            "scheduler drift compared",
            "intent model tightening",
            "telemetry sealed",
        ],
        "whois": [
            "rir path queried",
            "registrant trail returning",
            "allocation trail cross-linked",
            "owner profile cached",
        ],
        "dirb": [
            f"path walker mounted :: {lane}",
            "dead endpoints dropped",
            "live paths answering back",
            "interesting hits pinned",
        ],
        "airmon-ng": [
            "monitor mode engaged",
            "perimeter watchers slipping",
            "side-channel traffic captured",
            "breach window open",
        ],
        "hydra": [
            "auth workers forked",
            "credential spray cycling",
            "reuse corpus loaded",
            "lockout counters drifting",
            "challenge prompts desyncing",
            "weak auth path wobbling",
            "breach pressure holding",
        ],
        "ddos": [
            "bot 1 connected",
            "bot 2 connected",
            "bot 3 connected",
            "flood mesh pinned",
            f"transit pressure spikes :: {lane}",
            "queue depth exploding",
            "upstream buffers choking",
        ],
        "sqlmap": [
            "parameter set injected",
            "error surface widening",
            "backend fingerprint locked",
            "response parser harvesting faults",
            "exfil handle cracked",
            "injection window recorded",
        ],
        "spray": [
            f"spray fan out :: {lane}",
            "credential reuse surfacing",
            "login surface softening",
            "hydra window widening",
        ],
        "shred": [
            "wipe routine mounted",
            "journals tearing loose",
            "restore confidence collapsing",
            "repair posture degrading",
        ],
        "overflow": [
            "malformed writes injected",
            "allocator posture slipping",
            "heap canaries burning",
            "heap pressure destabilized",
            "guard pages turning noisy",
            "corruption spill armed",
        ],
        "hammer": [
            "crash harness armed",
            "panic thresholds climbing",
            "watchdog escalation live",
            "watchdogs screaming",
            "kernel fences splitting",
            "surface stability failing",
        ],
        "spoof": [
            "traffic cadence shifted",
            "false profile pushed forward",
            "heuristics biting the decoy",
        ],
        "harden": [
            "acl shell compiling",
            f"policy edges tighten :: {lane}",
            "defensive shell locked",
        ],
        "honeypot": [
            "fake services seeded",
            "telemetry beacons planted",
            "decoy surface holding",
        ],
        "canary": [
            f"watchpoint armed :: {lane}",
            "trap route sleeping",
            "callback waiting hot",
        ],
        "sinkhole": [
            "return path opened",
            f"hostile route bent :: {lane}",
            "redirect path live",
        ],
        "rekey": [
            "session material rotated",
            "stale handles revoked",
            "host cache dirtied",
        ],
        "patch": [
            "maintenance lane opened",
            "runtime stitched closed",
            "fault counters falling",
            "quick-fix cycle committed",
        ],
    }

    if meta.get("kind") == "item":
        item_name = meta.get("name", "field kit")
        return [
            f"unlock field kit :: {item_name}",
            f"deploy single-use payload toward {lane}",
            "consumable state committed into the live rig profile",
        ]

    return library.get(
        command_id,
        [
            "payload threads spawned",
            f"surface answers :: {service}",
            "impact window resolving",
        ],
    )


def build_player_action_frames(command_text: str, meta: dict, enemy, flag_notes: list[str]) -> list[CombatFrame]:
    host = enemy.get_visible_name()
    target = meta.get("target")
    cost = meta.get("cost", 0)
    header = [
        f"host   :: {host}",
        f"lane   :: {_lane_label(target)}",
        f"ram    :: reserve {cost} GB",
        f"queue  :: {command_text}",
    ]

    frames = [
        CombatFrame(
            title="PAYLOAD COMMIT",
            lines=tuple(header),
            tone="yellow",
            delay=0.35,
        )
    ]

    if flag_notes:
        frames.extend(
            _stream_frames(
                "WRAPPER STREAM",
                header,
                _wrapper_stream_lines(flag_notes, target),
                tone="magenta",
                tail_size=9,
                step_delay=0.07,
                final_delay=0.22,
            )
        )

    frames.extend(
        _stream_frames(
            "PAYLOAD STREAM",
            header,
            _script_stream_lines(meta.get("name", command_text), target, enemy, meta),
            tone=_script_tone(meta.get("kind", "unknown")),
            tail_size=10,
            step_delay=0.065,
            final_delay=0.24,
        )
    )
    return frames


def build_enemy_action_frames(enemy) -> list[CombatFrame]:
    intent = enemy.current_intent or {}
    kind = intent.get("kind", "idle")
    target = intent.get("target", "OS")
    name = intent.get("name", "Unknown Routine")
    host = enemy.get_visible_name()
    lane = _lane_label(target)

    library = {
        "scan_topology": [
            "hostile syn walkers out",
            "service geometry forming",
            "return-path timings being graphed",
            "surface adjacency model tightening",
            "your layout sharpening in their cache",
        ],
        "scan_signature": [
            "route jitter compared",
            "packet cadence collapsed into buckets",
            "weak lane narrowing",
            "operator fingerprint hardening",
            "signature lock tightening",
        ],
        "repair": [
            "repair queues spinning",
            f"service state restitched :: {lane}",
            "integrity fragments reassembled",
            "watchdog confidence rising",
            "integrity climbing",
        ],
        "trace": [
            "ownership paths walked",
            "transit records correlated",
            "trail map getting hotter",
            "egress history folding inward",
            "trace pressure propagating",
        ],
        "ram_lock": [
            "quota clamps engaging",
            "allocator lanes narrowed",
            "scheduler starvation rising",
            "runtime headroom squeezed",
            "runtime headroom shrinking",
        ],
        "attack": [
            f"countermeasure burst :: {lane}",
            "commit envelope hardened",
            "traffic stress spikes",
            "outbound pressure climbs",
            "response pressure holding",
        ],
        "drain": [
            f"value lane opening :: {lane}",
            "session bleed started",
            "exfil handles aligning",
            "buffered state siphoned",
            "host pulling state",
        ],
        "strip_defense": [
            "defense hooks isolating",
            "policy edges peeled back",
            "protection paths peeled back",
            "guard signatures decaying",
            "guard rails slipping",
        ],
        "finisher": [
            "kill-chain authority online",
            "terminal path selected",
            "burn notice propagating",
            "hard-stop packets staged",
            "termination path armed",
        ],
        "idle": [
            "host posture holds",
            "background traffic breathing",
            "countermeasure loop still alive",
        ],
    }
    header = [
        f"host    :: {host}",
        f"routine :: {name}",
        f"lane    :: {lane}",
    ]
    return [
        CombatFrame(title="HOSTILE COMMIT", lines=tuple(header), tone="red", delay=0.28),
        * _stream_frames(
            "COUNTER-STREAM",
            header,
            library.get(
                kind,
                [
                    f"{name} loading against {lane}",
                    "counter-intrusion logic taking the active route",
                    "the hostile queue settling into a visible response path",
                ],
            ),
            tone="red",
            tail_size=11,
            step_delay=0.055,
            final_delay=0.18,
        ),
    ]
