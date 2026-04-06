from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TutorialBootStep:
    focus: str | None
    reveal: str | None
    title: str
    body: str


BOOT_MENU_TITLE = "terminal rogue // boot menu"
BOOT_MENU_DEFAULT_STATUS = "checking local archive..."
BOOT_MENU_DEFAULT_SUBTITLE = "select a session mode to bring the workstation online"
BOOT_MENU_FOOTER = "the desktop stays offline until a boot path is selected"
BOOT_MENU_LABELS = {
    "new_tutorial": "new session // tutorial",
    "skip_tutorial": "new session // skip tutorial",
    "continue": "continue session",
    "quit": "power off",
}
BOOT_MENU_CONTINUE_STATUS = {
    True: "save archive detected // continue is available",
    False: "no save archive detected // start a new session",
}
BOOT_MENU_LOADING_COPY = {
    "1": (
        "initializing guided lab environment",
        "loading sandbox workstation, restricting the toolchain, and preparing the tutorial coach...",
    ),
    "2": (
        "initializing live session",
        "mounting a fresh rookie rig and routing you straight onto the live grid...",
    ),
    "3": (
        "restoring session archive",
        "reading the local save state and replaying the shell context...",
    ),
}


def get_boot_menu_loading_copy(choice: str) -> tuple[str, str]:
    return BOOT_MENU_LOADING_COPY.get(choice, ("starting session", "bringing the workstation online..."))


def get_tutorial_boot_steps() -> list[TutorialBootStep]:
    return [
        TutorialBootStep(
            focus=None,
            reveal=None,
            title="BOOTSTRAP // sandbox workstation",
            body="This shell is going to come online one panel at a time. Click this coach window to start the boot sequence.",
        ),
        TutorialBootStep(
            focus="objective",
            reveal="objective",
            title="BOOTSTRAP // objective buffer",
            body="This is the objective window. During the tutorial it is the cleanest place to read the current step and its exact command.",
        ),
        TutorialBootStep(
            focus="terminal",
            reveal="terminal",
            title="BOOTSTRAP // command shell",
            body="This is the terminal. You type at the live prompt at the bottom of the session buffer. Output and your commands stay in the same transcript.",
        ),
        TutorialBootStep(
            focus="target",
            reveal="target",
            title="BOOTSTRAP // target dossier",
            body="This is the hostile dossier. Host name, services, exposure, countermeasure, intent, and subsystem damage all land here once you have the intel.",
        ),
        TutorialBootStep(
            focus="player",
            reveal="player",
            title="BOOTSTRAP // rig state",
            body="This is your own rig state. RAM, subsystem integrity, active defenses, bots, and carried items live here instead of cluttering the shell.",
        ),
        TutorialBootStep(
            focus="databank",
            reveal="databank",
            title="BOOTSTRAP // databank",
            body="This is your installed toolkit. It only lists what this rig actually owns. Click any row to open a factual payload card.",
        ),
        TutorialBootStep(
            focus="route",
            reveal="route",
            title="BOOTSTRAP // routeweb",
            body="Outside combat this window is the route mesh. Inside a live host it flips into the architecture view for that system.",
        ),
        TutorialBootStep(
            focus="log",
            reveal="log",
            title="BOOTSTRAP // session archive",
            body="This is the session log. It mirrors the shell archive so clears do not erase what already happened.",
        ),
        TutorialBootStep(
            focus="terminal",
            reveal=None,
            title="BOOTSTRAP // system online",
            body="The workstation is live. Click once more and the coach will bring the warm-up host online for you.",
        ),
    ]


def dev_console_banner_lines() -> list[tuple[str, str]]:
    return [
        ("developer console // live runtime shell", "cyan"),
        ("runtime edits apply immediately to the current in-memory session", "muted"),
        ("", "text"),
        ("type help for commands", "green"),
    ]


def objective_staging_text(active: bool) -> str:
    if not active:
        return "\n".join(
            [
                "objective buffer",
                "",
                "guided session booting",
                "",
                "CLICK: open tutorial coach",
                "",
                "live objective output is muted until",
                "the warm-up node comes online.",
            ]
        )
    return "\n".join(
        [
            "objective buffer",
            "",
            "guided session active",
            "",
            "CLICK: open tutorial coach",
            "",
            "instructional output is currently routed",
            "through the tutorial coach window.",
        ]
    )


def player_staging_text() -> str:
    return (
        "rig state buffer\n\n"
        "no live hostile link yet.\n"
        "full rig telemetry appears when the\n"
        "warm-up node activates."
    )


