from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectiveCard:
    title: str
    body: str
    tone: str = "cyan"
    command: str = ""
    detail: str = ""
    tutorial: bool = False


CONTRACT_SENDERS = (
    "Null Freight",
    "Switchglass",
    "Auntie Root",
    "Mudlark",
    "Latch",
    "Broker 7",
    "Moss Signal",
    "Low Lantern",
)


def boot_layout_card() -> ObjectiveCard:
    return ObjectiveCard(
        title="BOOT LAYOUT",
        body="Left side: terminal feed. Right side: rig status, objective, target brief, route mesh, and databank.",
        tone="cyan",
    )


def live_grid_card() -> ObjectiveCard:
    return ObjectiveCard(
        title="ROUTE MESH",
        body="The mesh is live. Border nodes, rooted shells, and dead drops are updating against the current route state.",
        tone="cyan",
    )


def prebreach_recon_card() -> ObjectiveCard:
    return ObjectiveCard(
        title="PHASE 1 // RECON",
        body="Passive tap is live. Scout with scan tools, type soft engage to let the host answer first, or type engage to breach immediately.",
        tone="yellow",
        command="recon | soft engage | engage",
        detail="soft engage spends the host's opening response before full combat. It can hurt, but it also exposes live countermeasures, patch posture, and attack lanes.",
    )


def node_tap_card(node_ip: str, alert_text: str = "") -> ObjectiveCard:
    detail = f"Link state: {alert_text}." if alert_text else ""
    return ObjectiveCard(
        title=f"LIVE HOP // {node_ip}",
        body="You are parked on a live route. Scout from here, commit the breach when ready, or cut away to a different hop.",
        tone="yellow",
        detail=detail,
    )


def live_combat_card() -> ObjectiveCard:
    return ObjectiveCard(
        title="PHASE 2 // ENGAGE",
        body="The socket is hot now. Build the exploit stack around what recon exposed, then execute the chain in order.",
        tone="yellow",
        command="queue payloads | execute",
        detail="Adjacency windows only affect the next slotted payload. Stack order is the whole attack plan.",
    )


def cleanup_card(rooted: bool, forensic_ready: bool = False) -> ObjectiveCard:
    if rooted:
        return ObjectiveCard(
            title="PHASE 3 // CLEANUP",
            body="The node stayed intact. Loot is already moving. Cool the link, scrub heat, and leave the shell stable before you step back onto the route mesh.",
            tone="green",
            command="scrub | status | done",
            detail="Cleanup is the recovery pass after execution: reduce exposure, confirm what survived, then move on.",
        )
    command = "forensics | scrub | status | done" if forensic_ready else "scrub | status | done"
    detail = (
        "The hardware is dead. You can still work the crash image for salvage and intel before you walk."
        if forensic_ready
        else "The hardware is dead and the residue is already cold. Scrub your trace and move."
    )
    return ObjectiveCard(
        title="PHASE 3 // CLEANUP",
        body="The node bricked. Data channels collapsed, but crash residue can still pay out if you want to risk working the wreck.",
        tone="red",
        command=command,
        detail=detail,
    )


def day_wrap_card(completed_day: int) -> ObjectiveCard:
    return ObjectiveCard(
        title=f"DAY {completed_day} WRAP",
        body="The session is cooling down. Ledger closed, tunnel rotated, next subnet spinning up.",
        tone="green",
    )


def tutorial_bootstrap_card() -> ObjectiveCard:
    return ObjectiveCard(
        title="BOOTSTRAP",
        body="Orientation comes first. After that, the tutorial coach will bring the workstation online one panel at a time before the warm-up host starts.",
        tone="cyan",
        command="click through boot coach",
        detail="The opening clicks are story and system boot, not combat steps. The first live host starts only after the workstation is online.",
        tutorial=True,
    )


def sandbox_alert_card() -> ObjectiveCard:
    return ObjectiveCard(
        title="SANDBOX ALERT",
        body="This next fight is less hand-held. The coach stays with you, but route pressure and hostile readback matter more than the objective card now.",
        tone="yellow",
        command="watch route pressure",
        detail="Trace is your run heat, sweep is local hunt pressure, and BF/EX are the brute-force and exploit noise buckets that describe your style.",
        tutorial=True,
    )


