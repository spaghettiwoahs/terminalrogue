from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class StackStepPreview:
    phase: str
    command: str
    legal: bool
    ram_before: int
    ram_after: int
    message: str
    notes: list[str] = field(default_factory=list)


@dataclass
class StackProjection:
    legal: bool
    error: str = ""
    steps: list[StackStepPreview] = field(default_factory=list)
    preflight_commands: list[str] = field(default_factory=list)
    execution_commands: list[str] = field(default_factory=list)
    projected_player: object | None = None
    projected_enemy: object | None = None
    root_prediction: str | None = None
    root_reason: str = ""


def is_item_command(command_str: str) -> bool:
    return command_str.strip().lower().startswith("use ")


def parse_item_command(command_str: str, item_library: dict, player):
    tokens = command_str.strip().split()
    if len(tokens) < 2 or tokens[0].lower() != "use":
        raise ValueError("Error: Item syntax is 'use <item>' or 'use <item> -target <SUB>'.")

    item_id = tokens[1].lower()
    item_data = item_library.get(item_id)
    if not item_data:
        raise ValueError(f"Error: Consumable '{item_id}' not recognized.")
    if player and hasattr(player, "get_consumable_count") and player.get_consumable_count(item_id) <= 0:
        raise ValueError(f"Error: You do not have any '{item_id}'.")

    target_subsystem = None
    idx = 2
    while idx < len(tokens):
        token = tokens[idx]
        if token == "-target":
            if idx + 1 >= len(tokens):
                raise ValueError("Error: '-target' requires a subsystem name.")
            target_subsystem = tokens[idx + 1].upper()
            idx += 2
            continue
        raise ValueError(f"Error: Unexpected token '{token}'.")

    if item_data.get("requires_target") and not target_subsystem:
        default_target = item_data.get("default_target")
        if default_target:
            target_subsystem = str(default_target).upper()
        else:
            raise ValueError(f"Error: '{item_id}' requires '-target <SUBSYSTEM>'.")

    return item_id, item_data, target_subsystem


def apply_item_effect(item_id: str, item_data: dict, target_subsystem: str | None, player, enemy):
    effect = item_data.get("effect")
    amount = item_data.get("amount", 0)
    turns = item_data.get("turns", 1)

    if effect == "ram":
        restored, overflow = prime_ram_capsule(player, amount)
        if restored <= 0 and overflow <= 0:
            return False, "RAM capsule would have no effect."
        player.consume_consumable(item_id)
        parts = []
        if restored > 0:
            parts.append(f"+{restored} live RAM")
        if overflow > 0:
            parts.append(f"+{overflow} overflow RAM")
        return True, "Inline injection primed " + " and ".join(parts) + "."

    if effect == "guard":
        player.consume_consumable(item_id)
        player.grant_guard(target_subsystem, amount, turns)
        return True, f"ACL shell primed inline on [{target_subsystem}] for {turns} turn(s)."

    if effect == "patch":
        os_core = player.subsystems["OS"]
        restored = min(os_core.max_hp - os_core.current_hp, amount)
        had_lock = player.clear_ram_lock()
        if restored <= 0 and not had_lock:
            return False, "Patch item would have no effect."
        player.consume_consumable(item_id)
        if restored > 0:
            os_core.current_hp += restored
        return True, f"Inline patch restored {restored} Core OS HP."

    if effect == "decoy":
        scrubbed = enemy.scrub_player_recon_stage(item_data.get("scrub_stages", 1))
        player.signature_revealed = enemy.player_signature_revealed
        player.topology_exposed = enemy.player_topology_revealed
        player.consume_consumable(item_id)
        player.arm_scan_jammer(item_data.get("jammer_turns", 1))
        return True, f"Honeypot seed primed. Recon scrubbed by {scrubbed} stage(s)."

    if effect == "tripwire":
        player.consume_consumable(item_id)
        player.arm_tripwire(target_subsystem, item_data.get("trap_damage", 5), turns)
        return True, f"Canary kit armed on [{target_subsystem}] for {turns} turn(s)."

    return False, f"Unknown item effect '{effect}'."


