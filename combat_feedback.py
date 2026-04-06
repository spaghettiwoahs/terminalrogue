from __future__ import annotations


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


def build_action_feedback(command_id: str, meta: dict, enemy, before_state: dict, after_state: dict) -> list[str]:
    target = str(meta.get("target", "---")).upper() if meta.get("target") else None
    lane = _lane_label(target)
    lines: list[str] = []

    damage_dealt = 0
    went_offline = False
    if target and target in after_state["subsystems"]:
        damage_dealt, went_offline = _delta(before_state, after_state, target)

    if command_id == "ping":
        if went_offline:
            lines.append(f"icmp echo on {lane} went from dirty jitter to hard timeout in one step; whatever was living there just dropped off the route.")
        elif damage_dealt > 0:
            lines.append(f"icmp timing on {lane} came back ragged and wide; the lane is still answering, but it sounds hurt.")
        else:
            lines.append(f"icmp replies from {lane} still resolve cleanly; you got signal, but no visible break in posture.")
    elif command_id == "hydra":
        if went_offline:
            lines.append(f"auth traffic on {lane} collapsed into lockouts and dead air; the login surface burned itself out under the final burst.")
        elif damage_dealt > 0:
            lines.append(f"login responses on {lane} slowed, forked, and started disagreeing with each other; the auth surface is still up, but it is wobbling.")
    elif command_id == "airmon-ng":
        if went_offline:
            lines.append(f"monitor-mode capture on {lane} flattened into silence; the perimeter lost coherence and stopped maintaining a real beacon.")
        else:
            lines.append(f"monitor-mode capture shows the perimeter thinning on {lane}; the shell is still there, but it is leaking badly.")
    elif command_id == "nmap":
        if target:
            lines.append(f"version probes on {lane} came back with enough banner drift and stack weirdness to support a real fingerprint.")
        else:
            lines.append("syn/ack spread and service banners resolved into a usable surface map; the picture came from returned packets, not omniscience.")
    elif command_id == "enum":
        lines.append(f"process counters and runtime telemetry on {lane} stayed exposed just long enough to pin exact state off the live host.")
    elif command_id == "whois":
        lines.append("allocation and registrant records lined up with the active route; the operator trail came out of public ownership debris.")
    elif command_id == "dirb":
        lines.append(f"http status spread and path hits around {lane} peeled the management surface open one response at a time.")
    elif command_id == "sqlmap":
        if went_offline:
            lines.append(f"backend responses on {lane} decayed into broken query noise; the service stopped surviving its own answers.")
        else:
            lines.append(f"query behavior on {lane} leaked enough backend pain to confirm the injection actually landed.")
    elif command_id == "spray":
        if went_offline:
            lines.append(f"credential prompts on {lane} buckled into lockouts and dead air; the auth surface stopped keeping up with its own abuse.")
        else:
            lines.append(f"the login edge on {lane} is still alive, but the failure pattern now reeks of credential pressure.")
    elif command_id == "shred":
        if went_offline:
            lines.append(f"recovery chatter on {lane} just vanished under the wipe pass; the subsystem is not coming back cleanly.")
        else:
            lines.append(f"journal and restore chatter from {lane} turned feral; the lane took real structural damage.")
    elif command_id == "overflow":
        if went_offline:
            lines.append(f"runtime output from {lane} broke into allocator faults, then flatlined; the corrupted service never recovered.")
        else:
            lines.append(f"response structure on {lane} is visibly corrupt; the heap damage is in the shape of every answer coming back.")
    elif command_id == "hammer":
        if went_offline:
            lines.append(f"watchdog and panic signatures on {lane} rolled over into silence; the crash harness forced a hard, ugly failure.")
        else:
            lines.append(f"kernel panic indicators spiked across {lane}; the host stayed up, but only out of spite.")
    elif command_id == "spoof":
        lines.append("counter-recon traffic is biting on fabricated cadence now; the route accepted the lie, which means the read was poisoned.")
    elif command_id == "harden":
        lines.append(f"local acl acknowledgements returned from {lane}; the shell is live because policy commits actually stuck.")
    elif command_id == "honeypot":
        lines.append("the decoy service is advertising on the route now; the next hostile scan has something fake, clean, and believable to bite.")
    elif command_id == "canary":
        lines.append(f"callback handshake armed on {lane}; the trap is live because the watchpoint registered with your local control plane.")
    elif command_id == "sinkhole":
        lines.append(f"return-path sinkhole armed on {lane}; you can see the blackhole route because the redirect hook accepted the lane.")
    elif command_id == "rekey":
        lines.append("the old session material stopped validating immediately; the route is speaking under fresh keys now, and the host knows it.")
    elif command_id == "patch":
        lines.append("local watchdog noise eased off after the patch cycle; the rig is holding steadier than it was a moment ago.")
    elif meta.get("kind") == "item":
        lines.append("local kit telemetry confirmed the single-use payload took hold on the live rig state.")

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
    return deduped[:4]
