from __future__ import annotations

from combat_feedback_text import choose_command_feedback, choose_generic_feedback


def capture_enemy_feedback_state(enemy) -> dict:
    return {
        "subsystems": {
            key: {
                "hp": subsystem.current_hp,
                "max_hp": subsystem.max_hp,
                "destroyed": subsystem.is_destroyed,
            }
            for key, subsystem in enemy.subsystems.items()
        },
        "topology_revealed": enemy.topology_revealed,
        "intent_revealed": enemy.intent_revealed,
        "weakness_revealed": enemy.weakness_revealed,
        "player_topology_revealed": enemy.player_topology_revealed,
        "player_signature_revealed": enemy.player_signature_revealed,
        "security_breach_turns": enemy.security_breach_turns,
        "endpoint_hits": set(getattr(enemy, "endpoint_hits", set())),
        "telemetry_targets": set(getattr(enemy, "telemetry_targets", set())),
        "credential_pressure_turns": dict(getattr(enemy, "credential_pressure_turns", {})),
        "timing_windows": dict(getattr(enemy, "timing_windows", {})),
        "fingerprint_windows": dict(getattr(enemy, "fingerprint_windows", {})),
    }


def _lane_label(target: str | None) -> str:
    if not target or target == "---":
        return "route-wide"
    return f"[{str(target).upper()}]"


def _delta(before: dict, after: dict, key: str) -> tuple[int, bool]:
    before_sub = before["subsystems"].get(key, {})
    after_sub = after["subsystems"].get(key, {})
    return before_sub.get("hp", 0) - after_sub.get("hp", 0), (
        not before_sub.get("destroyed", False) and after_sub.get("destroyed", False)
    )


def _health_band(after_state: dict, target: str | None, damage_dealt: int, went_offline: bool) -> str:
    if not target or target not in after_state["subsystems"]:
        return "general"
    if went_offline:
        return "down"
    if damage_dealt <= 0:
        return "nohit"
    after_sub = after_state["subsystems"][target]
    max_hp = max(1, after_sub.get("max", 1))
    ratio = after_sub.get("hp", 0) / max_hp
    if ratio <= 0.25:
        return "low"
    if ratio <= 0.5:
        return "half"
    return "grazed"


def build_action_feedback(command_id: str, meta: dict, enemy, before_state: dict, after_state: dict) -> list[str]:
    target = str(meta.get("target", "---")).upper() if meta.get("target") else None
    lane = _lane_label(target)
    lines: list[str] = []
    host = enemy.get_visible_name()

    damage_dealt = 0
    went_offline = False
    if target and target in after_state["subsystems"]:
        damage_dealt, went_offline = _delta(before_state, after_state, target)
    band = _health_band(after_state, target, damage_dealt, went_offline)
    command_line = choose_command_feedback(command_id, band, lane=lane, host=host)
    generic_line = choose_generic_feedback(band, lane=lane, host=host)
    if command_line:
        lines.append(command_line)
    if generic_line and generic_line != command_line:
        lines.append(generic_line)
    if meta.get("kind") == "item" and not lines:
        lines.append("Local kit telemetry confirmed the single-use payload took hold on the live rig state.")

    if target and target in after_state["subsystems"] and not lines:
        if went_offline:
            lines.append(f"response signal from {lane} disappeared after the payload; follow-up probes just collapse into timeout noise.")
        elif damage_dealt > 0:
            lines.append(f"{lane} is still returning traffic, but the response shape degraded enough to prove a real hit landed.")

    if (
        not before_state["player_topology_revealed"]
        and after_state["player_topology_revealed"]
    ):
        lines.append("the host's counter-intel just gained a rough map of your rig; your own traffic handed them that outline.")
    if (
        not before_state["player_signature_revealed"]
        and after_state["player_signature_revealed"]
    ):
        lines.append("the host sharpened your route into a real signature lock; you can feel it in the way return pressure is starting to narrow.")
    if before_state["security_breach_turns"] < after_state["security_breach_turns"]:
        lines.append("perimeter watchdog chatter is still thin on the wire; the security lane remains visibly peeled open.")
    if target and target in after_state["credential_pressure_turns"]:
        if before_state["credential_pressure_turns"].get(target, 0) < after_state["credential_pressure_turns"].get(target, 0):
            lines.append(f"credential failures on {lane} are clustering tighter now; the lane is softening for a nastier follow-up.")
    if target and target in after_state["timing_windows"]:
        if before_state["timing_windows"].get(target, 0) < after_state["timing_windows"].get(target, 0):
            lines.append(f"timing on {lane} is cleaner than it was a moment ago; you have a real follow-up window there now.")
    if target and target in after_state["fingerprint_windows"]:
        if before_state["fingerprint_windows"].get(target, 0) < after_state["fingerprint_windows"].get(target, 0):
            lines.append(f"banner drift on {lane} is specific enough now to support a cleaner exploit pass.")
    if target and target in after_state["subsystems"]:
        os_delta, _ = _delta(before_state, after_state, "OS")
        if target != "OS" and os_delta > 0:
            lines.append("core instability bled through the subsystem failure; you could see the spill in the host's broader response pattern.")

    deduped: list[str] = []
    seen = set()
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        deduped.append(line)
    return deduped[:5]