def sim_breach_card() -> ObjectiveCard:
    return ObjectiveCard(
        title="SIM BREACH",
        body="The tutorial just turned real. From here on out, the coach stops scripting every move and the grid keeps going without it.",
        tone="red",
    )


def run_burned_card() -> ObjectiveCard:
    return ObjectiveCard(
        title="RUN BURNED",
        body="Trace hit critical mass or the node killed your rig. Save wiped. New run only.",
        tone="red",
    )


def build_drone_tutorial_card(enemy) -> ObjectiveCard:
    if enemy.subsystems["SEC"].current_hp == enemy.subsystems["SEC"].max_hp:
        return ObjectiveCard(
            title="STEP 1: TAP THE HOST",
            body="Run ping -target SEC, then execute. ping is your cheapest opener: low RAM, light pressure, and good for learning lane targeting before you spend a heavier payload.",
            tone="cyan",
            command="ping -target SEC",
            detail="SEC is the cleanest first lane because it sits on the perimeter. We open with ping instead of hydra because ping is cheap and readable, so you learn the board without committing a loud heavy strike first.",
            tutorial=True,
        )
    if enemy.subsystems["SEC"].current_hp > 0:
        return ObjectiveCard(
            title="STEP 2: USE A FLAG",
            body="Run hydra --burst -target SEC, then execute. hydra is your heavier brute-force payload: it costs more RAM, hits harder than ping, and --burst pushes even more pressure through the same lane.",
            tone="yellow",
            command="hydra --burst -target SEC",
            detail="This is why the first ping mattered. You already learned the lane cheaply, so now the stronger and noisier hit has a clear job: break the firewall open.",
            tutorial=True,
        )
    return ObjectiveCard(
        title="STEP 3: HIT THE CORE",
        body="Run hydra -target OS, then execute. The firewall is down now, so the same heavy payload can go straight into the core instead of getting soaked by SEC first.",
        tone="magenta",
        command="hydra -target OS",
        detail="That is the first combat lesson: use a cheap probe to learn the lane, a stronger payload to break the shield layer, then push the core once the path is open.",
        tutorial=True,
    )


def build_black_ice_tutorial_card(enemy) -> ObjectiveCard:
    if not enemy.player_topology_revealed:
        return ObjectiveCard(
            title="COUNTER-SCAN LIVE",
            body="The responder is probing your layout. Watch the target window and decide whether to poison the read before it finishes.",
            tone="yellow",
            command="honeypot",
            detail="The coach is backing off now. Read the dossier before you commit, including buses: they are the internal links that let splash and cascades travel between subsystems.",
            tutorial=True,
        )
    if not enemy.player_signature_revealed:
        return ObjectiveCard(
            title="LAYOUT EXPOSED",
            body="Your general layout is known, but your exposed signature lane is still unresolved.",
            tone="yellow",
            detail="If the next read lands cleanly, hostile pressure gets much more accurate.",
            tutorial=True,
        )
    return ObjectiveCard(
        title="SIGNATURE EXPOSED",
        body="The responder resolved your live signature lane. Read hostile activity and decide whether to spoof, rekey, or race.",
        tone="red",
        detail="This fight is meant to feel less scripted than the warm-up host.",
        tutorial=True,
    )


def prologue_heist_message() -> str:
    return (
        "[SENDER: LAB//OPS]\n"
        "> That relay is not part of the lesson plan.\n"
        "> Something live answered behind the training endpoint.\n"
        "> Instructor telemetry just lost sync.\n"
        "> Proceed carefully.\n"
    )


def lab_orientation_message() -> str:
    return (
        "[CIVIC CYBER LAB // ORIENTATION]\n"
        "> Welcome, newblood.\n"
        "> This is a cheap neighborhood sandbox, not a black-site war room.\n"
        "> You are here to learn how hostile systems behave, how not to panic, and how to keep your own box alive.\n"
        "> Nobody expects you to be a legend. They expect you to pay attention.\n"
    )


