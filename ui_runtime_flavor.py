from __future__ import annotations


def _lane(intent: dict) -> str:
    target = str(intent.get("target", "OS")).upper()
    return f"[{target}]"


def build_enemy_turn_disturbances(enemy) -> tuple[dict[str, list[tuple[str, str]]], str]:
    intent = enemy.current_intent or {}
    host = enemy.get_visible_name()
    routine = intent.get("name", "Unknown Routine")
    kind = intent.get("kind", "idle")
    lane = _lane(intent)

    default = {
        "player": [
            ("ALERT // hostile route pressure rising", "yellow"),
            (f"counter-intrusion loop active :: {routine}", "red"),
            ("local shell still holding, but the link is no longer quiet", "muted"),
        ],
        "target": [
            ("HOSTILE ROUTINE ACTIVE", "red"),
            (f"operator :: {host}", "yellow"),
            (f"routine :: {routine}", "yellow"),
        ],
        "route": [
            ("WARNING // return-path turbulence detected", "yellow"),
            ("adjacent transit links are spiking under hostile load", "muted"),
            ("outbound routing remains unstable until your next planning phase", "muted"),
        ],
    }

    library = {
        "scan_topology": (
            {
                "player": [
                    ("WARNING // topology scrape in progress", "yellow"),
                    (f"hostile walkers are tracing your exposed buses from {lane}", "red"),
                    ("layout confidence is climbing on the far end of the link", "muted"),
                ],
                "target": [
                    ("HOSTILE ENUMERATION", "red"),
                    (f"{routine} is crawling your rig geometry", "yellow"),
                    ("bus timings are being compared against the host's local cache", "muted"),
                ],
                "route": [
                    ("ALERT // scan noise spilling into the route mesh", "yellow"),
                    ("link-state probes are fanning out from the hostile node", "muted"),
                    ("transit edges are carrying more recon than payload traffic", "muted"),
                ],
            },
            "hostile topology scrape",
        ),
        "scan_signature": (
            {
                "player": [
                    ("ALERT // signature lock tightening", "red"),
                    ("timing jitter, packet shape, and lane preference are being reduced to a fingerprint", "yellow"),
                    ("if they keep this read, your safe angles get thinner next round", "muted"),
                ],
                "target": [
                    ("COUNTER-INTEL LIVE", "red"),
                    (f"{routine} is classifying your route signature", "yellow"),
                    ("the host is no longer content with a rough map", "muted"),
                ],
                "route": [
                    ("WARNING // return traffic pattern no longer looks random", "yellow"),
                    ("hostile heuristics are clustering around your preferred lanes", "muted"),
                    ("adjacent hops are starting to reflect the same read", "muted"),
                ],
            },
            "hostile signature hunt",
        ),
        "repair": (
            {
                "player": [
                    ("NOTICE // hostile recovery cycle engaged", "yellow"),
                    (f"repair queues are converging on {lane}", "red"),
                    ("the host is spending this window shoring up damage instead of pushing you", "muted"),
                ],
                "target": [
                    ("RECOVERY TRAFFIC", "yellow"),
                    (f"{routine} is restitching {lane}", "yellow"),
                    ("service chatter is denser and cleaner than it was a moment ago", "muted"),
                ],
                "route": [
                    ("NOTICE // internal keepalive chatter increasing", "yellow"),
                    ("repair traffic is briefly dominating the hostile node's outbound rhythm", "muted"),
                    ("route pressure is stable, but the window is closing", "muted"),
                ],
            },
            "hostile repair cycle",
        ),
        "trace": (
            {
                "player": [
                    ("ALERT // trace path propagating", "red"),
                    ("ownership paths are being walked back across the route", "yellow"),
                    ("the hostile node is spending this turn trying to make your exit expensive", "muted"),
                ],
                "target": [
                    ("TRACE PROCESS ACTIVE", "red"),
                    (f"{routine} is backtracking your ingress path", "yellow"),
                    ("registrar and transit metadata are being folded into one picture", "muted"),
                ],
                "route": [
                    ("WARNING // route mesh warming up", "yellow"),
                    ("hops behind you are getting noisier as the trace spreads", "muted"),
                    ("the map will cool again only if you survive the turn", "muted"),
                ],
            },
            "trace propagation",
        ),
        "ram_lock": (
            {
                "player": [
                    ("ALERT // quota clamp in flight", "red"),
                    ("hostile control traffic is squeezing your mem bus headroom", "yellow"),
                    ("scheduler pressure will clear at the start of your next clean turn", "muted"),
                ],
                "target": [
                    ("CONTROL ROUTINE ACTIVE", "red"),
                    (f"{routine} is forcing pressure onto {lane}", "yellow"),
                    ("the host is trying to make your next stack physically smaller", "muted"),
                ],
                "route": [
                    ("WARNING // control-plane bursts visible on the uplink", "yellow"),
                    ("the route is carrying more clamps and fewer scans", "muted"),
                    ("adjacent hops show the same ugly rhythm", "muted"),
                ],
            },
            "hostile control clamp",
        ),
        "attack": (
            {
                "player": [
                    ("ALERT // hostile payload commit", "red"),
                    (f"countermeasure traffic is boring straight toward {lane}", "yellow"),
                    ("the shell is still responsive, but the bus is screaming", "muted"),
                ],
                "target": [
                    ("WEAPON DISCHARGE", "red"),
                    (f"{routine} just committed on {lane}", "yellow"),
                    ("outbound pressure is no longer speculative", "muted"),
                ],
                "route": [
                    ("WARNING // route spike under live fire", "yellow"),
                    ("burst traffic from the hostile node is saturating nearby edges", "muted"),
                    ("return-path stability will not come back until the turn rolls", "muted"),
                ],
            },
            "hostile payload burst",
        ),
        "drain": (
            {
                "player": [
                    ("ALERT // exfil path opening", "red"),
                    (f"value-bearing traffic is being teased out through {lane}", "yellow"),
                    ("you can feel the host trying to turn your own state into yield", "muted"),
                ],
                "target": [
                    ("DRAIN ROUTINE ACTIVE", "red"),
                    (f"{routine} is pulling against {lane}", "yellow"),
                    ("the host is attacking by extraction rather than raw collapse", "muted"),
                ],
                "route": [
                    ("WARNING // outbound traffic now includes exfil signatures", "yellow"),
                    ("the route is carrying theft, not just damage", "muted"),
                    ("nearby hops show a steadier pull than a strike", "muted"),
                ],
            },
            "hostile siphon window",
        ),
        "strip_defense": (
            {
                "player": [
                    ("ALERT // defensive shell degradation", "red"),
                    ("guard rails are being peeled back before the next real hit", "yellow"),
                    ("the host is trying to make the board simpler for itself", "muted"),
                ],
                "target": [
                    ("DEFENSE EROSION", "red"),
                    (f"{routine} is stripping the lane around {lane}", "yellow"),
                    ("the control plane is choosing preparation over force", "muted"),
                ],
                "route": [
                    ("WARNING // defensive chatter collapsing on the route", "yellow"),
                    ("protective traffic is being displaced by cleaner offensive control", "muted"),
                    ("adjacent hops are watching the same opening form", "muted"),
                ],
            },
            "defense strip",
        ),
        "finisher": (
            {
                "player": [
                    ("ALERT // termination path armed", "red"),
                    ("every hostile signal on the route now points toward a kill decision", "yellow"),
                    ("if the host lands this clean, the shell may not come back", "muted"),
                ],
                "target": [
                    ("KILL ROUTINE", "red"),
                    (f"{routine} is no longer testing you", "yellow"),
                    ("the host has stopped spending cycles on subtlety", "muted"),
                ],
                "route": [
                    ("WARNING // route mesh carrying burn traffic", "yellow"),
                    ("adjacent links are reflecting termination-grade pressure", "muted"),
                    ("this is the loudest the hostile node gets before a hard cut", "muted"),
                ],
            },
            "kill-chain escalation",
        ),
    }

    return library.get(kind, (default, "hostile route pressure"))  # type: ignore[return-value]
