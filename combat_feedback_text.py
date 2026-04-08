from __future__ import annotations


FEEDBACK_VARIANTS = {
    "ping": {
        "nohit": [
            "{lane} answers on the same clean rhythm it had before; the probe hit skin, not meat.",
            "The echo comes back almost insultingly healthy from {lane}; you got timing, not pain.",
        ],
        "grazed": [
            "Round-trip noise from {lane} spreads wider and dirtier; the lane is still up, but it flinched.",
            "Latency on {lane} now lands with a rough edge; the subsystem noticed the jab.",
        ],
        "half": [
            "Replies from {lane} arrive in uneven bursts now, like the service is arguing with itself mid-flight.",
            "{lane} is still there, but the timing profile is split right down the middle.",
        ],
        "low": [
            "{lane} is barely holding signal now; every reply feels like it had to claw its way back.",
            "The lane answers late, thin, and angry. {lane} is one shove from dropping out.",
        ],
        "down": [
            "The next echo into {lane} resolves to dead air. Whatever lived there just stopped answering.",
            "Your probe comes back as timeout noise and nothing else; {lane} has fallen off the host.",
        ],
    },
    "hydra": {
        "nohit": [
            "The auth edge on {lane} is still absorbing the spray cleanly; no useful crack yet.",
            "Login prompts on {lane} stay disciplined under the burst. The door rattled but held.",
        ],
        "grazed": [
            "Failure banners on {lane} stop agreeing with each other; the login surface is starting to wobble.",
            "The auth path on {lane} is still alive, but the refusal pattern has gone sloppy.",
        ],
        "half": [
            "Half the auth surface on {lane} looks like policy and half of it looks like panic now.",
            "Credential responses on {lane} fracture into competing lockout states. That lane is unstable.",
        ],
        "low": [
            "The login edge on {lane} is hanging by dead sessions and bad counters.",
            "Auth on {lane} still answers, but only in the exhausted, stuttering way broken gates do.",
        ],
        "down": [
            "The final burst burns the auth surface right out of {lane}; only lockouts and silence remain.",
            "Credential traffic on {lane} collapses into dead prompts and hard refusal. The lane is gone.",
        ],
    },
    "airmon-ng": {
        "grazed": [
            "Perimeter chatter on {lane} thins enough that the host stops sounding sure of itself.",
            "Monitor-mode capture shows the shell on {lane} leaking through the seams.",
        ],
        "half": [
            "The perimeter on {lane} is still standing, but every beacon looks tired and late.",
            "{lane} is holding the firewall upright mostly out of habit at this point.",
        ],
        "low": [
            "Perimeter beacons from {lane} are faint and intermittent now; the shell is almost gone.",
            "The firewall posture on {lane} has dropped from discipline to reflex.",
        ],
        "down": [
            "The perimeter finally stops broadcasting like a real thing. {lane} is peeled open.",
            "Whatever was enforcing the edge on {lane} just fell quiet for good.",
        ],
    },
    "nmap": {
        "general": [
            "Returned banners and stack quirks line up into something you can actually exploit instead of guess at.",
            "The scan fills in real structure off the wire: ports, banners, and timing that have to come from the host.",
        ],
    },
    "masscan": {
        "general": [
            "The fast sweep trades precision for reach and the route pays you back in raw exposed surface.",
            "Ports light up in coarse, ugly bursts; it is enough to widen the board even if the picture stays fuzzy.",
        ],
    },
    "enum": {
        "general": [
            "Counters, process noise, and scheduler drift snap into a readable picture before the host can hide them again.",
            "You caught the lane in motion long enough to pin exact state, not just mood.",
        ],
    },
    "whois": {
        "general": [
            "The ownership trail comes out of public registry dust and transit paperwork, not magic.",
            "You are reading operator history out of the bureaucratic exhaust around the host.",
        ],
    },
    "dirb": {
        "general": [
            "Path hits on {lane} stop looking theoretical; the management surface is actually there and talking.",
            "Dead routes fall away and a smaller, uglier set of real endpoints is left standing on {lane}.",
        ],
    },
    "sqlmap": {
        "grazed": [
            "The backend on {lane} twitches just enough to admit your injection touched something real.",
            "The query surface on {lane} starts leaking the kind of discomfort only a live backend can produce.",
        ],
        "half": [
            "The service behind {lane} is now returning more pain than polish.",
            "Half the backend logic on {lane} is still doing work; the other half is busy bleeding.",
        ],
        "low": [
            "The backend on {lane} is still answering, but only like a machine working through a punctured lung.",
            "Every response from {lane} now feels one malformed answer away from collapse.",
        ],
        "down": [
            "The injection finally kicks the service out from under itself. {lane} stops behaving like an application.",
            "Backend noise on {lane} decays into broken answers and then into nothing useful at all.",
        ],
    },
    "siphon": {
        "grazed": [
            "The lane gives up value and blood at the same time; that hook definitely bit.",
            "You can feel live state draining through the tap on {lane} even while the service keeps standing.",
        ],
        "low": [
            "{lane} is so weak now the siphon feels less like a hook and more like a straw.",
            "The service on {lane} is still there, but it is mostly functioning as a thing to drain.",
        ],
        "down": [
            "You pulled the lane hollow enough that it stopped acting like a system and started acting like wreckage.",
            "The siphon empties {lane} right through its own service edge and leaves it dead behind the socket.",
        ],
    },
    "spray": {
        "grazed": [
            "The login surface on {lane} is still orderly, but you can hear strain in the refusal rhythm.",
            "The spray roughs up {lane} without breaking it; the follow-up window is the real prize.",
        ],
        "half": [
            "Credential prompts on {lane} are now split between policy and panic.",
            "Half of {lane} looks like a real auth flow and half of it looks like somebody losing control.",
        ],
        "down": [
            "The spray tips the auth edge over by volume alone. {lane} is no longer maintaining a coherent login surface.",
            "What comes back from {lane} is lockout trash and silence. The lane is spent.",
        ],
    },
    "shred": {
        "grazed": [
            "The lane is still up, but its recovery story just got much uglier.",
            "Journals and restore chatter on {lane} now sound like a machine forgetting how to heal.",
        ],
        "low": [
            "{lane} is holding together with nothing underneath it now; recovery has turned theoretical.",
            "The wipe pass leaves {lane} alive only in the technical sense.",
        ],
        "down": [
            "The wipe finishes what the damage started. {lane} is not coming back cleanly.",
            "Whatever was left of {lane} gets dragged under by its own ruined state.",
        ],
    },
    "overflow": {
        "grazed": [
            "Response structure on {lane} is subtly wrong now, the kind of wrong only memory damage can make.",
            "The lane is still talking, but the allocator underneath it is clearly limping.",
        ],
        "half": [
            "{lane} now behaves like a service standing on cracked heap glass.",
            "Half the lane still works and the other half is corruption wearing a uniform.",
        ],
        "low": [
            "You can hear allocator panic in every answer from {lane}. It is almost done.",
            "The corruption is so loud now that {lane} barely has a normal response left.",
        ],
        "down": [
            "The heap finally gives out. {lane} folds into allocator faults and never comes back.",
            "Corruption wins outright on {lane}; all that is left is crash residue.",
        ],
    },
    "hammer": {
        "grazed": [
            "The crash harness lands like a body blow; the host keeps standing, but not gracefully.",
            "Kernel panic indicators flare on {lane} and then just barely come back down.",
        ],
        "half": [
            "The host is still upright, but it is now thinking around a concussion.",
            "{lane} survives the hit in the same way a cracked turbine still technically spins.",
        ],
        "low": [
            "Everything about {lane} says one more clean hit would turn it into a postmortem.",
            "The harness leaves {lane} upright, loud, and almost finished.",
        ],
        "down": [
            "The crash finally sticks. {lane} doesn't degrade, it just ceases.",
            "Panic becomes silence on {lane}; the harness got the hard stop it wanted.",
        ],
    },
    "ddos": {
        "grazed": [
            "Transit pressure starts to stack up faster than the host can smooth it out.",
            "The route is still carrying traffic, but the lane is now working under flood conditions.",
        ],
        "half": [
            "Half the service posture on {lane} is now spent just trying to breathe through the flood.",
            "The host is no longer operating normally on {lane}; it is surviving traffic.",
        ],
        "low": [
            "The flood has turned {lane} into a clogged artery.",
            "The route is winning now; {lane} is only barely still a service.",
        ],
        "down": [
            "The flood finally drowns the lane outright. {lane} disappears under its own traffic.",
            "The route pressure gets high enough that {lane} stops being reachable in any meaningful sense.",
        ],
    },
    "harden": {"general": ["The policy commit sticks cleanly; the lane is harder in a way you can actually feel on the return path."]},
    "honeypot": {"general": ["The decoy surface is live now, bright enough and believable enough to waste a hostile read."]},
    "canary": {"general": ["The watchpoint takes. That lane now has a live callback waiting for the next bad idea."]},
    "sinkhole": {"general": ["The redirect hook catches and holds. If they commit there, the return path is yours to bend."]},
    "rekey": {"general": ["Old session material drops dead immediately; the route is speaking under fresh secrets now."]},
    "patch": {"general": ["The repair cycle bites fast and local. The rig sounds steadier because it actually is steadier."]},
    "spoof": {"general": ["The route accepts the lie for now. Counter-recon is reading the mask instead of the operator."]},
    "stager": {"general": ["You did not hit the lane; you planted time there instead. The next adjacent payload is the real detonation."]},
}