def target_staging_text() -> str:
    return (
        "target dossier\n\n"
        "no live host selected.\n"
        "the warm-up node will populate this\n"
        "window once the training link goes live."
    )


def target_idle_text() -> str:
    return (
        "> passive shell idle\n\n"
        "Recon, route, contracts, and node briefings appear here once you tap a live host."
    )


def route_staging_text() -> str:
    return (
        "routeweb standby\n\n"
        "combat architecture and route telemetry\n"
        "come online with the warm-up host."
    )


def log_staging_text() -> str:
    return (
        "SESSION LOG // standby archive\n\n"
        "training session not yet attached to a live node."
    )


def isolated_route_text(host_name: str) -> str:
    return "\n".join(
        [
            "routeweb // isolated link",
            "no public route mesh attached",
            "",
            f"[active] {host_name}",
            "linked hops: none",
        ]
    )


def databank_staging_text() -> str:
    return (
        "databank standby\n\n"
        "starter payload index stays muted until\n"
        "the warm-up node is live."
    )


def build_boot_tutorial_overlay(step: TutorialBootStep) -> tuple[str, set[str]]:
    text = "\n".join(
        [
            "TUTORIAL COACH",
            "",
            step.title,
            "",
            step.body,
            "",
            "CLICK TO CONTINUE",
        ]
    )
    return text, ({step.focus} if step.focus else set())


def build_warmup_gate_overlay(waiting: bool) -> tuple[str, set[str]]:
    if waiting:
        return (
            "\n".join(
                [
                    "TUTORIAL COACH",
                    "",
                    "WARM-UP NODE",
                    " Training host is being brought online.",
                    "",
                    "WAIT",
                    " The terminal will unlock as soon as the live root prompt is ready.",
                ]
            ),
            {"tutorial"},
        )
    return (
        "\n".join(
            [
                "TUTORIAL COACH",
                "",
                "WARM-UP NODE READY",
                " Click this coach window to activate the training host.",
                "",
                "NOTE",
                " The terminal stays locked until the real combat prompt is live.",
            ]
        ),
        {"tutorial"},
    )


def build_drone_tutorial_overlay(stage: str) -> tuple[str, set[str]]:
    if stage == "ping_sec":
        return (
            "\n".join(
                [
                    "TUTORIAL COACH",
                    "",
                    "DO THIS NOW",
                    " Type ping -target SEC, then press Enter.",
                    "",
                    "WHY",
                    " ping is your cheapest probe: 1 RAM, light pressure, and a clean first look at lane targeting.",
                    " We open on SEC because it is the front-facing firewall lane, and we use ping first so you learn the board without spending your heavy hit yet.",
                ]
            ),
            {"terminal"},
        )
    if stage == "break_sec":
        return (
            "\n".join(
                [
                    "TUTORIAL COACH",
                    "",
                    "HEAVIER PAYLOAD",
                    " hydra is your stronger brute-force script.",
                    " It costs more RAM than ping, hits harder, and --burst makes it stronger again.",
                    "",
                    "NEXT",
                    " Run hydra --burst -target SEC, then execute.",
                    " This is the expensive hit. Its job is to break SEC open after the cheap probe.",
                ]
            ),
            {"terminal"},
        )
    return (
        "\n".join(
            [
                "TUTORIAL COACH",
                "",
                "FINAL STEP",
                " Type hydra -target OS, then execute.",
                "",
                "WHY",
                " The firewall is down, so the same heavy payload can finally hit the core cleanly.",
                " That is the pattern: cheap read first, strong break second, core strike last.",
            ]
        ),
        {"terminal"},
    )


def sandbox_alert_overlay() -> tuple[str, set[str]]:
    return (
        "\n".join(
            [
                "TUTORIAL COACH",
                "",
                "NEXT LESSON",
                " The next fight is less scripted.",
                " You still get warnings, but now you need to read the target panel for yourself.",
            ]
        ),
        {"target"},
    )


def black_ice_overlay() -> tuple[str, set[str]]:
    return (
        "\n".join(
            [
                "TUTORIAL COACH",
                "",
                "READ THE TARGET WINDOW",
                " LINK   = how hot the breach is.",
                " INTENT = their next move once you reveal it.",
                "",
                " The coach is lighter here on purpose.",
                " Read the dossier first, then use the shell.",
            ]
        ),
        {"target"},
    )
