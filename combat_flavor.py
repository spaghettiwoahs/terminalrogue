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
    tail_size: int = 10,
    step_delay: float = 0.07,
    final_delay: float = 0.28,
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
                f"load wrapper[{index:02d}] :: lane={lane}",
                f"patch payload envelope :: {note}",
                f"seal wrapper[{index:02d}] :: commit-ready",
            ]
        )
    return stream


def _script_stream_lines(command_id: str, target: str | None, enemy, meta: dict) -> list[str]:
    lane = _lane_label(target)
    service = _service_hint(enemy, target)
    host = enemy.get_visible_name().split("[")[0].strip().lower().replace(" ", "_")

    library = {
        "ping": [
            f"open icmp socket -> host={host} lane={lane}",
            "emit echo sequence :: ttl=64 jitter=adaptive",
            f"collect rtt deltas -> {lane}",
            "cache timing mark for immediate follow-through",
            "close probe socket :: echo profile retained",
        ],
        "nmap": [
            f"queue half-open syn probes -> host={host} lane={lane}",
            f"banner grab tasks online -> {service}",
            "port-state classifier consuming returned packets",
            "service map merging into the live route cache",
            "scan thread closed :: telemetry written to dossier",
        ],
        "enum": [
            f"enumeration workers attached -> {lane}",
            "pull process counters and live runtime metadata",
            "compare scheduler drift against service telemetry",
            "host action model narrowing into a readable intent trace",
            "enumeration cache sealed into the active dossier",
        ],
        "whois": [
            f"query rir path -> host={host}",
            "registrant and netrange metadata returning through public mirrors",
            "ownership trail cross-linked against route context",
            "operator profile cached for lower-noise follow-up recon",
        ],
        "dirb": [
            f"wordlist walker mounted on {lane}",
            "endpoint guesses pruning dead paths at speed",
            "management surface returning enough structure to map live hits",
            "interesting paths pinned for follow-on exploit work",
        ],
        "airmon-ng": [
            f"flip interface posture -> monitor mode against {lane}",
            "peel perimeter watchers off the control plane",
            "capture side-channel packets from the weakened shell",
            "temporary breach window established under perimeter noise",
        ],
        "hydra": [
            f"spawn auth workers -> lane={lane} threads=parallel",
            "credential attempts cycling through weak login paths",
            "failure counters desyncing under sustained auth pressure",
            "lockout edge approaching but the route is still answering back",
            "usable breach pressure holding on the lane like a cracked hinge",
        ],
        "sqlmap": [
            f"inject parameter set -> lane={lane}",
            "backend errors collapsing into a repeatable query surface",
            "fingerprinted datastore accepting dirty test vectors",
            "exfil handles opening just long enough to pull value out",
            "injection window recorded for later chain work",
        ],
        "spray": [
            f"fan credential spray across {lane}",
            "weak reuse paths surfacing under shallow auth pressure",
            "successful retries still sparse but the login surface is softening",
            "brute-force follow-up window widening across exposed auth paths",
        ],
        "shred": [
            f"mount destructive wipe routine -> lane={lane}",
            "recovery metadata and journals tearing out of order",
            "restore confidence collapsing across the damaged volume",
            "the lane is still live, but recovery posture is getting ugly",
        ],
        "overflow": [
            f"drive malformed writes into {lane}",
            "allocator assumptions starting to slip under bad input",
            "heap posture destabilizing around the active process set",
            "next hostile commit may inherit the corruption spill if the host is unlucky",
        ],
        "hammer": [
            f"arm crash harness -> lane={lane}",
            "watchdogs and panic thresholds climbing under load",
            "the host is spending stability to keep the lane upright",
            "one clean hit from here can push the whole surface sideways in a hurry",
        ],
        "spoof": [
            "shape outbound traffic away from your real cadence",
            "host heuristics lock onto manufactured noise instead",
            "behavioral cache drifts further from your true route profile",
        ],
        "harden": [
            f"compile fresh acl shell around {lane}",
            "policy edges tightening against expected ingress paths",
            "defensive shell locked into the subsystem control plane",
        ],
        "honeypot": [
            "seed fake services and telemetry beacons",
            "prime the next hostile scan with controlled nonsense",
            "decoy surface now holding in front of your real node",
        ],
        "canary": [
            f"arm watchpoint callback on {lane}",
            "trap route sleeping until a hostile commit hits the lane",
            "callback detonation path standing by",
        ],
        "sinkhole": [
            f"open a return-path sinkhole behind {lane}",
            "hostile packets on that lane are being lined up for self-harm",
            "redirect path is live and waiting for the next commit",
        ],
        "rekey": [
            "rotate session material and invalidate stale handles",
            "scrub recon-linked cache state out of the current exchange",
            "the host now has to trust a colder and dirtier read on you",
        ],
        "patch": [
            "open emergency maintenance lane on the local rig",
            "stitch damaged services back into a stable runtime set",
            "apply quick fixes before the host can capitalize on the gap",
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
            f"spawn payload threads -> host={host} lane={lane}",
            f"host surface answers from {service}",
            "execution trace resolving into a usable impact window",
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
            "launch hostile syn walkers across your exposed edges",
            "coarse service geometry forming inside the host cache",
            "your rough layout starting to stabilize under hostile recon",
        ],
        "scan_signature": [
            "compare route jitter against known offensive fingerprints",
            "narrow response timing toward your actual weak lane",
            "signature lock tightening on the live exchange one ugly packet at a time",
        ],
        "repair": [
            f"restart queues spinning around {lane}",
            "stale service state being replaced under active pressure",
            "integrity being stitched back into the damaged lane",
        ],
        "trace": [
            "walk upstream ownership and allocation paths in parallel",
            "expand route history into a hotter map of your trail",
            "trace pressure propagating beyond the immediate node",
        ],
        "ram_lock": [
            "hostile quotas clamping down on your execution headroom",
            "scheduler pressure and handle starvation stacking up",
            "your available runtime shrinking under hostile control",
        ],
        "attack": [
            f"countermeasure burst driving straight into {lane}",
            "the host pushing live traffic stress through the route",
            "direct response pressure holding on the targeted lane",
        ],
        "drain": [
            f"value-bearing data opening under {lane}",
            "exfil handles aligning behind the hostile queue",
            "the host pulling useful state before the window closes",
        ],
        "strip_defense": [
            "hostile hooks isolating your active defensive layer",
            "protection paths being peeled off the live exchange",
            "your planted guard rails starting to slip loose",
        ],
        "finisher": [
            "kill-chain authority stepping to the top of the hostile queue",
            "burn notice propagating through session control state",
            "the node preparing to terminate the link where it stands",
        ],
        "idle": [
            "the host holds posture without a clean opening",
            "background control traffic keeps the route alive",
            "quiet does not mean safe; the countermeasure loop is still breathing",
        ],
    }
    header = [
        f"host    :: {host}",
        f"routine :: {name}",
        f"lane    :: {lane}",
    ]
    return [
        CombatFrame(title="HOSTILE COMMIT", lines=tuple(header), tone="red", delay=0.36),
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
            tail_size=10,
            step_delay=0.075,
            final_delay=0.26,
        ),
    ]
