from __future__ import annotations


DNA_KEYS = ("vectors", "protocols", "behaviors")


VECTOR_REASON_MAP = {
    "access": "access paths hardened",
    "credential": "auth surfaces hardened",
    "network": "uplink shapers retuned",
    "service": "service banners filtered",
    "recon": "recon signatures filtered",
    "web": "reverse proxy rules tightened",
    "database": "query guards warmed up",
    "memory": "allocator guards raised",
    "kernel": "kernel hooks armed",
    "defense": "defense lattice profiled",
    "counterintel": "counterintel baselines reinforced",
    "wireless": "rf monitors retuned",
    "stack": "stack loader heuristics tuned",
    "data": "data sinks fenced off",
    "destruction": "destructive I/O throttled",
}

PROTOCOL_REASON_MAP = {
    "icmp": "echo traffic filtered",
    "tcp": "socket filters narrowed",
    "udp": "udp rate shapers engaged",
    "syn": "syn cookies tightened",
    "banner": "banner leakage reduced",
    "http": "http routes tarpitted",
    "https": "tls front-ends reshaped",
    "ssh": "ssh auth daemon tarpitted",
    "smb": "file-share sessions hardened",
    "sql": "database parsers watched",
    "dns": "resolver noise clipped",
    "tls": "session keys rotated",
    "bus": "bus arbitration hardened",
    "buffer": "buffer sentries primed",
    "thread": "thread fanout watched",
}

BEHAVIOR_REASON_MAP = {
    "probe": "probe cadence recognized",
    "timing": "timing windows compensated for",
    "scan": "scan patterns cached",
    "enumerate": "enumeration footprints recognized",
    "brute": "brute-force cadence cached",
    "spray": "spray pattern filtered",
    "inject": "injection heuristics enabled",
    "flood": "flood response plans activated",
    "burst": "burst windows damped",
    "split": "forked threads sandboxed",
    "spread": "propagation guards staged",
    "smash": "panic handlers pre-armed",
    "corrupt": "corruption sentries active",
    "wipe": "destructive writes rate-limited",
    "mask": "opsec veil partly burned",
    "evade": "evasion profile partially mapped",
    "fortify": "hardening pattern profiled",
    "trap": "watchpoint lane anticipated",
    "repair": "repair timing predicted",
    "stage": "loader staging profiled",
    "defer": "deferred payload hook traced",
    "drain": "exfil siphon monitored",
}


def _normalize_list(values) -> tuple[str, ...]:
    if not values:
        return ()
    normalized = []
    for value in values:
        token = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        if token and token not in normalized:
            normalized.append(token)
    return tuple(normalized)


def normalize_payload_dna(dna: dict | None) -> dict[str, tuple[str, ...]]:
    dna = dna or {}
    return {key: _normalize_list(dna.get(key)) for key in DNA_KEYS}


def merge_payload_dna(*dna_records: dict | None) -> dict[str, tuple[str, ...]]:
    merged = {key: [] for key in DNA_KEYS}
    for dna in dna_records:
        normalized = normalize_payload_dna(dna)
        for key in DNA_KEYS:
            for token in normalized[key]:
                if token not in merged[key]:
                    merged[key].append(token)
    return {key: tuple(values) for key, values in merged.items()}


def build_payload_signature(dna: dict | None) -> str:
    normalized = normalize_payload_dna(dna)
    parts = []
    for key in DNA_KEYS:
        values = normalized[key]
        if values:
            parts.append(f"{key}:{','.join(values)}")
    return "|".join(parts)


def dominant_dna_labels(counts: dict[str, int], reason_map: dict[str, str], limit: int = 2) -> list[str]:
    ranked = sorted(
        ((token, count) for token, count in counts.items() if count > 0),
        key=lambda item: (-item[1], item[0]),
    )
    labels = []
    for token, _count in ranked[:limit]:
        labels.append(reason_map.get(token, token.replace("_", " ")))
    return labels


def dna_adaptation_reasons(dna: dict | None) -> list[str]:
    normalized = normalize_payload_dna(dna)
    reasons = []
    for token in normalized["vectors"]:
        reason = VECTOR_REASON_MAP.get(token)
        if reason and reason not in reasons:
            reasons.append(reason)
    for token in normalized["protocols"]:
        reason = PROTOCOL_REASON_MAP.get(token)
        if reason and reason not in reasons:
            reasons.append(reason)
    for token in normalized["behaviors"]:
        reason = BEHAVIOR_REASON_MAP.get(token)
        if reason and reason not in reasons:
            reasons.append(reason)
    return reasons
