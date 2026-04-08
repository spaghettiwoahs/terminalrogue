import random


SUBSYSTEM_LANES = ("SEC", "NET", "MEM", "STO")


def _ensure_node(node):
    if hasattr(node, "ensure_runtime_defaults"):
        node.ensure_runtime_defaults()


def seed_worm(node, intensity: int, source: str | None = None):
    _ensure_node(node)
    applied = max(0, int(intensity))
    if applied <= 0:
        return 0
    node.worm_level += applied
    if source:
        node.worm_origin = source
    return node.worm_level


def node_brick_threshold(node, config: dict):
    base = int(config.get("worm_brick_threshold_base", 8))
    scale = int(config.get("worm_brick_threshold_scale", 4))
    return max(6, base + (max(1, getattr(node, "difficulty", 1)) * scale))


def strip_root_claim(node, state):
    lost_module = getattr(node, "installed_module", None)
    node.root_access = False
    node.installed_module = None
    node.module_slots = 0
    node.map_flags = []
    if hasattr(state, "strip_rooted_node"):
        state.strip_rooted_node(node)
    return lost_module


def mark_node_bricked(node, subnet, node_index, state, reason: str):
    _ensure_node(node)
    lost_module = strip_root_claim(node, state)
    node.compromise_state = "bricked"
    node.locked_data = True
    node.forensic_complete = False
    node.revolt_state = None
    subnet.cleared_nodes.add(node_index)

    cached_enemy = getattr(node, "cached_enemy", None)
    if cached_enemy is not None:
        if hasattr(cached_enemy, "ensure_runtime_defaults"):
            cached_enemy.ensure_runtime_defaults()
        for subsystem in cached_enemy.subsystems.values():
            subsystem.current_hp = 0
            subsystem.is_destroyed = True

    return {
        "reason": reason,
        "lost_module": lost_module,
    }


def _apply_corrosion(node, amount: int, rng: random.Random):
    _ensure_node(node)
    if amount <= 0:
        return 0, None, False

    cached_enemy = getattr(node, "cached_enemy", None)
    if cached_enemy is not None:
        if hasattr(cached_enemy, "ensure_runtime_defaults"):
            cached_enemy.ensure_runtime_defaults()
        viable = [key for key in SUBSYSTEM_LANES if not cached_enemy.subsystems[key].is_destroyed]
        target_key = rng.choice(viable or ["OS"])
        dealt = cached_enemy.subsystems[target_key].take_damage(amount)
        total = dealt
        if cached_enemy.subsystems[target_key].is_destroyed and target_key != "OS":
            cascade = cached_enemy.subsystems["OS"].take_damage(2)
            total += cascade
        node.worm_corruption += total
        return total, target_key, cached_enemy.subsystems["OS"].current_hp <= 0

    target_key = rng.choice(SUBSYSTEM_LANES)
    pending = dict(getattr(node, "pending_subsystem_damage", {}))
    pending[target_key] = pending.get(target_key, 0) + amount
    if target_key != "OS" and amount >= 4:
        pending["OS"] = pending.get("OS", 0) + 1
    node.pending_subsystem_damage = pending
    node.worm_corruption += amount
    return amount, target_key, False