def prime_ram_capsule(player, amount: int):
    max_ram = player.get_effective_max_ram()
    injected = max(0, amount)
    total_after = player.current_ram + injected
    new_current = min(total_after, max_ram)
    overflow = max(0, total_after - max_ram)
    restored = max(0, new_current - player.current_ram)
    player.current_ram = new_current
    return restored, overflow


def consume_stack_ram(player, cost: int, overflow_ram: int):
    overflow_spent = min(max(0, overflow_ram), max(0, cost))
    base_spent = max(0, cost - overflow_spent)
    if base_spent > 0:
        player.current_ram = max(0, player.current_ram - base_spent)
    overflow_lost = max(0, overflow_ram - overflow_spent)
    return overflow_spent, base_spent, overflow_lost


def split_stack(queue_commands: list[str]) -> tuple[list[str], list[str]]:
    return [], list(queue_commands)


def simulate_command_delta(arsenal, command_str: str, player, enemy, state):
    shadow_player = deepcopy(player)
    shadow_enemy = deepcopy(enemy)
    shadow_state = deepcopy(state)
    if hasattr(shadow_player, "ensure_runtime_defaults"):
        shadow_player.ensure_runtime_defaults()
    if hasattr(shadow_enemy, "ensure_runtime_defaults"):
        shadow_enemy.ensure_runtime_defaults()
    if hasattr(shadow_state, "ensure_runtime_defaults"):
        shadow_state.ensure_runtime_defaults()
    before = {key: subsystem.current_hp for key, subsystem in shadow_enemy.subsystems.items()}
    result = arsenal.execute(command_str, shadow_player, shadow_enemy, shadow_state, phase="dry_run")
    delta = {
        key: before[key] - shadow_enemy.subsystems[key].current_hp
        for key in shadow_enemy.subsystems
    }
    return result, delta


def apply_held_damage(enemy, target_subsystem: str):
    held_map = getattr(enemy, "held_damage_buffers", {})
    held = held_map.get(target_subsystem, 0)
    if held <= 0 or target_subsystem not in enemy.subsystems:
        return []

    lines = []
    target = enemy.subsystems[target_subsystem]
    dealt = target.take_damage(held)
    held_map[target_subsystem] = 0
    if dealt > 0:
        lines.append(f"Held charge released into [{target_subsystem}] for {dealt} damage.")
    if target.is_destroyed and target_subsystem != "OS":
        cascade = enemy.subsystems["OS"].take_damage(2)
        if cascade > 0:
            lines.append(f"Bus collapse echoed 2 damage into [OS].")
    return lines


def bank_excess_damage(enemy, target_subsystem: str, amount: int, source: str = "buffer"):
    if amount <= 0 or target_subsystem not in enemy.subsystems:
        return []
    enemy.held_damage_buffers[target_subsystem] = enemy.held_damage_buffers.get(target_subsystem, 0) + amount
    return [f"{source} trapped {amount} excess damage on [{target_subsystem}] for later release."]


def apply_adjacency_window(enemy, pending_window: dict | None, target_subsystem: str | None):
    if not pending_window or not target_subsystem or pending_window.get("target") != target_subsystem:
        return []

    lines = []
    kind = pending_window.get("kind")
    if kind == "timing":
        enemy.arm_timing_window(target_subsystem, 1)
        lines.append(f"Timing window consumed on [{target_subsystem}].")
    elif kind == "fingerprint":
        enemy.arm_fingerprint_window(target_subsystem, 1)
        lines.append(f"Fingerprint cache consumed on [{target_subsystem}].")
    return lines


def clear_adjacency_window(enemy, pending_window: dict | None):
    if not pending_window:
        return
    target_subsystem = pending_window.get("target")
    if not target_subsystem:
        return
    if pending_window.get("kind") == "timing":
        enemy.timing_windows[target_subsystem] = 0
    elif pending_window.get("kind") == "fingerprint":
        enemy.fingerprint_windows[target_subsystem] = 0


def next_adjacency_window(arsenal, command_str: str, player):
    try:
        parsed = arsenal.parse_command(command_str, owner=player)
    except ValueError:
        return None

    script_data = arsenal.scripts.get(parsed.base_cmd, {})
    target = parsed.target_subsystem or script_data.get("default_target")
    if target:
        target = str(target).upper()

    if parsed.base_cmd == "ping" and target:
        return {"kind": "timing", "target": target, "source": "ping"}
    if parsed.base_cmd == "nmap" and parsed.has_target and target:
        return {"kind": "fingerprint", "target": target, "source": "nmap"}
    return None


