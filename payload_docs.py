from __future__ import annotations


def script_effect_lines(script_id: str, data: dict) -> list[str]:
    effects: list[str] = []

    if data.get("damage"):
        effects.append(f"Base damage: {data['damage']}.")
    if data.get("repair"):
        effects.append(f"Base repair: {data['repair']} Core OS HP.")
    if data.get("disrupt_turns"):
        effects.append(f"Security breach window: {data['disrupt_turns']} turn(s).")
    if data.get("guard"):
        effects.append(f"ACL shell strength: {data['guard']} for {data.get('turns', 1)} turn(s).")
    if data.get("trap_damage"):
        effects.append(f"Trap damage: {data['trap_damage']}.")
    if data.get("ratio"):
        effects.append(f"Reflection ratio: {int(data['ratio'] * 100)}%.")
    if data.get("flat_damage"):
        effects.append(f"Flat reflected bonus damage: {data['flat_damage']}.")

    special = {
        "ping": [
            "On hit, arms a timing window on the struck subsystem for 1 turn.",
            "If topology is known but hostile intent is still hidden, it reveals hostile intent.",
            "Against NET, gains +1 damage.",
        ],
        "nmap": [
            "Untargeted mode reveals host identity, countermeasure, open ports, banners, and subsystem layout.",
            "Targeted mode requires mapped topology.",
            "Targeted mode is blocked while SEC is active unless SEC is destroyed or already breached.",
            "Successful targeted scans arm a fingerprint window on the chosen subsystem for 2 turns.",
            "If the chosen subsystem is the hidden weakness, the weakness is revealed.",
        ],
        "enum": [
            "Requires -target and mapped topology.",
            "Reveals exact HP on the chosen subsystem.",
            "Reveals current hostile intent.",
            "On NET, primes a quiet window worth -20 exposure on the next recon action.",
        ],
        "whois": [
            "Reveals owner, role, and netrange metadata.",
            "Primes a quiet window worth -10 exposure on the next recon action.",
        ],
        "dirb": [
            "Requires -target and mapped topology.",
            "Reveals exact telemetry for the chosen subsystem.",
            "Marks endpoint hits on that subsystem.",
            "Endpoint hits give later sqlmap runs on that subsystem +2 damage.",
        ],
        "airmon-ng": [
            "Can only target SEC.",
            "On hit, breaches perimeter controls for 2 turns.",
        ],
        "hydra": [
            "Gains +3 damage on auth surfaces.",
            "Loses 3 damage on non-auth surfaces, to a minimum of 1.",
            "Gains +2 damage on lanes already primed with credential pressure.",
        ],
        "sqlmap": [
            "Gains +2 damage on MEM, STO, database surfaces, or web surfaces.",
            "Gains another +2 damage if endpoint hits are already marked there.",
            "On STO hit, exfiltrates +8 Crypto.",
            "On MEM hit, jams the next hostile action for 1 turn.",
        ],
        "spray": [
            "Gains +2 damage on SEC, NET, or auth surfaces.",
            "On successful SEC hit, breaches perimeter controls for 1 turn.",
            "On successful auth-surface hit, primes credential pressure on that subsystem for 2 turns.",
        ],
        "shred": [
            "Gains +3 damage if the target is at or below 50% HP.",
            "On MEM or STO hit, blocks repair on that lane for 2 turns.",
        ],
        "overflow": [
            "Gains +2 damage on MEM or NET.",
            "On successful MEM or NET hit, jams the next hostile action for 1 turn.",
        ],
        "hammer": [
            "Gains +2 damage on OS while SEC is already destroyed.",
            "On successful open-core OS hit, jams the next hostile action for 1 turn.",
            "Also deals 2 collateral damage to one random live NET, MEM, or STO lane.",
        ],
        "spoof": [
            "Scrubs 1 hostile recon stage from your rig if any is present.",
            "Reduces hostile adaptation streaks by 2.",
        ],
        "harden": [
            "If hostile intent is revealed and you harden the correct lane, the ACL shell gains +2 strength.",
        ],
        "honeypot": [
            "The next hostile scan is redirected into false telemetry for 1 turn.",
        ],
        "canary": [
            "Arms the trap for 1 turn on the chosen subsystem.",
        ],
        "sinkhole": [
            "Arms the sinkhole for 1 turn on the chosen subsystem.",
            "The next hostile move on that lane is reflected at 100% strength plus 2 flat damage.",
        ],
        "rekey": [
            "Clears any RAM lock on the player.",
            "Scrubs 1 hostile recon stage from the player.",
            "Fully clears hostile adaptation state.",
        ],
        "patch": [
            "Repairs the most damaged supporting lane for 2 HP.",
            "Restores 1 RAM if below cap.",
        ],
    }
    effects.extend(special.get(script_id, []))
    return effects or ["No additional mechanical effects beyond its baseline class behavior."]