def sandbox_rules_message() -> str:
    return (
        "[INSTRUCTOR NOTE // LAB RULES]\n"
        "> Training routes should stay synthetic.\n"
        "> No public spill. No real operators. No live critical systems.\n"
        "> If anything outside the lesson starts answering back, close the link and call it in.\n"
        "> That is the rule. That is always the rule.\n"
    )


def defense_notes_message() -> str:
    return (
        "[FIELD NOTE // ACTIVE DEFENSE]\n"
        "> Counter-intrusion package unlocked.\n"
        "> The sandbox no longer looks isolated.\n"
        "> Treat the next link as live traffic.\n"
    )


def burn_notice_message() -> str:
    return (
        "[LAB//SYSTEM FAILURE]\n"
        "> Training instance lost containment.\n"
        "> Sandbox routes just dumped you into live public infrastructure.\n"
        "> Instructor link lost.\n"
        "> Safe mode gone.\n"
        "> The exercise just became real traffic.\n"
    )


def survival_primer_message() -> str:
    return (
        "[SURVIVAL PRIMER // LIVE GRID]\n"
        "> Real runs are unstable. Route maps, node mixes, modifiers, and major responders reshuffle.\n"
        "> Routes open and collapse. Hosts change hands. The grid does not wait for you.\n"
        "> One dead rig ends the run.\n"
        "> What you keep is not hardware. It is what you learn.\n"
    )


def _brief_for(node) -> str:
    label = node.node_type.upper()
    return f"{node.ip_address} // {label}"


def terminate_contract_copy(node) -> dict:
    return {
        "subject": f"Drop {_brief_for(node)}",
        "brief": "Simple bounty. Kill the host and leave a crater.",
        "condition_text": "Neutralize the node.",
        "body": (
            f"Need {node.ip_address} dark.\n"
            "No special handling. No follow-up questions.\n"
            "If the box panics and dies, I get what I need."
        ),
    }


def salvage_contract_copy(node) -> dict:
    return {
        "subject": f"Crack the caches on {_brief_for(node)}",
        "brief": "Storage pull. Rupture STO before the host dies.",
        "condition_text": "Destroy [STO] before or during the kill.",
        "body": (
            f"Target {node.ip_address} is sitting on something worth lifting.\n"
            "I do not care about elegance.\n"
            "Break storage and then finish the job."
        ),
    }


def ghost_contract_copy(node) -> dict:
    return {
        "subject": f"Ghost-touch {_brief_for(node)}",
        "brief": "Signature discipline job. Win before they fingerprint your weak angle.",
        "condition_text": "Neutralize the node without letting the host reveal your signature.",
        "body": (
            "Need a clean touch.\n"
            "If they get your weak angle, the deal is off.\n"
            "Move fast, jam the scans, keep your signature dark."
        ),
    }


def dossier_contract_copy(node) -> dict:
    return {
        "subject": f"Build a dossier on {_brief_for(node)}",
        "brief": "Recon-first contract. Surface the host and scrape telemetry before kill.",
        "condition_text": "Reveal topology and at least one telemetry target before neutralizing the node.",
        "body": (
            f"{node.ip_address} matters more alive than dead, until it doesn't.\n"
            "I need structure, chatter, and a proper read before you flatten it.\n"
            "Bring me a dossier, then end the host."
        ),
    }


def capture_contract_copy(node) -> dict:
    return {
        "subject": f"Take root on {_brief_for(node)}",
        "brief": "Control job. Finish cleanly and keep the shell alive.",
        "condition_text": "Finish with Root Access instead of bricking the node.",
        "body": (
            f"{node.ip_address} is more valuable breathing than burning.\n"
            "I want the shell, the route flags, and whatever infrastructure the chassis can still host.\n"
            "Keep it intact."
        ),
    }


def disarm_contract_copy(node) -> dict:
    return {
        "subject": f"Strip perimeter on {_brief_for(node)}",
        "brief": "Disable the perimeter before the kill lands.",
        "condition_text": "Take [SEC] offline before the node is neutralized.",
        "body": (
            f"{node.ip_address} is carrying a perimeter profile I need collapsed.\n"
            "I do not care who owns the core afterwards.\n"
            "Break the shell, then finish the host."
        ),
    }