def command_target(arsenal, command_str: str, player):
    parsed = arsenal.parse_command(command_str, owner=player)
    script_data = arsenal.scripts.get(parsed.base_cmd, {})
    target = parsed.target_subsystem or script_data.get("default_target")
    if not target and script_data.get("type") in {"brute_force", "exploit"}:
        target = "OS"
    return parsed, script_data, str(target).upper() if target else None


def classify_resolution(command_str: str, parsed_command, pre_enemy, post_enemy, result_metadata: dict | None = None) -> tuple[str | None, str]:
    pre_os = pre_enemy.subsystems["OS"].current_hp
    post_os = post_enemy.subsystems["OS"].current_hp
    if pre_os > 0 and post_os > 0:
        return None, ""
    if pre_os <= 0:
        return None, ""

    result_metadata = result_metadata or {}

    collateral_damage = 0
    collateral_drops = 0
    for key in post_enemy.subsystems:
        if key == "OS":
            continue
        before = pre_enemy.subsystems[key].current_hp
        after = post_enemy.subsystems[key].current_hp
        delta = max(0, before - after)
        collateral_damage += delta
        if before > 0 and after <= 0:
            collateral_drops += 1

    aggressive_flags = {"--worm", "--fork", "--volatile", "--burst"}
    aggressive_scripts = {"hammer", "overflow", "shred"}
    volatile_profile = (
        parsed_command.base_cmd in aggressive_scripts
        or any(flag in aggressive_flags for flag in parsed_command.flags)
    )
    overkill_damage = max(0, int(result_metadata.get("overkill_damage", 0)))
    contained_overkill = max(0, int(result_metadata.get("contained_overkill", 0)))
    effective_overkill = max(0, overkill_damage - contained_overkill)
    offlane_kill = parsed_command.target_subsystem not in {None, "OS"}

    if collateral_drops > 0 or collateral_damage >= 3 or offlane_kill:
        reasons = []
        if collateral_drops > 0:
            reasons.append("subsystem buses collapsed during the kill")
        if collateral_damage >= 3:
            reasons.append("collateral bus damage spiked during the kill")
        if offlane_kill:
            reasons.append("the core died by spillover instead of a clean OS finish")
        return "bricked", "; ".join(reasons) or "sloppy kill chain bricked the node"

    if effective_overkill >= 4 or (volatile_profile and effective_overkill >= 2):
        reasons = []
        if effective_overkill > 0:
            reasons.append(f"core finish overshot by {effective_overkill}")
        if contained_overkill > 0:
            reasons.append(f"{contained_overkill} excess damage was contained, but the live spike was still too rough")
        if parsed_command.base_cmd in aggressive_scripts:
            reasons.append(f"{parsed_command.base_cmd} destabilized the core")
        if any(flag in aggressive_flags for flag in parsed_command.flags):
            reasons.append("volatile wrappers were present")
        return "bricked", "; ".join(reasons) or "sloppy kill chain bricked the node"

    if contained_overkill > 0:
        return "rooted", f"contained finish shaved {contained_overkill} excess pressure off the core and granted root access"
    return "rooted", "clean core finish granted root access"


