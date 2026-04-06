import random

from game_text import (
    CONTRACT_SENDERS,
    dossier_contract_copy,
    ghost_contract_copy,
    salvage_contract_copy,
    terminate_contract_copy,
)


def _reward_for(node, bonus=0):
    return 35 + (node.difficulty * 18) + bonus


def build_terminate_contract(rng, node, day):
    copy = terminate_contract_copy(node)
    return {
        "id": f"terminate::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "terminate",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, 10 + day * 4),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def build_salvage_contract(rng, node, day):
    copy = salvage_contract_copy(node)
    return {
        "id": f"salvage::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "salvage",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, 22 + day * 5),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def build_ghost_contract(rng, node, day):
    copy = ghost_contract_copy(node)
    return {
        "id": f"ghost::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "ghost",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, 30 + day * 6),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def build_dossier_contract(rng, node, day):
    copy = dossier_contract_copy(node)
    return {
        "id": f"dossier::{node.ip_address}",
        "sender": rng.choice(CONTRACT_SENDERS),
        "subject": copy["subject"],
        "type": "dossier",
        "target_ip": node.ip_address,
        "target_node_type": node.node_type,
        "reward": _reward_for(node, 18 + day * 4),
        "accepted": False,
        "completed": False,
        "failed": False,
        "day_issued": day,
        "brief": copy["brief"],
        "condition_text": copy["condition_text"],
        "body": copy["body"],
    }


def generate_contracts(run_seed, day, world):
    rng = random.Random(f"{run_seed}:{day}:{world.subnet_name}:contracts")
    hostile_nodes = [node for node in world.nodes if node.node_type != "shop"]
    standard_nodes = [node for node in hostile_nodes if node.node_type != "gatekeeper"]
    contracts = []
    used_ips = set()

    def add_contract(builder, pool):
        available = [node for node in pool if node.ip_address not in used_ips]
        if not available:
            return
        node = rng.choice(available)
        contracts.append(builder(rng, node, day))
        used_ips.add(node.ip_address)

    add_contract(build_terminate_contract, hostile_nodes)
    add_contract(build_salvage_contract, standard_nodes or hostile_nodes)
    add_contract(build_ghost_contract, standard_nodes or hostile_nodes)
    if day >= 2:
        add_contract(build_dossier_contract, hostile_nodes)

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

    return False, "contract handler missing"