def flag_effect_lines(flag_id: str, data: dict) -> list[str]:
    effects: list[str] = []
    if data.get("damage_bonus"):
        effects.append(f"Damage bonus: +{data['damage_bonus']}.")
    if data.get("noise_bonus"):
        effects.append(f"Trace noise bonus: +{data['noise_bonus']}.")
    if data.get("exposure_delta"):
        effects.append(f"Recon exposure change: {data['exposure_delta']}.")

    special = {
        "--ransom": [
            "Converts final landed total damage into equal Crypto.",
            "Only pays on damage that actually lands.",
        ],
        "--stealth": [
            "Suppresses brute-force and exploit trace-noise logging.",
        ],
        "--ghost": [
            "Low-cost recon wrapper with no extra combat-side bonus beyond its exposure reduction.",
        ],
        "--worm": [
            "If the primary target is destroyed before the payload's full damage is consumed, leftover damage jumps to one random live subsystem.",
        ],
        "--burst": [
            "Adds its damage bonus before defenses and reactions are resolved.",
        ],
        "--fork": [
            "After the main hit resolves, deals max(1, total_damage // 2) to one random second live subsystem.",
        ],
        "--volatile": [
            "Adds its damage bonus before defenses and reactions are resolved.",
        ],
    }
    effects.extend(special.get(flag_id, []))
    return effects or ["No additional mechanical effects loaded for this modifier."]


def item_effect_lines(data: dict) -> list[str]:
    effects: list[str] = []
    effect = data.get("effect")
    amount = data.get("amount", 0)
    turns = data.get("turns", 1)

    if effect == "ram":
        effects.append(f"Restores up to {amount} RAM.")
    elif effect == "guard":
        effects.append(f"Adds {amount} guard integrity to the chosen subsystem.")
        effects.append(f"Duration: {turns} turn(s).")
    elif effect == "patch":
        effects.append(f"Repairs up to {amount} Core OS HP.")
        effects.append("Also clears RAM lock residue if present.")
    elif effect == "decoy":
        effects.append(f"Scrubs {data.get('scrub_stages', 1)} hostile recon stage(s).")
        effects.append(f"Arms a scan jammer for {data.get('jammer_turns', 1)} turn(s).")
    elif effect == "tripwire":
        effects.append(f"Arms a {data.get('trap_damage', 0)}-damage trap on the chosen subsystem.")
        effects.append(f"Duration: {turns} turn(s).")

    if data.get("requires_target"):
        effects.append("Requires -target <OS|SEC|NET|MEM|STO>.")

    return effects or ["Single-use tactical utility."]


def target_effect_lines(target_id: str) -> list[str]:
    return {
        "OS": [
            "If OS reaches 0, the fight ends immediately.",
            "Subsystem collapses can also spill 2 cascade damage into OS.",
        ],
        "SEC": [
            "SEC intercepts most direct OS pressure while it is still online.",
            "Breaking SEC allows cleaner OS damage and deeper targeted fingerprinting.",
        ],
        "NET": [
            "NET damage degrades recon quality, trace routines, and disconnect stability.",
        ],
        "MEM": [
            "MEM controls RAM regeneration per turn.",
            "Every 4 missing MEM HP also cuts 1 effective max RAM.",
        ],
        "STO": [
            "Breaking STO can spill extra Crypto and loot without ending the fight.",
        ],
    }.get(target_id, ["Subsystem reference entry."])