def build_projection(queue_commands: list[str], arsenal, player, enemy, state, item_library: dict) -> StackProjection:
    sim_player = deepcopy(player)
    sim_enemy = deepcopy(enemy)
    sim_state = deepcopy(state)
    if hasattr(sim_player, "ensure_runtime_defaults"):
        sim_player.ensure_runtime_defaults()
    if hasattr(sim_enemy, "ensure_runtime_defaults"):
        sim_enemy.ensure_runtime_defaults()
    if hasattr(sim_state, "ensure_runtime_defaults"):
        sim_state.ensure_runtime_defaults()
    steps: list[StackStepPreview] = []
    root_prediction = None
    root_reason = ""
    overflow_ram = 0

    preflight_commands, execution_commands = split_stack(queue_commands)

    pending_window = None
    pending_stager_target = None
    pending_buffer_target = None
    execution_queue = list(execution_commands)
    queue_index = 0
    while queue_index < len(execution_queue):
        command_str = execution_queue[queue_index]
        ram_before = sim_player.current_ram
        if is_item_command(command_str):
            try:
                item_id, item_data, target_subsystem = parse_item_command(command_str, item_library, sim_player)
            except ValueError as exc:
                return StackProjection(
                    legal=False,
                    error=str(exc),
                    steps=steps,
                    preflight_commands=preflight_commands,
                    execution_commands=execution_commands,
                    projected_player=sim_player,
                    projected_enemy=sim_enemy,
                )

            notes = []
            if pending_window:
                source = pending_window.get("source", "adjacency")
                notes.append(f"{source} window expired before a live payload consumed it")
            clear_adjacency_window(sim_enemy, pending_window)
            pending_window = None
            if pending_stager_target:
                notes.append(f"stager window on [{pending_stager_target}] expired without a matching adjacent offensive payload")
                pending_stager_target = None
            if pending_buffer_target:
                notes.append(f"buffer window on [{pending_buffer_target}] expired without a matching adjacent offensive payload")
                pending_buffer_target = None

            if item_data.get("effect") == "ram":
                restored, gained_overflow = prime_ram_capsule(sim_player, item_data.get("amount", 0))
                overflow_ram += gained_overflow
                success = restored > 0 or gained_overflow > 0
                if success:
                    sim_player.consume_consumable(item_id)
                message_bits = []
                if restored > 0:
                    message_bits.append(f"Inline injection added +{restored} live RAM.")
                if gained_overflow > 0:
                    message_bits.append(f"Overflow reserve +{gained_overflow} primed for the next payload.")
                    notes.append(f"next live payload can burn +{gained_overflow} overflow RAM before it dissipates")
                if not message_bits:
                    message_bits.append("Inline injection would have no effect.")
                message = " ".join(message_bits)
            else:
                success, message = apply_item_effect(item_id, item_data, target_subsystem, sim_player, sim_enemy)

            steps.append(
                StackStepPreview(
                    phase="item",
                    command=command_str,
                    legal=success,
                    ram_before=ram_before,
                    ram_after=sim_player.current_ram,
                    message=message,
                    notes=notes,
                )
            )
            if not success:
                return StackProjection(
                    legal=False,
                    error=message,
                    steps=steps,
                    preflight_commands=preflight_commands,
                    execution_commands=execution_commands,
                    projected_player=sim_player,
                    projected_enemy=sim_enemy,
                )
            queue_index += 1
            continue

        try:
            parsed, script_data, target_subsystem = command_target(arsenal, command_str, sim_player)
            cost = arsenal.get_command_cost(parsed)
        except ValueError as exc:
            return StackProjection(
                legal=False,
                error=str(exc),
                steps=steps,
                preflight_commands=preflight_commands,
                execution_commands=execution_commands,
                projected_player=sim_player,
                projected_enemy=sim_enemy,
            )

        available_ram = sim_player.current_ram + overflow_ram
        if available_ram < cost:
            message = f"Projected RAM fault: needs {cost}, would have {available_ram}."
            steps.append(
                StackStepPreview(
                    phase="execution",
                    command=command_str,
                    legal=False,
                    ram_before=ram_before,
                    ram_after=sim_player.current_ram,
                    message=message,
                )
            )
            return StackProjection(
                legal=False,
                error=message,
                steps=steps,
                preflight_commands=preflight_commands,
                execution_commands=execution_commands,
                projected_player=sim_player,
                projected_enemy=sim_enemy,
            )
        overflow_spent, base_spent, overflow_lost = consume_stack_ram(sim_player, cost, overflow_ram)
        overflow_ram = 0
        notes = []
        if overflow_spent > 0:
            notes.append(f"overflow reserve contributed {overflow_spent} RAM to this payload")
        if overflow_lost > 0:
            notes.append(f"unused overflow reserve {overflow_lost} dissipated after commit")
        if base_spent > 0:
            notes.append(f"live pool spent {base_spent} RAM")
        notes.extend(apply_held_damage(sim_enemy, target_subsystem) if target_subsystem else [])
        if sim_enemy.subsystems["OS"].current_hp <= 0 and not root_prediction:
            root_prediction = "bricked"
            root_reason = "stored detonation cooked the core before a clean live finish landed"
            steps.append(
                StackStepPreview(
                    phase="execution",
                    command=command_str,
                    legal=True,
                    ram_before=ram_before,
                    ram_after=sim_player.current_ram,
                    message="Held charge detonated before the live payload committed.",
                    notes=notes,
                )
            )
            break
        notes.extend(apply_adjacency_window(sim_enemy, pending_window, target_subsystem))

        pre_enemy = deepcopy(sim_enemy)
        message = ""
        result_metadata = {}
        stager_consumed = False
        buffer_consumed = False

        if parsed.base_cmd == "jmp":
            if queue_index + 2 < len(execution_queue):
                first = execution_queue[queue_index + 1]
                second = execution_queue[queue_index + 2]
                execution_queue[queue_index + 1], execution_queue[queue_index + 2] = second, first
                message = f"Branch shim swapped the next payloads: '{second}' will resolve before '{first}'."
            else:
                message = "Branch shim found no full two-payload window to reorder."
        elif parsed.base_cmd == "stager":
            message = f"Stager armed on [{target_subsystem}] for the next adjacent offensive payload."
            pending_stager_target = target_subsystem
        elif parsed.base_cmd == "buffer":
            message = f"Containment buffer armed on [{target_subsystem}] for the next adjacent offensive payload."
            pending_buffer_target = target_subsystem
        elif (
            pending_stager_target
            and target_subsystem == pending_stager_target
            and script_data.get("type") in {"brute_force", "exploit"}
        ):
            result, delta = simulate_command_delta(arsenal, command_str, sim_player, sim_enemy, sim_state)
            stored = sum(max(0, value) for key, value in delta.items() if key == target_subsystem)
            result_metadata = getattr(result, "metadata", {}) or {}
            notes.extend(bank_excess_damage(sim_enemy, target_subsystem, stored, source="stager"))
            pending_stager_target = None
            stager_consumed = True
            message = (
                f"Stager intercepted {parsed.base_cmd} on [{target_subsystem}] and banked {stored} damage "
                "for a later detonation."
            )
            if not result.success:
                message = f"Stager fault: {result.message}"
        else:
            result = arsenal.execute(command_str, sim_player, sim_enemy, sim_state, phase="combat")
            result_metadata = getattr(result, "metadata", {}) or {}
            message = result.message
            if (
                pending_buffer_target
                and target_subsystem == pending_buffer_target
                and script_data.get("type") in {"brute_force", "exploit"}
            ):
                contained = max(0, int(result_metadata.get("overkill_damage", 0)))
                if contained > 0:
                    result_metadata["contained_overkill"] = contained
                    notes.extend(bank_excess_damage(sim_enemy, target_subsystem, contained, source="buffer"))
                else:
                    notes.append(f"buffer on [{target_subsystem}] found no excess pressure to trap")
                pending_buffer_target = None
                buffer_consumed = True

        if pending_stager_target and parsed.base_cmd != "stager" and not stager_consumed:
            notes.append(f"stager window on [{pending_stager_target}] expired without a matching adjacent offensive payload")
            pending_stager_target = None
        if pending_buffer_target and parsed.base_cmd != "buffer" and not buffer_consumed:
            notes.append(f"buffer window on [{pending_buffer_target}] expired without a matching adjacent offensive payload")
            pending_buffer_target = None

        clear_adjacency_window(sim_enemy, pending_window)
        pending_window = next_adjacency_window(arsenal, command_str, sim_player)

        if not root_prediction:
            root_prediction, root_reason = classify_resolution(command_str, parsed, pre_enemy, sim_enemy, result_metadata)

        steps.append(
            StackStepPreview(
                phase="execution",
                command=command_str,
                legal=True,
                ram_before=ram_before,
                ram_after=sim_player.current_ram,
                message=message,
                notes=notes,
            )
        )
        queue_index += 1

    return StackProjection(
        legal=True,
        steps=steps,
        preflight_commands=preflight_commands,
        execution_commands=execution_commands,
        projected_player=sim_player,
        projected_enemy=sim_enemy,
        root_prediction=root_prediction,
        root_reason=root_reason,
    )