def advance_worm_activity(network, state, config: dict, current_subnet_id: str | None = None):
    rng = random.Random()
    messages = []
    spread_chance = float(config.get("worm_spread_chance", 0.45))
    cross_spread_chance = float(config.get("worm_cross_subnet_chance", 0.28))
    decay = int(config.get("worm_decay", 1))
    corrosion_min = int(config.get("worm_corrosion_min", 1))
    corrosion_max = int(config.get("worm_corrosion_max", 3))

    for subnet_id, subnet in network.subnets.items():
        for node_index, node in enumerate(subnet.world_map.nodes):
            _ensure_node(node)
            if node.worm_level <= 0:
                continue
            if getattr(node, "compromise_state", "live") == "bricked":
                node.worm_level = max(0, node.worm_level - decay)
                continue

            corrosion = rng.randint(corrosion_min, corrosion_max) + max(0, node.worm_level // 3)
            dealt, target_key, core_collapse = _apply_corrosion(node, corrosion, rng)

            if dealt > 0 and (subnet_id == current_subnet_id or getattr(node, "root_access", False)):
                label = f"{node.ip_address} [{target_key}]"
                messages.append(f"[WORM] {label} took {dealt} internal corruption across the bus fabric.")

            if core_collapse or node.worm_corruption >= node_brick_threshold(node, config):
                result = mark_node_bricked(node, subnet, node_index, state, "worm")
                message = f"[WORM] {node.ip_address} collapsed into dead hardware."
                if result["lost_module"]:
                    message += f" Lost module: {result['lost_module']}."
                messages.append(message)
                node.worm_level = 0
                continue

            spread_targets = list(network.iter_macro_neighbors(subnet_id, node_index))
            rng.shuffle(spread_targets)
            spread_budget = 1 + (1 if node.worm_level >= 4 else 0)
            for neighbor_subnet_id, neighbor_index in spread_targets[:spread_budget]:
                neighbor_subnet = network.get_subnet(neighbor_subnet_id)
                if not neighbor_subnet:
                    continue
                neighbor = neighbor_subnet.world_map.nodes[neighbor_index]
                _ensure_node(neighbor)
                if getattr(neighbor, "compromise_state", "live") == "bricked":
                    continue
                chance = cross_spread_chance if neighbor_subnet_id != subnet_id else spread_chance
                if rng.random() > chance:
                    continue
                seed = max(1, node.worm_level // 2)
                previous_level = neighbor.worm_level
                seed_worm(neighbor, seed, source=node.ip_address)
                if neighbor.worm_level > previous_level:
                    messages.append(
                        f"[WORM] {node.ip_address} propagated into {neighbor.ip_address}."
                    )

            node.worm_level = max(0, node.worm_level - decay)

    if len(messages) > 8:
        extra = len(messages) - 8
        messages = messages[:8] + [f"[WORM] +{extra} more route-mesh incidents."]
    return messages


def advance_revolt_activity(network, state, config: dict, current_subnet_id: str | None = None):
    rng = random.Random()
    messages = []
    base_chance = float(config.get("revolt_base_chance", 0.1))
    trace_scale = float(config.get("revolt_trace_scale", 0.002))
    timer_min = int(config.get("revolt_timer_min", 2))
    timer_max = int(config.get("revolt_timer_max", 4))

    for subnet_id, subnet in network.subnets.items():
        for node_index, node in enumerate(subnet.world_map.nodes):
            _ensure_node(node)
            if getattr(node, "compromise_state", "live") != "rooted" or not getattr(node, "root_access", False):
                if getattr(node, "revolt_state", None) and not getattr(node, "root_access", False):
                    node.revolt_state = None
                continue

            revolt_state = getattr(node, "revolt_state", None)
            if revolt_state:
                revolt_state["timer"] -= 1
                if revolt_state["timer"] <= 0:
                    lost_module = strip_root_claim(node, state)
                    node.compromise_state = "cleared"
                    node.revolt_state = None
                    message = (
                        f"[REVOLT] {node.ip_address} was retaken by {revolt_state['faction']} traffic. "
                        "Your shell access is gone."
                    )
                    if lost_module:
                        message += f" Lost module: {lost_module}."
                    messages.append(message)
                elif subnet_id == current_subnet_id:
                    messages.append(
                        f"[REVOLT] {node.ip_address} is contested by {revolt_state['faction']} // respond in {revolt_state['timer']} step(s)."
                    )
                continue

            chance = base_chance + (state.trace_level * trace_scale)
            if getattr(node, "installed_module", None):
                chance += 0.04
            if rng.random() > chance:
                continue

            faction = rng.choice(("antivirus", "white_hat"))
            node.revolt_state = {
                "faction": faction,
                "timer": rng.randint(timer_min, timer_max),
                "strength": max(
                    node.difficulty + 1,
                    (state.get_difficulty_pressure() if hasattr(state, "get_difficulty_pressure") else state.day) + 1,
                ),
            }
            messages.append(
                f"[REVOLT] {node.ip_address} drew {faction} attention. The rooted shell is under challenge."
            )

    if len(messages) > 8:
        extra = len(messages) - 8
        messages = messages[:8] + [f"[REVOLT] +{extra} more contested signals."]
    return messages


def advance_lockdown_activity(network, state, config: dict, current_subnet_id: str | None = None):
    rng = random.Random()
    messages = []
    base_chance = float(config.get("lockdown_base_chance", 0.08))
    pressure_scale = float(config.get("lockdown_pressure_scale", 0.01))
    duration_min = int(config.get("lockdown_turns_min", 1))
    duration_max = int(config.get("lockdown_turns_max", 3))
    pressure = state.get_difficulty_pressure() if hasattr(state, "get_difficulty_pressure") else max(1, getattr(state, "day", 1))

    for subnet_id, subnet in network.subnets.items():
        for node in subnet.world_map.nodes:
            _ensure_node(node)
            if getattr(node, "compromise_state", "live") != "live":
                node.lockdown_turns = max(0, getattr(node, "lockdown_turns", 0) - 1)
                continue
            if node.node_type == "shop":
                continue
            if getattr(node, "lockdown_turns", 0) > 0:
                node.lockdown_turns = max(0, node.lockdown_turns - 1)
                if node.lockdown_turns > 0 and subnet_id == current_subnet_id:
                    messages.append(
                        f"[LOCKDOWN] {node.ip_address} remains under hardened routing for {node.lockdown_turns} more step(s)."
                    )
                continue

            chance = base_chance + (pressure * pressure_scale)
            if node.node_type == "gatekeeper":
                chance += 0.04
            if rng.random() > chance:
                continue

            node.lockdown_turns = rng.randint(duration_min, duration_max)
            if subnet_id == current_subnet_id:
                messages.append(
                    f"[LOCKDOWN] {node.ip_address} pulled fresh ACLs and route filters. Expect a harder breach."
                )

    if len(messages) > 8:
        extra = len(messages) - 8
        messages = messages[:8] + [f"[LOCKDOWN] +{extra} more route-hardening events."]
    return messages


def advance_dynamic_events(network, state, config: dict, current_subnet_id: str | None = None):
    messages = []
    messages.extend(advance_worm_activity(network, state, config, current_subnet_id=current_subnet_id))
    messages.extend(advance_revolt_activity(network, state, config, current_subnet_id=current_subnet_id))
    messages.extend(advance_lockdown_activity(network, state, config, current_subnet_id=current_subnet_id))
    return messages