GENERIC_VARIANTS = {
    "nohit": [
        "{lane} is still reading clean on the wire.",
        "No visible structural change on {lane} yet.",
    ],
    "grazed": [
        "{lane} remains functional, but the damage is now visible in the response shape.",
        "The subsystem is still live, just less sure of itself than it was a second ago.",
    ],
    "half": [
        "{lane} is now operating from the middle of the damage curve.",
        "Half the lane still behaves like a machine and half of it behaves like a warning.",
    ],
    "low": [
        "{lane} is deep in the red now.",
        "There is not much real service left on {lane}.",
    ],
    "down": [
        "{lane} is offline.",
        "The subsystem on {lane} has dropped out of the host.",
    ],
    "general": [
        "The host told on itself through the wire while the payload was live.",
    ],
}


def _pick(options: list[str], seed: str) -> str | None:
    if not options:
        return None
    score = sum(ord(ch) for ch in seed)
    return options[score % len(options)]


def choose_command_feedback(command_id: str, band: str, *, lane: str, host: str) -> str | None:
    command_variants = FEEDBACK_VARIANTS.get(command_id, {})
    options = (
        command_variants.get(band)
        or command_variants.get("general")
        or command_variants.get("any")
        or []
    )
    template = _pick(options, f"{command_id}|{band}|{lane}|{host}")
    return template.format(lane=lane, host=host) if template else None


def choose_generic_feedback(band: str, *, lane: str, host: str) -> str | None:
    template = _pick(GENERIC_VARIANTS.get(band, []) or GENERIC_VARIANTS["general"], f"generic|{band}|{lane}|{host}")
    return template.format(lane=lane, host=host) if template else None
