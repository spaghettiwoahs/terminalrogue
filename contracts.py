import random

from game_text import (
    CONTRACT_SENDERS,
    capture_contract_copy,
    disarm_contract_copy,
    dossier_contract_copy,
    ghost_contract_copy,
    salvage_contract_copy,
    terminate_contract_copy,
)


def _reward_for(node, pressure=1, bonus=0):
    return 35 + (node.difficulty * 18) + (pressure * 7) + bonus


def build_terminate_contract(rng, node, day, pressure):
    copy = terminate_contract_copy(node)
    return {
        "id": f"terminate::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "terminate",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, pressure, 10 + pressure * 3),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def build_salvage_contract(rng, node, day, pressure):
    copy = salvage_contract_copy(node)
    return {
        "id": f"salvage::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "salvage",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, pressure, 24 + pressure * 4),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def build_ghost_contract(rng, node, day, pressure):
    copy = ghost_contract_copy(node)
    return {
        "id": f"ghost::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "ghost",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, pressure, 30 + pressure * 5),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def build_dossier_contract(rng, node, day, pressure):
    copy = dossier_contract_copy(node)
    return {
        "id": f"dossier::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "dossier",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, pressure, 18 + pressure * 3),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def build_capture_contract(rng, node, day, pressure):
    copy = capture_contract_copy(node)
    return {
        "id": f"capture::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "capture",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, pressure, 28 + pressure * 5),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def build_disarm_contract(rng, node, day, pressure):
    copy = disarm_contract_copy(node)
    return {
        "id": f"disarm::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "disarm",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, pressure, 20 + pressure * 4),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def generate_contracts(state, world, subnet_key=None):
    day = getattr(state, "day", 1)
    pressure = state.get_difficulty_pressure() if hasattr(state, "get_difficulty_pressure") else max(1, day)
    progression_score = state.get_progression_score() if hasattr(state, "get_progression_score") else day
    key = subnet_key or getattr(world, "subnet_id", getattr(world, "subnet_name", "current"))
    rng = random.Random(f"{state.run_seed}:{key}:{progression_score}:{pressure}:contracts")
    hostile_nodes = [node for node in world.nodes if node.node_type != "shop"]
    standard_nodes = [node for node in hostile_nodes if node.node_type != "gatekeeper"]
    contracts = []
    used_ips = set()

    def add_contract(builder, pool):
        available = [node for node in pool if node.ip_address not in used_ips]
        if not available:
            available = list(pool)
        if not available:
            return
        node = rng.choice(available)
        contracts.append(builder(rng, node, day, pressure))
        used_ips.add(node.ip_address)

    add_contract(build_terminate_contract, hostile_nodes)
    add_contract(build_salvage_contract, standard_nodes or hostile_nodes)
    add_contract(build_ghost_contract, standard_nodes or hostile_nodes)
    if progression_score >= 12:
        add_contract(build_dossier_contract, hostile_nodes)
    if progression_score >= 20:
        add_contract(build_capture_contract, standard_nodes or hostile_nodes)
    if progression_score >= 28:
        add_contract(build_disarm_contract, hostile_nodes)

    return contracts


def evaluate_contract(contract, node, enemy, encounter_report):
    if contract.get("target_ip") != node.ip_address:
        return None

    contract_type = contract.get("type")
    if contract_type == "terminate":
        return True, "target dropped"
    if contract_type == "salvage":
        return encounter_report.get("sto_destroyed", False), "storage never ruptured"
    if contract_type == "ghost":
        return not encounter_report.get("signature_revealed", False), "host fingerprinted you"
    if contract_type == "dossier":
        topology = encounter_report.get("topology_revealed", False)
        telemetry = encounter_report.get("telemetry_count", 0) > 0
        return topology and telemetry, "dossier incomplete"
    if contract_type == "capture":
        return encounter_report.get("resolution") == "rooted", "node was not captured intact"
    if contract_type == "disarm":
        return encounter_report.get("sec_destroyed", False), "perimeter shell never dropped"

    return False, "contract handler missing"
