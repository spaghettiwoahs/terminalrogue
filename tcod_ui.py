import builtins
from datetime import datetime
import math
import os
import platform
import queue
import random
import re
import shlex
import sys
import textwrap
import threading
import time
from pathlib import Path

import tcod
from tcod.cffi import lib

from arsenal import Arsenal
from combat import CombatEngine
from data_loader import DataLoader
from entities import Enemy, Player
from game_text import (
    boot_layout_card,
    build_black_ice_tutorial_card,
    build_drone_tutorial_card,
    burn_notice_message,
    cleanup_card,
    day_wrap_card,
    defense_notes_message,
    lab_orientation_message,
    live_grid_card,
    live_combat_card,
    prebreach_recon_card,
    prologue_heist_message,
    run_burned_card,
    sandbox_alert_card,
    sandbox_rules_message,
    node_tap_card,
    sim_breach_card,
    survival_primer_message,
    tutorial_bootstrap_card,
)
from game_state import GameState, ThreatLedger
from network_events import advance_dynamic_events, mark_node_bricked, seed_worm
from payload_docs import flag_effect_lines, item_effect_lines, script_effect_lines


ANSI_RE = re.compile(r"\033\[[0-9;]*m")
ANSI_COLOR_HINTS = {
    "\033[91m": "red",
    "\033[92m": "green",
    "\033[93m": "yellow",
    "\033[95m": "magenta",
    "\033[96m": "cyan",
}
SHIFTED_SYMBOLS = {
    "`": "~",
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "-": "_",
    "=": "+",
    "[": "{",
    "]": "}",
    "\\": "|",
    ";": ":",
    "'": '"',
    ",": "<",
    ".": ">",
    "/": "?",
}
ASCII_ART = {
    "terminal_rogue": (
        " _______ ______  ____  __  __ ___ _   _    _    _     \n"
        "|_   _| |  ____|  _ \\|  \\/  |_ _| \\ | |  / \\  | |    \n"
        "  | |   | |__  | |_) | |\\/| || ||  \\| | / _ \\ | |    \n"
        "  | |   |  __| |  _ <| |  | || || |\\  |/ ___ \\| |___ \n"
        "  |_|   |_|    |_| \\_\\_|  |_|___|_| \\_/_/   \\_\\_____|\n"
        "\n"
        " ______   ___   ____ _   _ _____\n"
        "|  _ \\ \\ / / | / / _` | | | ____|\n"
        "| |_) \\ V /| |/ / (_| | |_| |  _|\n"
        "|____/ \\_/ |___/ \\__,_|\\__,_|___|\n"
    ),
    "archive_echo": (
        "    _    ____   ____ _   _ ___ ____   _____   __\n"
        "   / \\  |  _ \\ / ___| | | |_ _|  _ \\ | ____| / /\n"
        "  / _ \\ | |_) | |   | |_| || || |_) ||  _|  / / \n"
        " / ___ \\|  _ <| |___|  _  || ||  __/ | |___/ /  \n"
        "/_/   \\_\\_| \\_\\\\____|_| |_|___|_|    |_____/_/   \n"
    ),
    "black_ice": (
        " ____  _        _    ____ _  __  ___ ____ _____\n"
        "| __ )| |      / \\  / ___| |/ / |_ _/ ___| ____|\n"
        "|  _ \\| |     / _ \\| |   | ' /   | | |   |  _|  \n"
        "| |_) | |___ / ___ \\ |___| . \\   | | |___| |___ \n"
        "|____/|_____/_/   \\_\\____|_|\\_\\ |___\\____|_____|\n"
    ),
    "burn_notice": (
        " ____  _   _ ____  _   _   _   _  ___ _____ ___ ____ _____\n"
        "| __ )| | | |  _ \\| \\ | | | \\ | |/ _ \\_   _|_ _/ ___| ____|\n"
        "|  _ \\| | | | |_) |  \\| | |  \\| | | | || |  | | |   |  _|  \n"
        "| |_) | |_| |  _ <| |\\  | | |\\  | |_| || |  | | |___| |___ \n"
        "|____/ \\___/|_| \\_\\_| \\_| |_| \\_|\\___/ |_| |___\\____|_____|\n"
    ),
    "survival": (
        " ____  _   _ ____ __     _____     ___ _   _    _    _     \n"
        "/ ___|| | | |  _ \\\\ \\   / /_ _|   |_ _| \\ | |  / \\  | |    \n"
        "\\___ \\| | | | |_) |\\ \\ / / | |_____| ||  \\| | / _ \\ | |    \n"
        " ___) | |_| |  _ <  \\ V /  | |_____| || |\\  |/ ___ \\| |___ \n"
        "|____/ \\___/|_| \\_\\  \\_/  |___|   |___|_| \\_/_/   \\_\\_____|\n"
    ),
}


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


class TcodTerminalApp:
    WIDTH = 140
    HEIGHT = 50
    TILE_WIDTH = 12
    TILE_HEIGHT = 20
    INPUT_HEIGHT = 4
    FEED_WIDTH = 96
    SIDEBAR_WIDTH = WIDTH - FEED_WIDTH
    CONTENT_HEIGHT = HEIGHT - INPUT_HEIGHT
    COLORS = {
        "bg": (8, 10, 8),
        "panel": (8, 10, 8),
        "panel_alt": (8, 10, 8),
        "line": (88, 98, 88),
        "shadow": (0, 0, 0),
        "text": (216, 220, 214),
        "muted": (122, 130, 122),
        "cyan": (124, 168, 168),
        "green": (118, 192, 118),
        "yellow": (208, 184, 102),
        "red": (210, 102, 102),
        "magenta": (164, 150, 186),
        "white": (239, 241, 238),
    }
    DAY_SCRIPT_UNLOCKS = {
        0: ("ping", "hydra"),
        6: ("nmap",),
        12: ("enum",),
        16: ("masscan",),
        18: ("airmon-ng",),
        24: ("harden",),
        30: ("honeypot", "patch", "jmp", "stager"),
        36: ("buffer",),
        38: ("whois", "dirb"),
        48: ("spray", "sqlmap", "ddos", "siphon"),
        58: ("spoof", "rekey"),
        70: ("overflow", "hammer"),
        84: ("canary", "sinkhole", "shred"),
    }
    DAY_FLAG_UNLOCKS = {
        0: ("--burst",),
        14: ("--stealth",),
        42: ("--ghost",),
        66: ("--cascade",),
        72: ("--worm",),
        86: ("--fork", "--volatile"),
        96: ("--ransom",),
    }
    DAY_META_UNLOCKS = {
        24: ("dry_run",),
        34: ("subnet_travel",),
        44: ("pattern_cache",),
        58: ("supercruise",),
    }

    def __init__(self):
        self.running = True
        self.context = None
        self.console = None
        self.game_thread = None
        self.io_lock = threading.RLock()
        self.input_queue = queue.Queue()
        self.active_prompt = ""
        self.current_input = ""
        self.stdout_buffer = ""
        self.log_lines = []
        self.max_log_lines = 1400
        self.session_log_records = []
        self.max_session_log_records = 6000
        self.suspend_session_archive = 0
        self.command_history = []
        self.max_command_history = 240

        self.state = None
        self.player = None
        self.arsenal = None
        self.current_enemy = None
        self.active_tap_node_index = None
        self.item_library = {}

        initial_objective = boot_layout_card()
        self.objective_title = initial_objective.title
        self.objective_body = initial_objective.body
        self.objective_tone = initial_objective.tone
        self.objective_command = initial_objective.command
        self.objective_detail = initial_objective.detail
        self.objective_is_tutorial = initial_objective.tutorial
        self.tileset_name = "fallback"

        self.map_world = None
        self.map_cleared = set()
        self.map_active = None
        self.map_status = "Awaiting active subnet."
        self.databank_lines = ["TOOLS", " booting...", "", "FLAGS", " offline"]
        self.shop_databank_entries = {}
        self.route_sweep_level = 0
        self.route_sweep_max = 0
        self.combat_engine = None
        self.dev_console_requested = False
        self.return_to_menu_requested = False
        self.selected_save_reference = None
        self.active_save_reference = None

    @staticmethod
    def databank_role_label(kind: str, entry_id: str, data: dict) -> str:
        if kind == "script":
            return str(data.get("type", "tool")).replace("_", "-")

        if kind == "flag":
            return {
                "--ransom": "crypto",
                "--stealth": "mask",
                "--ghost": "opsec",
                "--worm": "chain",
                "--burst": "power",
                "--volatile": "power",
                "--fork": "split",
            }.get(entry_id, "mod")

        if kind == "item":
            return "single-use"

        return "misc"

    def load_ui_tileset(self):
        font_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        font_candidates = [
            font_dir / "lucon.ttf",
            font_dir / "consola.ttf",
        ]
        for candidate in font_candidates:
            if not candidate.exists():
                continue
            try:
                self.tileset_name = candidate.stem.upper()
                return tcod.tileset.load_truetype_font(candidate, self.TILE_WIDTH, self.TILE_HEIGHT)
            except Exception:
                continue

        self.tileset_name = "fallback"
        return None

    def run(self):
        old_stdout = sys.stdout
        sys.stdout = self
        try:
            try:
                lib.SDL_SetLogPriorities(lib.SDL_LOG_PRIORITY_CRITICAL)
            except Exception:
                pass
            tileset = self.load_ui_tileset()
            with tcod.context.new(
                columns=self.WIDTH,
                rows=self.HEIGHT,
                title="Terminal Rogue // tcod",
                vsync=True,
                tileset=tileset,
                argv=[],
                sdl_window_flags=tcod.context.SDL_WINDOW_RESIZABLE,
            ) as context:
                self.context = context
                self.console = tcod.console.Console(self.WIDTH, self.HEIGHT, order="F")
                self.game_thread = threading.Thread(target=self.run_game, daemon=True)
                self.game_thread.start()

                while self.running:
                    self.render()
                    self.context.present(
                        self.console,
                        keep_aspect=True,
                        integer_scaling=True,
                        clear_color=self.COLORS["bg"],
                    )

                    for event in tcod.event.get():
                        self.handle_event(event)

                    if self.game_thread and not self.game_thread.is_alive() and not self.active_prompt:
                        self.running = False

                    time.sleep(0.016)
        finally:
            sys.stdout = old_stdout

    def handle_event(self, event):
        if isinstance(event, tcod.event.Quit):
            self.running = False
            return

        if not isinstance(event, tcod.event.KeyDown):
            return

        if event.sym == tcod.event.KeySym.BACKSPACE:
            self.current_input = self.current_input[:-1]
            return

        if event.sym == tcod.event.KeySym.ESCAPE:
            self.current_input = ""
            return

        if event.sym in (tcod.event.KeySym.RETURN, tcod.event.KeySym.KP_ENTER):
            self.submit_current_input()
            return

        if not self.active_prompt:
            return

        typed = self.keydown_to_text(event)
        if typed:
            self.current_input += typed

    def keydown_to_text(self, event):
        if event.mod & (tcod.event.Modifier.CTRL | tcod.event.Modifier.ALT | tcod.event.Modifier.GUI):
            return ""

        sym = int(event.sym)
        if sym < 32 or sym > 126:
            return ""

        char = chr(sym)
        shift = bool(event.mod & tcod.event.Modifier.SHIFT)
        caps = bool(event.mod & tcod.event.Modifier.CAPS)

        if char.isalpha():
            return char.upper() if shift ^ caps else char.lower()

        if shift:
            return SHIFTED_SYMBOLS.get(char, char)

        return char

    def submit_current_input(self):
        command = self.current_input
        prompt = self.active_prompt
        self.current_input = ""

        if command.strip():
            self.command_history.append(command)
            if len(self.command_history) > self.max_command_history:
                self.command_history = self.command_history[-self.max_command_history :]

        if prompt or command:
            echo_line = f"{prompt}{command}".rstrip()
            self.write((echo_line if echo_line else "") + "\n")
        else:
            self.write("\n")

        if command and self.handle_local_command(command):
            return

        self.active_prompt = ""
        self.input_queue.put(command)

    def handle_local_command(self, cmd: str) -> bool:
        lowered = cmd.lower().strip()
        shell_command = self.try_handle_shell_command(cmd)
        if shell_command is not None:
            return shell_command

        if lowered == "help":
            self.write(self.build_dynamic_help_text())
            return True

        if lowered == "dev":
            self.request_dev_console()
            self.write("[sys] Developer console requested.\n")
            return True

        if lowered.startswith("man "):
            target = lowered[4:].strip()
            if not self.arsenal:
                self.write("[sys] Error: Arsenal databank offline. Boot sequence incomplete.\n")
                return True

            target = self.arsenal.resolve_script_name(target)

            if target in {"exploit", "exploits", "combo", "combos"}:
                self.write(self.build_exploit_manual_text())
                return True

            if target in {"item", "items", "consumable", "consumables"}:
                self.write(self.build_item_manual_text())
                return True

            topic_manual = self.build_topic_manual_text(target)
            if topic_manual:
                self.write(topic_manual)
                return True

            shell_manual = self.build_shell_command_manual_text(target)
            if shell_manual:
                self.write(shell_manual)
                return True

            subsystem_entry = self.get_manual_entry(target)
            if subsystem_entry:
                self.write(f"\n=== MAN PAGE: {target.upper()} ===\n> {subsystem_entry}\n\n")
                return True

            payload_manual = self.build_payload_manual_text(target)
            if payload_manual:
                self.write(payload_manual)
                return True

            self.write(f"[sys] man: No manual entry for payload '{target}'.\n")
            return True

        return False

    def try_handle_shell_command(self, cmd: str):
        stripped = cmd.strip()
        if not stripped:
            return None

        try:
            tokens = shlex.split(stripped)
        except ValueError as exc:
            self.write(f"[sys] shell parse error: {exc}\n")
            return True

        if not tokens:
            return None

        name = tokens[0].lower()
        args = tokens[1:]

        if name in {"cls", "reset-terminal"}:
            self.clear_terminal_history()
            if self.current_enemy and self.combat_engine:
                self.combat_engine.render_planning_snapshot()
            return True

        if name == "clear":
            if self.current_enemy:
                return None
            self.clear_terminal_history()
            return True

        if name == "pwd":
            self.write(self.get_shell_cwd() + "\n")
            return True

        if name == "ls":
            target = args[0] if args else self.get_shell_cwd()
            normalized = self.normalize_virtual_path(target)
            listing = self.list_virtual_path(normalized)
            if listing is None:
                self.write(f"ls: cannot access '{target}': No such file or directory\n")
            else:
                self.write(listing + "\n")
            return True

        if name == "cat":
            if not args:
                self.write("cat: missing operand\n")
                return True
            normalized = self.normalize_virtual_path(args[0])
            contents = self.read_virtual_path(normalized)
            if contents is None:
                self.write(f"cat: {args[0]}: No such file or directory\n")
            else:
                if normalized.startswith("~/var/log/"):
                    self.suspend_session_archive += 1
                    try:
                        self.write(contents.rstrip("\n") + "\n")
                    finally:
                        self.suspend_session_archive = max(0, self.suspend_session_archive - 1)
                else:
                    self.write(contents.rstrip("\n") + "\n")
            return True

        if name == "history":
            if not self.command_history:
                self.write("history: session command list is empty\n")
                return True
            width = len(str(len(self.command_history)))
            lines = [f"{index:>{width}}  {value}" for index, value in enumerate(self.command_history, start=1)]
            self.write("\n".join(lines) + "\n")
            return True

        if name == "contracts":
            self.write(self.build_shell_contracts_text().rstrip("\n") + "\n")
            return True

        if name in {"domains", "estate"}:
            self.write(self.build_shell_domains_text().rstrip("\n") + "\n")
            return True

        if name == "whoami":
            self.write("root\n")
            return True

        if name == "hostname":
            self.write(self.get_shell_hostname() + "\n")
            return True

        if name == "uname":
            if args and args[0] == "-a":
                self.write(self.build_uname_text(full=True) + "\n")
            else:
                self.write(self.build_uname_text(full=False) + "\n")
            return True

        if name == "date":
            self.write(datetime.now().astimezone().strftime("%a %b %d %H:%M:%S %Z %Y") + "\n")
            return True

        return None

    def clear_terminal_history(self):
        self.stdout_buffer = ""
        self.log_lines = []

    @staticmethod
    def should_archive_line(plain: str) -> bool:
        stripped = plain.strip()
        if not stripped:
            return False
        if all(ch in "-=+#*._ " for ch in stripped):
            return False
        return True

    def classify_session_log_tag(self, plain: str, tone: str) -> str:
        lowered = plain.strip().lower()
        if lowered.startswith("root@") or lowered.startswith("recon@"):
            return "CMD"
        if "[queue commit]" in lowered or "[queue resolved]" in lowered or "[impact report]" in lowered:
            return "OPS"
        if "[counter-attack]" in lowered or "[hostile activity]" in lowered:
            return "OPS"
        if lowered.startswith("[sys]") or "bootstrapping" in lowered or "decrypting distributed botnet payloads" in lowered:
            return "SYS"
        if "tutorial" in lowered or "archive//echo" in lowered or "field note" in lowered or "survival primer" in lowered:
            return "NOTE"
        if "bot" in lowered or "support" in lowered:
            return "BOT"
        if tone == "green" or lowered.startswith("[+]") or "success" in lowered or "access granted" in lowered:
            return "OK"
        if tone == "red" or "error" in lowered or "[!]" in lowered or "failed" in lowered or "critical" in lowered:
            return "ERR"
        if tone == "yellow" or "trace" in lowered or "warning" in lowered or "counter-intel" in lowered:
            return "WARN"
        if tone == "magenta":
            return "NOTE"
        if tone == "cyan":
            return "SYS"
        return "INFO"

    def archive_session_line(self, plain: str, tone: str):
        if self.suspend_session_archive > 0:
            return
        if not self.should_archive_line(plain):
            return
        tag = self.classify_session_log_tag(plain, tone)
        self.session_log_records.append(
            {
                "time": datetime.now().astimezone().strftime("%H:%M:%S"),
                "tag": tag,
                "tone": tone,
                "text": plain.strip(),
            }
        )
        if len(self.session_log_records) > self.max_session_log_records:
            self.session_log_records = self.session_log_records[-self.max_session_log_records :]

    def get_shell_cwd(self):
        return "~"

    def get_shell_hostname(self):
        identity = self.get_terminal_identity()
        if "@" in identity:
            return identity.split("@", 1)[1]
        return "terminal-rogue"

    def get_shell_prompt(self):
        return f"{self.get_terminal_identity()}:{self.get_shell_cwd()}$ "

    def get_recon_prompt(self):
        return "recon@link:~$ "

    def build_uname_text(self, *, full: bool):
        system_name = "TerminalRogueOS"
        kernel = "6.8.rogue"
        machine = "x86_64"
        if not full:
            return system_name
        host = self.get_shell_hostname()
        platform_name = platform.system() or "Windows"
        return f"{system_name} {host} {kernel} #1 {platform_name} {machine}"

    def normalize_virtual_path(self, raw_path: str | None):
        raw = (raw_path or "").strip()
        if not raw or raw in {".", "~", "~/", "/"}:
            return "~"

        alias_map = {
            "player": "~/proc/player",
            "target": "~/proc/target",
            "objective": "~/proc/objective",
            "architecture": "~/proc/architecture",
            "route": "~/net/routeweb",
            "routeweb": "~/net/routeweb",
            "databank": "~/usr/share/databank",
            "manuals": "~/usr/share/manuals",
            "session.log": "~/var/log/session.log",
            "history.log": "~/var/log/history.log",
        }
        lowered = raw.lower()
        if lowered in alias_map:
            return alias_map[lowered]

        if raw.startswith("~/"):
            return raw.rstrip("/")
        if raw.startswith("/"):
            return ("~" + raw).rstrip("/")
        if raw.startswith("proc/") or raw.startswith("net/") or raw.startswith("usr/") or raw.startswith("var/"):
            return ("~/" + raw).rstrip("/")
        if raw in {"proc", "net", "usr", "var"}:
            return f"~/{raw}"
        return raw.rstrip("/")

    def get_virtual_tree(self):
        return {
            "~": ["proc/", "net/", "usr/", "var/"],
            "~/proc": ["player", "target", "objective", "architecture", "contracts", "domains"],
            "~/net": ["routeweb"],
            "~/usr": ["share/"],
            "~/usr/share": ["databank", "manuals"],
            "~/var": ["log/"],
            "~/var/log": ["session.log", "history.log"],
        }

    def list_virtual_path(self, path: str):
        tree = self.get_virtual_tree()
        if path in tree:
            return "  ".join(tree[path])
        if self.read_virtual_path(path) is not None:
            return path.split("/")[-1]
        return None

    def read_virtual_path(self, path: str):
        readers = {
            "~/proc/player": self.build_shell_player_text,
            "~/proc/target": self.build_shell_target_text,
            "~/proc/objective": self.build_shell_objective_text,
            "~/proc/architecture": self.build_shell_architecture_text,
            "~/proc/contracts": self.build_shell_contracts_text,
            "~/proc/domains": self.build_shell_domains_text,
            "~/net/routeweb": self.build_shell_route_text,
            "~/usr/share/databank": self.build_shell_databank_text,
            "~/usr/share/manuals": self.build_shell_manual_index_text,
            "~/var/log/session.log": self.build_shell_session_log_text,
            "~/var/log/history.log": self.build_shell_history_text,
        }
        reader = readers.get(path)
        if not reader:
            return None
        return reader()

    def build_shell_player_text(self):
        if not self.player or not self.state:
            return "bootstrapping session state..."

        player = self.player
        ram_max = player.get_effective_max_ram()
        projection = None
        if self.combat_engine:
            snapshot = getattr(self.combat_engine, "planning_snapshot", None)
            if snapshot:
                projection = snapshot.get("projection")
        defense_text = player.get_defense_summary().replace("DEFENSE     ", "")
        cache_text = player.get_hardening_summary() if player.adaptive_hardening_active else ""
        bot_text = player.get_support_bot_summary().replace("BOT BAY     ", "")
        item_text = player.get_consumable_summary()
        sto = player.subsystems["STO"]
        lines = [
            f"RIG         {player.handle} // {player.title}",
            f"RAM         {player.current_ram}/{ram_max}   REGEN {player.get_ram_regen()}/turn   SIG {player.signature_subsystem}",
            f"IP          {player.local_ip}",
            (
                f"OS {player.subsystems['OS'].current_hp:>2}/{player.subsystems['OS'].max_hp:<2}   "
                f"SEC {player.subsystems['SEC'].current_hp:>2}/{player.subsystems['SEC'].max_hp:<2}"
            ),
            (
                f"NET {player.subsystems['NET'].current_hp:>2}/{player.subsystems['NET'].max_hp:<2}   "
                f"MEM {player.subsystems['MEM'].current_hp:>2}/{player.subsystems['MEM'].max_hp:<2}   "
                f"STO {sto.current_hp:>2}/{sto.max_hp:<2}"
            ),
            f"DEFENSE     {defense_text}",
            f"CACHE       {cache_text or ('PRIMING' if player.adaptive_hardening_active else 'OFFLINE')}",
            f"BOTS        {bot_text}",
            f"ITEMS       {item_text}",
        ]
        if projection and projection.projected_player and projection.steps:
            ghost_player = projection.projected_player
            ram_delta = ghost_player.current_ram - player.current_ram
            lines.append(
                f"STACK DELTA {ram_delta:+d} RAM  {'LEGAL' if projection.legal else 'FAULT'}"
            )
            detail_bits = []
            if projection.root_prediction:
                detail_bits.append(f"OUTCOME {projection.root_prediction.upper()}")
            if detail_bits:
                lines.append("DETAIL      " + " | ".join(detail_bits))
        return "\n".join(lines)

    def build_shell_target_text(self):
        enemy = self.current_enemy
        if not enemy:
            return "No live hostile link.\n\nScan a node or breach a host to populate this file."

        owner, role, allocation = enemy.owner_profile
        intel_text = enemy.description if enemy.identity_revealed else "identity unresolved. host profile still masked."
        if enemy.weakness_revealed:
            weakness_text = enemy.weakness
        elif enemy.security_breach_turns > 0 or enemy.subsystems["SEC"].is_destroyed:
            weakness_text = "fingerprint pending"
        else:
            weakness_text = "masked by perimeter controls"

        lines = [
            f"HOST        {enemy.get_visible_name()}",
            f"COUNTER     {enemy.get_visible_weapon()}",
            f"OPERATING   {enemy.subsystems['OS'].name}",
            f"LINK        {enemy.get_recon_alert_text()}",
            f"EXPOSURE    {enemy.recon_exposure}",
            f"PORTS       {enemy.get_service_summary() if enemy.topology_revealed else 'unresolved'}",
            f"VULN        {weakness_text}",
            f"INTENT      {enemy.current_intent.get('name', 'Idle') if enemy.intent_revealed else 'unresolved'}",
        ]
        if enemy.identity_revealed:
            lines.append(f"OWNER       {owner}")
            lines.append(f"ROLE        {role}")
            lines.append(f"NETRANGE    {allocation}")
        else:
            lines.append("OWNER       unresolved")
            lines.append("ROLE        unresolved")
            lines.append("NETRANGE    unresolved")

        adaptation = enemy.get_adaptation_summary()
        if adaptation:
            lines.append(f"ADAPT       {adaptation}")

        lines.append("")
        lines.append("INTEL")
        lines.append(f" {intel_text}")
        lines.append("")
        lines.append("SUBSYSTEMS")
        for key in ("OS", "SEC", "NET", "MEM", "STO"):
            lines.append(self.build_shell_enemy_detail_row(enemy, key))
        lines.append("")
        lines.append("BUSES")
        lines.extend(enemy.get_bus_report_lines())
        return "\n".join(lines)

    @staticmethod
    def build_shell_enemy_row(enemy, left: str, right: str | None = None):
        def chunk(key: str):
            subsystem = enemy.subsystems[key]
            if enemy.has_telemetry_for(key):
                label = f"{subsystem.current_hp:>2}/{subsystem.max_hp:<2}"
            elif enemy.topology_revealed:
                label = "layout"
            else:
                label = "??"
            return f"{key:<3} {label}"

        row = chunk(left)
        if right:
            row += f"   {chunk(right)}"
        return row

    @staticmethod
    def build_shell_enemy_detail_row(enemy, key: str):
        subsystem = enemy.subsystems[key]
        if enemy.has_telemetry_for(key):
            label = f"{subsystem.current_hp:>2}/{subsystem.max_hp:<2}"
        elif enemy.topology_revealed:
            label = "layout"
        else:
            label = "??"
        pressure = enemy.classify_pressure(subsystem)
        return f" {key:<3} {subsystem.name:<10} {label:<7} {pressure}"

    def build_shell_objective_text(self):
        lines = [self.objective_title, "", self.objective_body.strip()]
        if self.objective_command:
            lines.extend(["", f"TRY: {self.objective_command}"])
        if self.objective_detail:
            lines.append(f"WHY: {self.objective_detail}")
        active_contract_lines = self.state.get_active_contract_summary_lines() if self.state else []
        if active_contract_lines:
            lines.extend(["", *active_contract_lines])
        return "\n".join(lines)

    def build_shell_contracts_text(self):
        if not self.state:
            return "ACTIVE CONTRACTS\n\nno live session state"
        tracked = self.state.get_accepted_contracts()
        inbox = list(self.state.current_contracts)
        lines = ["ACTIVE CONTRACTS"]
        if tracked:
            for contract in tracked[:8]:
                lines.append(
                    f"- tracking {contract['target_ip']} // {contract['type']} // {contract['reward']}c"
                )
            if len(tracked) > 8:
                lines.append(f"- +{len(tracked) - 8} more tracked")
        else:
            lines.append("- none")
        if inbox:
            lines.extend(["", "MAIL INBOX"])
            for contract in inbox[:6]:
                lines.append(
                    f"- available {contract['target_ip']} // {contract['type']} // {contract['reward']}c"
                )
            if len(inbox) > 6:
                lines.append(f"- +{len(inbox) - 6} more waiting")
        return "\n".join(lines)

    def build_shell_domains_text(self):
        if not self.state:
            return "ROOTED DOMAINS\n\n- none"
        inventory = []
        for module_id, count in sorted(self.state.module_inventory.items()):
            inventory.append(f"{module_id} x{count}")
        lines = self.state.get_rooted_domain_summary_lines(limit=10)
        if inventory:
            lines.extend(["", "MODULE INVENTORY", *[f"- {entry}" for entry in inventory]])
        botnet_power = self.state.get_domain_botnet_power()
        if botnet_power:
            lines.extend(["", f"BOTNET POWER {botnet_power}"])
        return "\n".join(lines)

    def build_shell_architecture_text(self):
        if not self.current_enemy:
            return "Passive shell idle.\n\nNo hostile architecture is loaded."

        enemy = self.current_enemy

        def label(key: str):
            subsystem = enemy.subsystems[key]
            if enemy.has_telemetry_for(key):
                return f"{key} {subsystem.current_hp:>2}/{subsystem.max_hp:<2}"
            if enemy.topology_revealed:
                return f"{key} layout"
            return f"{key} ??"

        lines = [
            "HOST ARCHITECTURE",
            "",
            "             [ " + label("SEC") + " ]",
            "                  |",
            "[ " + label("NET") + " ]--[ " + label("OS") + " ]--[ " + label("MEM") + " ]",
            "                  |",
            "             [ " + label("STO") + " ]",
            "",
        ]
        if enemy.topology_revealed:
            lines.append("bus fabric:")
            lines.extend(enemy.get_bus_report_lines())
            lines.append("")
            lines.append("open services:")
            for entry in enemy.get_surface_report_lines():
                lines.append(entry.strip())
        else:
            lines.append("blind tap. no topology yet.")
        return "\n".join(lines)

    def build_shell_route_text(self):
        if self.current_enemy:
            return self.build_shell_architecture_text()
        if not self.map_world:
            return "awaiting route mesh..."

        world = self.map_world
        focus_index = self.map_active
        if focus_index is None:
            focus_index = min(world.entry_links) if world.entry_links else 0
        focus_node = world.nodes[focus_index]
        lines = [
            world.subnet_name,
            self.map_status or "mesh idle",
        ]

        if self.map_network and self.map_subnet_id:
            subnet = self.map_network.get_subnet(self.map_subnet_id)
            if subnet:
                domain = self.map_network.get_domain(subnet.domain_id)
                lines.extend(
                    [
                        "",
                        "[macro]",
                        f" domain {domain.name if domain else subnet.domain_id}",
                        f" subnet {subnet.subnet_id} // {'conquered' if subnet.is_conquered() else 'active'}",
                    ]
                )
                if self.has_standard_travel_unlock():
                    neighbors = self.map_network.neighboring_subnet_ids(subnet.subnet_id)
                    if neighbors:
                        lines.extend(["", "[adjacent]"])
                        for subnet_id in sorted(neighbors):
                            linked_subnet = self.map_network.get_subnet(subnet_id)
                            if not linked_subnet:
                                continue
                            state = "open" if subnet.is_conquered() else "sealed"
                            if linked_subnet.is_conquered():
                                state = "conquered"
                            lines.append(f" {subnet_id:<4} {linked_subnet.subnet_name:<18} {state}")

        lines.extend(
            [
                "",
                "[focus]",
                f" {self.describe_shell_route_node(world, focus_index, focus_node)}",
                f" depth {world.node_depths.get(focus_index, 1)}",
            ]
        )

        active_intel = self.build_node_intel_summary(focus_node)
        if active_intel:
            lines.append(f"  {active_intel}")

        lines.extend(["", "[ingress]"])
        if focus_index in world.entry_links:
            lines.append(" <- shell uplink // public route hop")
        inbound = world.get_inbound_hops(focus_index)
        if not inbound and focus_index not in world.entry_links:
            lines.append(" none")
        else:
            for node_index in inbound:
                lines.append(f" <- {self.describe_shell_route_node(world, node_index, world.nodes[node_index])}")

        lines.extend(["", "[egress]"])
        outbound = world.get_outbound_hops(focus_index)
        if not outbound:
            lines.append(" none")
        else:
            for node_index in outbound:
                node = world.nodes[node_index]
                lines.append(f" -> {self.describe_shell_route_node(world, node_index, node)}")
                intel = self.describe_shell_route_secondary(world, focus_index, node_index, node)
                if intel:
                    lines.append(f"    {intel}")
                fanout = world.get_outbound_hops(node_index)
                if fanout:
                    preview = ", ".join(self.describe_shell_route_short_label(world, idx) for idx in fanout[:3])
                    lines.append(f"    fanout: {preview}")

        return "\n".join(lines)

    def describe_shell_route_node(self, world, node_index, node):
        status = self.get_node_status_text(node_index, node, self.map_cleared)
        label = self.describe_shell_route_label(world, node_index, node)
        depth = world.node_depths.get(node_index, 1)
        if label == node.ip_address:
            return f"{label} [{status}] d{depth}"
        return f"{label} @ {node.ip_address} [{status}] d{depth}"

    def describe_shell_route_secondary(self, world, focus_index, node_index, node):
        status = self.get_node_status_text(node_index, node, self.map_cleared)
        if status == "LOCKED":
            return "route sealed"
        return self.build_node_intel_summary(node)

    def describe_shell_route_label(self, world, node_index, node):
        if node.node_type == "shop":
            return "market relay"
        enemy = getattr(node, "cached_enemy", None)
        if enemy and enemy.identity_revealed:
            return enemy.get_visible_name().split("[")[0].strip()
        if node_index in self.map_cleared and enemy and enemy.topology_revealed:
            scanned = self.get_node_scan_label(enemy).strip()
            if scanned and scanned not in {"HOSTILE", "SCANNED"}:
                return scanned.title()
        return node.ip_address

    def describe_shell_route_short_label(self, world, node_index):
        label = self.describe_shell_route_label(world, node_index, world.nodes[node_index])
        if label == world.nodes[node_index].ip_address:
            return label.split(".")[-1]
        return label[:14]

    def build_shell_databank_text(self):
        return "\n".join(self.databank_lines)

    def get_installed_script_ids(self):
        if not self.arsenal:
            return []
        if not self.player:
            return list(self.arsenal.scripts.keys())
        return [script_id for script_id in self.arsenal.scripts if self.player.owns_script(script_id)]

    def get_installed_flag_ids(self):
        if not self.arsenal:
            return []
        if not self.player:
            return list(self.arsenal.flags.keys())
        return [flag_id for flag_id in self.arsenal.flags if self.player.owns_flag(flag_id)]

    def get_visible_item_ids(self):
        if not self.item_library:
            return []
        if not self.player:
            return sorted(self.item_library.keys())
        return [
            item_id
            for item_id in sorted(self.item_library)
            if self.player.get_consumable_count(item_id) > 0
        ]

    @staticmethod
    def _split_completion_input(text: str):
        raw = text or ""
        parts = raw.split()
        if raw.endswith(" "):
            parts.append("")
        return parts

    @staticmethod
    def _filter_completion_matches(candidates, prefix: str):
        seen = set()
        matches = []
        lowered_prefix = (prefix or "").lower()
        for candidate in candidates:
            if not candidate:
                continue
            if candidate in seen:
                continue
            if lowered_prefix and not str(candidate).lower().startswith(lowered_prefix):
                continue
            seen.add(candidate)
            matches.append(candidate)
        exact = lowered_prefix
        return sorted(matches, key=lambda value: (str(value).lower() != exact, str(value).lower()))

    def get_completion_subsystem_tokens(self):
        if self.player and getattr(self.player, "subsystems", None):
            return list(self.player.subsystems.keys())
        return ["OS", "SEC", "NET", "MEM", "STO"]

    def get_visible_manual_target_ids(self):
        visible = []
        seen = set()

        def add(token: str):
            if not token:
                return
            if token in seen:
                return
            seen.add(token)
            visible.append(token)

        for line in self.get_visible_manual_topics():
            stripped = line.strip()
            if stripped.startswith("man "):
                add(stripped[4:].strip())

        add("exploit")
        add("items")
        for subsystem in self.get_completion_subsystem_tokens():
            add(subsystem.lower())
        for script_id in self.get_installed_script_ids():
            add(script_id)
        for flag_id in self.get_installed_flag_ids():
            add(flag_id)
        for item_id in self.get_visible_item_ids():
            add(item_id)
        return visible

    def get_virtual_path_candidates(self):
        tree = self.get_virtual_tree()
        alias_tokens = [
            "player",
            "target",
            "objective",
            "architecture",
            "route",
            "routeweb",
            "databank",
            "manuals",
            "session.log",
            "history.log",
        ]
        candidates = set(alias_tokens)
        for path, entries in tree.items():
            candidates.add(path)
            for entry in entries:
                entry_name = entry.rstrip("/")
                candidates.add(entry_name)
                if path == "~":
                    candidates.add(f"~/{entry_name}")
                else:
                    candidates.add(f"{path}/{entry_name}".replace("//", "/"))
        for path in (
            "~/proc/player",
            "~/proc/target",
            "~/proc/objective",
            "~/proc/architecture",
            "~/proc/contracts",
            "~/proc/domains",
            "~/net/routeweb",
            "~/usr/share/databank",
            "~/usr/share/manuals",
            "~/var/log/session.log",
            "~/var/log/history.log",
        ):
            candidates.add(path)
        return sorted(candidates)

    def get_route_completion_node_ids(self):
        if not self.state or not getattr(self.state, "active_network", None):
            return []
        network = self.state.active_network
        current_subnet = network.get_subnet(self.state.current_subnet_id or network.entry_subnet_id)
        if not current_subnet:
            return []
        world = current_subnet.world_map
        cleared_nodes = current_subnet.cleared_nodes
        current_anchor = current_subnet.current_anchor
        matches = []
        for index, node in enumerate(world.nodes):
            if index in cleared_nodes:
                can_revisit = world.can_traverse_from(current_anchor, index, cleared_nodes)
                can_fast_travel = self.state.can_fast_travel_to(node)
                if can_revisit or can_fast_travel:
                    matches.append(node.ip_address.lower())
            elif world.can_traverse_from(current_anchor, index, cleared_nodes):
                matches.append(node.ip_address.lower())
        return self._filter_completion_matches(matches, "")

    def get_active_tap_context(self, current_subnet, enemies_data=None, modifiers=None, ability_library=None):
        tap_index = self.active_tap_node_index
        if tap_index is None or not current_subnet:
            return None, None, None
        world = current_subnet.world_map
        if tap_index < 0 or tap_index >= len(world.nodes):
            self.active_tap_node_index = None
            self.current_enemy = None
            return None, None, None
        if tap_index != current_subnet.current_anchor:
            self.active_tap_node_index = None
            self.current_enemy = None
            return None, None, None
        if tap_index in current_subnet.cleared_nodes:
            self.active_tap_node_index = None
            self.current_enemy = None
            return None, None, None

        node = world.nodes[tap_index]
        if getattr(node, "compromise_state", "") in {"rooted", "bricked"} or node.node_type == "shop":
            self.active_tap_node_index = None
            self.current_enemy = None
            return None, None, None

        enemy = self.current_enemy
        if enemies_data is not None and ability_library is not None:
            enemy = self.build_enemy_for_node(node, enemies_data, modifiers or {}, ability_library)
            self.current_enemy = enemy
        return tap_index, node, enemy

    def get_standard_travel_completion_tokens(self):
        if not self.state or not getattr(self.state, "active_network", None):
            return []
        network = self.state.active_network
        current_subnet = network.get_subnet(self.state.current_subnet_id or network.entry_subnet_id)
        if not current_subnet:
            return []
        candidates = []
        for subnet_id in sorted(current_subnet.neighbors):
            subnet = network.get_subnet(subnet_id)
            if not subnet:
                continue
            candidates.append(subnet.subnet_id.lower())
            candidates.append(subnet.subnet_name.lower().replace(" ", "_"))
        return self._filter_completion_matches(candidates, "")

    def get_supercruise_completion_tokens(self):
        if not self.state or not getattr(self.state, "active_network", None):
            return []
        network = self.state.active_network
        current_subnet_id = self.state.current_subnet_id or network.entry_subnet_id
        candidates = []
        for subnet_id, subnet in sorted(network.subnets.items()):
            if subnet_id == current_subnet_id:
                continue
            candidates.append(subnet.subnet_id.lower())
            candidates.append(subnet.subnet_name.lower().replace(" ", "_"))
        for domain_id, domain in sorted(network.domains.items()):
            candidates.append(domain_id.lower())
            candidates.append(domain.name.lower().replace(" ", "_"))
        candidates.extend(["current", "active", "here"])
        return self._filter_completion_matches(candidates, "")

    def get_shell_command_completion_matches(self, text: str):
        shell_roots = [
            "help",
            "dev",
            "man",
            "pwd",
            "ls",
            "cat",
            "history",
            "contracts",
            "domains",
            "whoami",
            "hostname",
            "uname",
            "date",
            "clear",
            "cls",
            "reset-terminal",
        ]
        parts = self._split_completion_input(text)
        token = parts[-1] if parts else ""
        if len(parts) <= 1:
            return self._filter_completion_matches(shell_roots, token)

        name = parts[0].lower()
        if name == "man":
            return self._filter_completion_matches(self.get_visible_manual_target_ids(), token)
        if name in {"ls", "cat"}:
            return self._filter_completion_matches(self.get_virtual_path_candidates(), token)
        if name == "uname":
            return self._filter_completion_matches(["-a"], token)
        return []

    def get_payload_completion_matches(self, text: str, *, include_use: bool = True):
        parts = self._split_completion_input(text)
        token = parts[-1] if parts else ""
        installed_scripts = self.get_installed_script_ids()
        visible_items = self.get_visible_item_ids()

        if len(parts) <= 1:
            roots = list(installed_scripts)
            if include_use and visible_items:
                roots.append("use")
            return self._filter_completion_matches(roots, token)

        name = parts[0].lower()
        if name == "use" and include_use:
            if len(parts) == 2:
                return self._filter_completion_matches(visible_items, token)
            item_id = parts[1]
            item_data = self.item_library.get(item_id, {}) if self.item_library else {}
            supports_target = bool(item_data.get("needs_target") or item_data.get("targetable") or item_data.get("default_target"))
            if not supports_target:
                return []
            if len(parts) >= 3 and parts[-2].lower() == "-target":
                return self._filter_completion_matches(self.get_completion_subsystem_tokens(), token.upper())
            candidates = []
            if "-target" not in [part.lower() for part in parts[2:]]:
                candidates.append("-target")
            return self._filter_completion_matches(candidates, token)

        if not self.arsenal or name not in self.arsenal.scripts:
            return []

        script_data = self.arsenal.scripts.get(name, {})
        supports_target = script_data.get("supports_target", True)
        used_flags = {part for part in parts[1:] if part.startswith("--")}
        has_target = any(part.lower() == "-target" for part in parts[1:])
        if len(parts) >= 3 and parts[-2].lower() == "-target":
            return self._filter_completion_matches(self.get_completion_subsystem_tokens(), token.upper())

        candidates = []
        if supports_target and not has_target:
            candidates.append("-target")
        candidates.extend(
            flag_id
            for flag_id in self.arsenal.get_owned_allowed_flags(name, owner=self.player)
            if flag_id not in used_flags
        )
        return self._filter_completion_matches(candidates, token)

    def get_terminal_completion_matches(self, text: str):
        prompt = (self.active_prompt or "").strip().lower()
        parts = self._split_completion_input(text)
        token = parts[-1] if parts else ""
        shell_roots = self.get_shell_command_completion_matches(text) if len(parts) <= 1 else []
        if len(parts) > 1 and parts[0].lower() in {
            "help",
            "dev",
            "man",
            "pwd",
            "ls",
            "cat",
            "history",
            "contracts",
            "domains",
            "whoami",
            "hostname",
            "uname",
            "date",
            "clear",
            "cls",
            "reset-terminal",
        }:
            return self.get_shell_command_completion_matches(text)

        context_candidates = []
        if "root@player:~$" in prompt:
            context_candidates = ["execute", "clear", "disconnect", "exit", "wait", "pass", "defend", "repair"]
            if self.state and self.state.has_meta("dry_run"):
                context_candidates.append("dry_run")
            if len(parts) <= 1:
                context_candidates.extend(self.get_payload_completion_matches(text, include_use=True))
            elif parts[0].lower() in {"defend", "repair"}:
                return self._filter_completion_matches(self.get_completion_subsystem_tokens(), token)
            else:
                payload_matches = self.get_payload_completion_matches(text, include_use=True)
                return payload_matches or self.get_shell_command_completion_matches(text)
        elif "recon@link:~$" in prompt:
            if len(parts) <= 1:
                context_candidates = ["engage", "soft engage", "disconnect", "exit"]
                context_candidates.extend(self.get_payload_completion_matches(text, include_use=False))
            elif len(parts) == 2 and parts[0].lower() == "soft":
                context_candidates = ["engage"]
            else:
                payload_matches = self.get_payload_completion_matches(text, include_use=False)
                return payload_matches or self.get_shell_command_completion_matches(text)
        elif "cleanup@node:~$" in prompt:
            context_candidates = ["status", "scrub", "forensics", "done", "exit", "leave"]
        elif self.active_tap_node_index is not None or "tap@" in prompt or "hop@" in prompt:
            if len(parts) <= 1:
                context_candidates = ["recon", "engage", "soft engage", "leave", "bot", "mail", "s"]
                if self.has_standard_travel_unlock():
                    context_candidates.extend(["subnets", "travel"])
                if self.has_supercruise_unlock():
                    context_candidates.append("supercruise")
                context_candidates.extend(self.get_route_completion_node_ids())
                context_candidates.extend(self.get_payload_completion_matches(text, include_use=False))
            elif len(parts) == 2 and parts[0].lower() == "soft":
                context_candidates = ["engage"]
            elif parts[0].lower() == "travel" and self.has_standard_travel_unlock():
                return self._filter_completion_matches(self.get_standard_travel_completion_tokens(), token)
            elif parts[0].lower() == "supercruise" and self.has_supercruise_unlock():
                return self._filter_completion_matches(self.get_supercruise_completion_tokens(), token)
            else:
                payload_matches = self.get_payload_completion_matches(text, include_use=False)
                if payload_matches:
                    return payload_matches
        elif "select node ip or route command:" in prompt:
            if len(parts) <= 1:
                context_candidates = ["bot", "mail", "s"]
                if self.has_standard_travel_unlock():
                    context_candidates.extend(["subnets", "travel"])
                if self.has_supercruise_unlock():
                    context_candidates.append("supercruise")
                context_candidates.extend(self.get_route_completion_node_ids())
            elif parts[0].lower() == "travel" and self.has_standard_travel_unlock():
                return self._filter_completion_matches(self.get_standard_travel_completion_tokens(), token)
            elif parts[0].lower() == "supercruise" and self.has_supercruise_unlock():
                return self._filter_completion_matches(self.get_supercruise_completion_tokens(), token)
        elif "open contract #:" in prompt:
            total = len(self.state.get_accepted_contracts()) + len(self.state.current_contracts) if self.state else 0
            context_candidates = [str(index) for index in range(1, total + 1)]
        elif "select a purchase:" in prompt:
            stock_size = len(self.shop_databank_entries)
            context_candidates = [str(index) for index in range(1, stock_size + 2)] if stock_size else []
        elif "install module #:" in prompt:
            module_count = len(self.state.module_inventory) if self.state and self.state.module_inventory else 0
            context_candidates = [str(index) for index in range(1, module_count + 1)]
            context_candidates.append("a")
        elif "select bot to configure:" in prompt:
            bot_count = len(self.player.support_bots) if self.player else 0
            context_candidates = [str(index) for index in range(1, bot_count + 1)]
        elif "target subsystem" in prompt:
            context_candidates = self.get_completion_subsystem_tokens()
        elif "run cadence in turns" in prompt:
            context_candidates = ["1", "2", "3", "4"]
        elif "select an option:" in prompt:
            context_candidates = ["1", "2", "3", "4"]

        return self._filter_completion_matches([*shell_roots, *context_candidates], token)

    def has_any_installed_script(self, script_ids):
        installed = set(self.get_installed_script_ids())
        return any(script_id in installed for script_id in script_ids)

    def has_seen_bricked_node(self):
        if self.map_world and any(getattr(node, "compromise_state", "") == "bricked" for node in self.map_world.nodes):
            return True
        if self.state and getattr(self.state, "active_network", None):
            for subnet in self.state.active_network.subnets.values():
                if any(getattr(node, "compromise_state", "") == "bricked" for node in subnet.world_map.nodes):
                    return True
        return False

    def is_manual_topic_visible(self, topic: str):
        topic = self.normalize_manual_topic(topic)
        always_visible = {"shell", "commands", "classes", "subsystems", "ram", "phases", "trace", "noise", "sweep", "buses", "os", "sec", "net", "mem", "sto"}
        if topic in always_visible:
            return True
        if topic == "flags":
            return bool(self.get_installed_flag_ids())
        if topic in {"scan", "recon"}:
            return self.has_any_installed_script({"nmap", "enum", "whois", "dirb"})
        if topic == "defense":
            return self.has_any_installed_script({"harden", "honeypot", "canary", "sinkhole", "rekey", "patch", "spoof"})
        if topic in {"brute-force", "brute"}:
            return any(self.arsenal.scripts[script_id].get("type") == "brute_force" for script_id in self.get_installed_script_ids())
        if topic == "exploit":
            return any(self.arsenal.scripts[script_id].get("type") == "exploit" for script_id in self.get_installed_script_ids())
        if topic == "utility":
            return any(self.arsenal.scripts[script_id].get("type") == "utility" for script_id in self.get_installed_script_ids())
        if topic == "root":
            return bool(self.state and self.state.rooted_domains)
        if topic == "brick":
            return self.has_seen_bricked_node()
        if topic == "dry_run":
            return bool(self.state and self.state.has_meta("dry_run"))
        if topic == "contracts":
            return bool(
                self.state
                and (self.state.current_contracts or self.state.active_contracts or self.state.contract_history)
            )
        if topic == "domains":
            return bool(
                self.state
                and (
                    self.state.rooted_domains
                    or self.state.module_inventory
                    or self.state.get_domain_botnet_power() > 0
                )
            )
        return False

    def get_visible_manual_topics(self):
        topic_labels = [
            ("shell", "man shell"),
            ("commands", "man commands"),
            ("classes", "man classes"),
            ("subsystems", "man subsystems"),
            ("ram", "man ram"),
            ("trace", "man trace"),
            ("noise", "man noise"),
            ("sweep", "man sweep"),
            ("buses", "man buses"),
            ("phases", "man phases"),
            ("flags", "man flags"),
            ("recon", "man recon"),
            ("scan", "man scan"),
            ("defense", "man defense"),
            ("brute-force", "man brute-force"),
            ("exploit", "man exploit"),
            ("utility", "man utility"),
            ("root", "man root"),
            ("brick", "man brick"),
            ("dry_run", "man dry_run"),
            ("contracts", "man contracts"),
            ("domains", "man domains"),
        ]
        return [label for topic, label in topic_labels if self.is_manual_topic_visible(topic)]

    def build_dynamic_help_text(self):
        installed_scripts = self.get_installed_script_ids()
        installed_flags = self.get_installed_flag_ids()
        visible_topics = self.get_visible_manual_topics()
        shell_helpers = ["pwd", "ls", "cat", "history", "whoami", "hostname", "uname", "date", "clear", "cls", "reset-terminal", "dev"]
        if self.state and self.state.has_meta("dry_run"):
            shell_helpers.append("dry_run")

        lines = [
            "\n\033[93m=== SYSTEM HELP ===\033[0m",
            "\033[96m[SHELL]\033[0m",
            " " + ", ".join(shell_helpers),
            " cat ~/proc/player   cat ~/proc/target   cat ~/usr/share/databank   cat ~/var/log/session.log",
            "",
            "\033[96m[STACK]\033[0m",
            " queue payloads in the terminal, then type execute",
            " clear empties the stack // wait or pass yields the turn // disconnect bails out of a live hostile link",
            " queued items resolve first as pre-flight injectors // the live stack then resolves FIFO",
            "",
            "\033[96m[RIG]\033[0m",
            f" installed scripts: {', '.join(installed_scripts) if installed_scripts else 'none'}",
            f" installed flags: {', '.join(installed_flags) if installed_flags else 'none'}",
            "",
            "\033[96m[MANUALS]\033[0m",
            " man <script|flag|item|target> for an entry on something you currently know",
        ]
        if visible_topics:
            lines.append(" " + "   ".join(visible_topics))
        lines.append("")
        return "\n".join(lines)

    def build_shell_manual_index_text(self):
        lines = ["manual topics", ""]
        lines.extend(self.get_visible_manual_topics() or [" man shell", " man commands"])
        lines.extend(
            [
                "",
                "shell commands",
                "",
                " man pwd",
                " man ls",
                " man cat",
                " man history",
                " man whoami",
                " man hostname",
                " man uname",
                " man date",
                " man clear",
                " man reset-terminal",
                " man dev",
            ]
        )
        return "\n".join(lines)

    def build_shell_session_log_text(self):
        if not self.session_log_records:
            return "SESSION LOG // empty archive\n\nNo visible terminal events have been recorded yet."

        lines = [
            "SESSION LOG // chronological archive",
            f"entries: {len(self.session_log_records)}",
            "format: HH:MM:SS [TAG ] event",
            "",
        ]
        for record in self.session_log_records[-220:]:
            lines.append(f"{record['time']} [{record['tag']:<4}] {record['text']}")
        return "\n".join(lines)

    def build_shell_history_text(self):
        if not self.command_history:
            return "[command history empty]"
        width = len(str(len(self.command_history)))
        return "\n".join(f"{index:>{width}}  {value}" for index, value in enumerate(self.command_history, start=1))

    def build_shell_command_manual_text(self, target: str):
        topic = target.strip().lower()
        manuals = {
            "shell": self.format_manual_page(
                "shell",
                [
                    (
                        "WHAT IT IS",
                        [
                            "The dev terminal is a real local shell layered on top of the game prompts.",
                            "It can inspect pseudo-files that mirror the live UI, so you can read state from the terminal without clicking windows.",
                        ],
                    ),
                    (
                        "IMPORTANT PATHS",
                        [
                            "~/proc/player = current rig snapshot.",
                            "~/proc/target = current hostile brief.",
                            "~/proc/objective = current objective card.",
                            "~/proc/architecture = hostile subsystem lattice when linked.",
                            "~/net/routeweb = route mesh when roaming.",
                            "~/usr/share/databank = installed tools, flags, items, and targets.",
                            "~/var/log/session.log = formatted chronological archive of terminal-visible events.",
                            "~/var/log/history.log = commands typed this session.",
                        ],
                    ),
                    (
                        "AVAILABLE SHELL COMMANDS",
                        [
                            "pwd, ls, cat, history, whoami, hostname, uname, date, clear, cls, reset-terminal.",
                            "Outside combat, clear wipes the visible terminal like a normal shell.",
                            "Inside combat, use cls or reset-terminal if you only want to clean the viewport without stealing the queue command clear.",
                        ],
                    ),
                ],
            ),
            "dev": self.format_manual_page(
                "dev",
                [
                    ("NAME", ["dev - open the live developer console in a separate desktop window."]),
                    (
                        "WHAT IT DOES",
                        [
                            "Launches a dedicated runtime shell for diagnostics, state edits, route manipulation, and toolkit testing.",
                            "The dev console edits the in-memory session immediately. It does not wait for a save unless you explicitly run save there.",
                        ],
                    ),
                    (
                        "COMMON TASKS",
                        [
                            "status = quick run snapshot.",
                            "dump player|target|route|state = inspect live runtime views.",
                            "set day|crypto|trace|ram|maxram <value> = edit core session values.",
                            "grant / revoke / give / take = mutate the live toolkit or inventory.",
                        ],
                    ),
                ],
            ),
            "pwd": self.format_manual_page(
                "pwd",
                [
                    ("NAME", ["pwd - print the current virtual working path for the dev terminal."]),
                    ("OUTPUT", [f"The shell currently lives at {self.get_shell_cwd()} during normal operation."]),
                    ("WHY USE IT", ["Useful when you are hopping between pseudo-file paths and want to confirm where the shell thinks home is."]),
                ],
            ),
            "ls": self.format_manual_page(
                "ls",
                [
                    ("NAME", ["ls - list the contents of a virtual directory or echo a virtual file name."]),
                    ("SYNOPSIS", ["ls", "ls ~/proc", "ls ~/usr/share", "ls ~/var/log"]),
                    (
                        "WHAT IT SHOWS",
                        [
                            "Directory names in the shell layer end with /. Files do not.",
                            "The listing is not your real Windows filesystem. It is a pseudo-filesystem for live game state.",
                        ],
                    ),
                ],
            ),
            "cat": self.format_manual_page(
                "cat",
                [
                    ("NAME", ["cat - print a virtual state file into the terminal."]),
                    (
                        "SYNOPSIS",
                        [
                            "cat ~/proc/player",
                            "cat ~/proc/target",
                            "cat ~/proc/objective",
                            "cat ~/net/routeweb",
                            "cat ~/usr/share/databank",
                            "cat ~/var/log/session.log",
                        ],
                    ),
                    (
                        "WHY USE IT",
                        [
                            "It lets you keep your hands in the terminal and still inspect the same information shown in the windows.",
                            "It is the fastest way to read the board if you want a shell-first playstyle.",
                        ],
                    ),
                ],
            ),
            "history": self.format_manual_page(
                "history",
                [
                    ("NAME", ["history - print previously entered commands from this running session."]),
                    ("NOTES", ["This includes shell helper commands, combat payloads, recon commands, and utility actions typed into the live prompt."]),
                ],
            ),
            "whoami": self.format_manual_page(
                "whoami",
                [("NAME", ["whoami - print the effective shell user."]), ("OUTPUT", ["This shell runs as root for style and clarity, so the output is root."])],
            ),
            "hostname": self.format_manual_page(
                "hostname",
                [
                    ("NAME", ["hostname - print the current rig identity used by the prompt."]),
                    ("OUTPUT", [f"On this rig the host portion is currently {self.get_shell_hostname()}."]),
                ],
            ),
            "uname": self.format_manual_page(
                "uname",
                [
                    ("NAME", ["uname - print the shell platform banner."]),
                    ("SYNOPSIS", ["uname", "uname -a"]),
                    ("NOTES", ["This is flavor text for the in-world shell surface. uname -a gives the fuller banner line."]),
                ],
            ),
            "date": self.format_manual_page(
                "date",
                [
                    ("NAME", ["date - print the current local time from the host machine."]),
                    ("WHY USE IT", ["Pure flavor, but it helps sell the machine as a living desktop rather than a static UI."]),
                ],
            ),
            "clear": self.format_manual_page(
                "clear",
                [
                    ("NAME", ["clear - wipe the visible terminal buffer outside active combat."]),
                    (
                        "IMPORTANT",
                        [
                            "In combat, the word clear is already used by the game queue to empty planned payloads.",
                            "If you only want to wipe the viewport at any time, use cls or reset-terminal instead.",
                        ],
                    ),
                ],
            ),
            "cls": self.format_manual_page(
                "cls",
                [("NAME", ["cls - emergency viewport wipe that always clears the visible terminal buffer."])],
            ),
            "reset-terminal": self.format_manual_page(
                "reset-terminal",
                [("NAME", ["reset-terminal - same effect as cls; fully wipes the visible terminal transcript."])],
            ),
            "wait": self.format_manual_page(
                "wait",
                [
                    ("NAME", ["wait - yield the turn without committing a stack."]),
                    (
                        "WHAT IT DOES",
                        [
                            "Ends your planning phase immediately.",
                            "Spends no RAM and commits no payloads.",
                            "Useful when you want the next turn's RAM recovery more than a weak stack right now.",
                        ],
                    ),
                ],
            ),
            "pass": self.format_manual_page(
                "pass",
                [
                    ("NAME", ["pass - alias for wait."]),
                    ("WHAT IT DOES", ["Exactly the same behavior as wait."]),
                ],
            ),
            "defend": self.format_manual_page(
                "defend",
                [
                    ("NAME", ["defend - brace one of your subsystems with a short ACL shell."]),
                    (
                        "SYNTAX",
                        [
                            "defend <OS|SEC|NET|MEM|STO>",
                            "If no target is given, it defaults to OS.",
                        ],
                    ),
                    (
                        "WHAT IT DOES",
                        [
                            "Ends the turn immediately.",
                            "Costs no RAM.",
                            "Adds a small temporary block to the chosen subsystem for the next hostile hit.",
                        ],
                    ),
                ],
            ),
            "repair": self.format_manual_page(
                "repair",
                [
                    ("NAME", ["repair - spend the turn restoring a little integrity to your own rig."]),
                    (
                        "SYNTAX",
                        [
                            "repair <OS|SEC|NET|MEM|STO>",
                            "If no target is given, it defaults to OS.",
                        ],
                    ),
                    (
                        "WHAT IT DOES",
                        [
                            "Ends the turn immediately.",
                            "Costs no RAM.",
                            "Restores a small amount of HP to the chosen subsystem if it is damaged.",
                            "Repair throughput improves gradually as your run progression climbs.",
                        ],
                    ),
                ],
            ),
        }
        return manuals.get(topic)

    def set_objective(
        self,
        title: str,
        body: str,
        tone: str = "cyan",
        command: str = "",
        detail: str = "",
        tutorial: bool = False,
    ):
        self.objective_title = title.upper()
        self.objective_body = body
        self.objective_tone = tone
        self.objective_command = command
        self.objective_detail = detail
        self.objective_is_tutorial = tutorial

    def apply_objective_card(self, card):
        self.set_objective(
            card.title,
            card.body,
            tone=card.tone,
            command=card.command,
            detail=card.detail,
            tutorial=card.tutorial,
        )

    def clear_objective(self):
        self.apply_objective_card(live_grid_card())

    def has_standard_travel_unlock(self):
        return bool(self.state and self.state.has_meta("subnet_travel"))

    def has_supercruise_unlock(self):
        return bool(self.state and self.state.has_meta("supercruise"))

    def get_ascii_art(self, art_key: str):
        return ASCII_ART.get(art_key, "")

    def update_arsenal_display(self, arsenal: Arsenal):
        lines = ["TOOLS", " name         ram  class"]
        visible_scripts = list(arsenal.scripts.keys())
        visible_flags = list(arsenal.flags.keys())
        if self.player:
            visible_scripts = [name for name in arsenal.scripts if self.player.owns_script(name)]
            visible_flags = [flag for flag in arsenal.flags if self.player.owns_flag(flag)]

        for name in visible_scripts:
            data = arsenal.scripts[name]
            role = self.databank_role_label("script", name, data)
            lines.append(f" {name:<12} {data['ram']:>2}   {role:<10}")
        lines.extend(["", "FLAGS", " flag         ram  class"])
        for flag in visible_flags:
            data = arsenal.flags[flag]
            role = self.databank_role_label("flag", flag, data)
            lines.append(f" {flag:<12} +{data['ram']:<2}  {role:<10}")
        visible_items = []
        if self.item_library:
            for item_id in sorted(self.item_library):
                if self.player and self.player.get_consumable_count(item_id) <= 0:
                    continue
                visible_items.append(item_id)

        if visible_items:
            lines.extend(["", "ITEMS", " item         mode"])
            for item_id in visible_items:
                data = self.item_library[item_id]
                role = self.databank_role_label("item", item_id, data)
                lines.append(f" {item_id:<12} {role}")
        lines.extend(["", "TARGETS", " OS  NET  MEM  SEC  STO"])
        self.databank_lines = lines
        self.shop_databank_entries = {}

    def clear_shop_databank(self):
        self.shop_databank_entries = {}
        if self.arsenal:
            self.update_arsenal_display(self.arsenal)

    def set_shop_databank(self, shop_stock, consumable_library, module_library):
        self.shop_databank_entries = {}
        lines = ["MARKET", " slot  offer                cost  class"]
        for idx, offer in enumerate(shop_stock, start=1):
            token = f"[{idx}]"
            stock_kind = offer.get("stock_kind", offer.get("type", "misc"))
            if stock_kind == "script":
                class_label = "script"
            elif stock_kind == "flag":
                class_label = "flag"
            elif stock_kind == "module":
                class_label = "module"
            elif stock_kind == "bot":
                class_label = "bot"
            elif stock_kind in {"heal", "ram", "trace"}:
                class_label = "system"
            else:
                class_label = "item"

            title = offer.get("name", offer.get("item_id", offer.get("script_id", offer.get("flag_id", offer.get("module_id", "offer")))))
            self.shop_databank_entries[token] = {
                "kind": "shop_offer",
                "id": offer.get("offer_id", title),
                "title": title,
                "data": {
                    **dict(offer),
                    "consumable_library": consumable_library,
                    "module_library": module_library,
                },
            }
            lines.append(f" {token:<5} {title[:20]:<20} {offer.get('cost', 0):>4}  {class_label}")
        self.databank_lines = lines

    def script_unlock_thresholds(self):
        mapping = {}
        for threshold, script_ids in self.DAY_SCRIPT_UNLOCKS.items():
            for script_id in script_ids:
                mapping.setdefault(script_id, threshold)
        return mapping

    def flag_unlock_thresholds(self):
        mapping = {}
        for threshold, flag_ids in self.DAY_FLAG_UNLOCKS.items():
            for flag_id in flag_ids:
                mapping.setdefault(flag_id, threshold)
        return mapping

    def scaled_shop_cost(self, base_cost: int, *, weight: float = 1.0) -> int:
        current_day = max(1, self.state.day if self.state else 1)
        progression = self.state.get_progression_score() if self.state and hasattr(self.state, "get_progression_score") else current_day
        scale = 1.0 + ((current_day - 1) * 0.06) + ((progression // 12) * 0.03 * weight)
        return max(8, int(round(base_cost * scale)))

    def build_shop_stock(self, events_data):
        base_shop_items = list(events_data.get("shops", {}).items())
        consumable_library = events_data.get("consumables", {})
        module_library = events_data.get("modules", {})
        if not base_shop_items:
            return []

        progression = self.state.get_progression_score() if self.state and hasattr(self.state, "get_progression_score") else self.state.day
        current_day = max(1, self.state.day if self.state else 1)
        tier_budget = max(progression, current_day * 4 - 2)
        subnet_token = sum(ord(ch) for ch in str(getattr(self.state, "current_subnet_id", "") or ""))
        node_token = int(self.map_active or 0)
        rng = random.Random((self.state.run_seed if self.state else 0) + current_day * 101 + progression * 17 + subnet_token + (node_token * 29))

        def eligible_static(item_id, item):
            item_type = item.get("type")
            if item_type == "heal":
                return True
            if item_type == "consumable":
                return True
            if item_type == "trace":
                return current_day >= 2 or progression >= 6
            if item_type == "ram":
                return current_day >= 2 or progression >= 8
            if item_type == "bot":
                return current_day >= 2 or progression >= 10
            if item_type == "module":
                return current_day >= 3 or progression >= 14
            return True

        sustain_pool = []
        tactical_pool = []
        infrastructure_pool = []
        for item_id, item in base_shop_items:
            if not eligible_static(item_id, item):
                continue
            offer = dict(item)
            offer["offer_id"] = item_id
            offer["cost"] = self.scaled_shop_cost(item.get("cost", 0), weight=1.0 if item.get("type") != "module" else 1.25)
            offer["stock_kind"] = item.get("type")
            item_type = item.get("type")
            if item_type in {"heal", "trace"} or (item_type == "consumable" and item.get("item_id") in {"ram_capsule", "failsafe_patch"}):
                sustain_pool.append(offer)
            elif item_type in {"module", "bot", "ram"}:
                infrastructure_pool.append(offer)
            else:
                tactical_pool.append(offer)

        stock = []
        used_offer_ids = set()

        def pick_from(pool):
            available = [offer for offer in pool if offer["offer_id"] not in used_offer_ids]
            if not available:
                return None
            chosen = rng.choice(available)
            used_offer_ids.add(chosen["offer_id"])
            return chosen

        for pool in (sustain_pool, tactical_pool):
            chosen = pick_from(pool)
            if chosen:
                stock.append(chosen)

        if current_day >= 2 or progression >= 8:
            chosen = pick_from(infrastructure_pool)
            if chosen:
                stock.append(chosen)

        script_thresholds = self.script_unlock_thresholds()
        if self.arsenal and self.player:
            script_candidates = [
                script_id
                for script_id, threshold in script_thresholds.items()
                if threshold > 0
                and threshold <= tier_budget
                and not self.player.owns_script(script_id)
                and script_id in self.arsenal.scripts
            ]
            if script_candidates:
                script_id = rng.choice(script_candidates)
                script_data = self.arsenal.scripts[script_id]
                stock.append(
                    {
                        "offer_id": f"script::{script_id}",
                        "name": script_id,
                        "stock_kind": "script",
                        "script_id": script_id,
                        "cost": self.scaled_shop_cost(36 + (script_data.get("ram", 0) * 18), weight=1.2),
                    }
                )

        flag_thresholds = self.flag_unlock_thresholds()
        if self.arsenal and self.player and (current_day >= 2 or progression >= 10):
            flag_candidates = [
                flag_id
                for flag_id, threshold in flag_thresholds.items()
                if threshold > 0
                and threshold <= tier_budget
                and not self.player.owns_flag(flag_id)
                and flag_id in self.arsenal.flags
            ]
            if flag_candidates:
                flag_id = rng.choice(flag_candidates)
                flag_data = self.arsenal.flags[flag_id]
                stock.append(
                    {
                        "offer_id": f"flag::{flag_id}",
                        "name": flag_id,
                        "stock_kind": "flag",
                        "flag_id": flag_id,
                        "cost": self.scaled_shop_cost(24 + (flag_data.get("ram", 0) * 16), weight=1.15),
                    }
                )

        target_stock = 4 if current_day < 3 else 5
        while len(stock) < target_stock:
            chosen = pick_from(tactical_pool) or pick_from(sustain_pool) or pick_from(infrastructure_pool)
            if not chosen:
                break
            stock.append(chosen)

        return stock[:target_stock]

    def apply_day_unlocks(self, *, announce: bool = False):
        if not self.player or not self.state:
            return []

        progression_score = self.state.get_progression_score() if hasattr(self.state, "get_progression_score") else self.state.day
        meta_labels = {
            "dry_run": "dry_run",
            "subnet_travel": "subnet travel",
            "pattern_cache": "pattern cache",
            "supercruise": "supercruise",
        }
        unlocked_lines = []
        unlocked_scripts = []
        unlocked_flags = []
        unlocked_meta = []

        for unlock_threshold, script_ids in sorted(self.DAY_SCRIPT_UNLOCKS.items()):
            if progression_score < unlock_threshold:
                continue
            for script_id in script_ids:
                if not self.player.owns_script(script_id):
                    self.player.grant_script(script_id)
                    unlocked_scripts.append(script_id)

        for unlock_threshold, flag_ids in sorted(self.DAY_FLAG_UNLOCKS.items()):
            if progression_score < unlock_threshold:
                continue
            for flag_id in flag_ids:
                if not self.player.owns_flag(flag_id):
                    self.player.grant_flag(flag_id)
                    unlocked_flags.append(flag_id)

        for unlock_threshold, unlock_ids in sorted(self.DAY_META_UNLOCKS.items()):
            if progression_score < unlock_threshold:
                continue
            for unlock_id in unlock_ids:
                if not self.state.has_meta(unlock_id):
                    self.state.unlock_meta(unlock_id)
                    unlocked_meta.append(unlock_id)

        if unlocked_scripts:
            unlocked_lines.append(f"[UNLOCK] scripts: {', '.join(unlocked_scripts)}")
        if unlocked_flags:
            unlocked_lines.append(f"[UNLOCK] flags: {', '.join(unlocked_flags)}")
        if unlocked_meta:
            unlocked_lines.append(
                f"[UNLOCK] systems: {', '.join(meta_labels.get(unlock_id, unlock_id) for unlock_id in unlocked_meta)}"
            )

        if self.arsenal:
            self.update_arsenal_display(self.arsenal)

        if announce:
            for line in unlocked_lines:
                print(line)

        return unlocked_lines

    def set_network_world(
        self,
        world=None,
        cleared_nodes=None,
        active_index=None,
        status_text=None,
        *,
        network=None,
        subnet_id=None,
        domain_id=None,
    ):
        self.map_world = world
        self.map_cleared = set(cleared_nodes or set())
        self.map_active = active_index
        self.map_network = network
        self.map_subnet_id = subnet_id
        self.map_domain_id = domain_id
        if status_text:
            self.map_status = status_text
        elif not world:
            self.map_status = "Awaiting active subnet."
        else:
            self.map_status = f"{world.subnet_name} | {len(world.nodes)} visible routes"

    @staticmethod
    def get_contract_status(contract):
        if contract.get("completed"):
            return "DONE"
        if contract.get("failed"):
            return "FAILED"
        if contract.get("accepted"):
            return "TRACKING"
        return "AVAILABLE"

    def build_contract_node_summary(self, ip_address: str, *, accepted_only=False):
        if not self.state:
            return None

        contracts = self.state.get_contracts_for_node(ip_address, accepted_only=accepted_only)
        if not contracts:
            return None

        labels = []
        for contract in contracts[:2]:
            status = self.get_contract_status(contract)
            labels.append(f"{status.lower()} {contract['type']}")
        return "contracts: " + " | ".join(labels)

    def view_contract_inbox(self, world):
        if not self.state:
            self.clear_screen()
            print("=== DEAD DROP // CONTRACT INBOX ===\n")
            print("[sys] Inbox offline. No session state is loaded.")
            input("[Press Enter to return to the route mesh...]")
            return

        while True:
            self.clear_screen()
            tracked_contracts = self.state.get_accepted_contracts()
            inbox_contracts = list(self.state.current_contracts)
            if not tracked_contracts and not inbox_contracts:
                print("=== DEAD DROP // CONTRACT INBOX ===\n")
                print("[sys] Inbox empty. No buyers are whispering right now.")
                input("[Press Enter to return to the route mesh...]")
                return

            active_count = len(tracked_contracts)
            print("=== DEAD DROP // CONTRACT INBOX ===\n")
            print(
                f"Subnet: {world.subnet_name}   Day: {self.state.day}   "
                f"Wallet: {self.state.player_crypto} Crypto   Active: {active_count}\n"
            )

            menu_contracts = []
            if tracked_contracts:
                print("[TRACKING]")
                for contract in tracked_contracts:
                    menu_contracts.append(contract)
                    idx = len(menu_contracts)
                    print(
                        f"[{idx}] TRACKING {contract['sender']} :: {contract['subject']}"
                    )
                    print(
                        f"    target {contract['target_ip']} ({contract['target_node_type'].upper()}) | "
                        f"payout {contract['reward']} Crypto"
                    )
                    print(f"    {contract['brief']}")
                    print(f"    condition: {contract['condition_text']}\n")

            if inbox_contracts:
                print("[INBOX]")
            for contract in inbox_contracts:
                menu_contracts.append(contract)
                idx = len(menu_contracts)
                status = self.get_contract_status(contract)
                print(
                    f"[{idx}] {status:<8} {contract['sender']} :: {contract['subject']}"
                )
                print(
                    f"    target {contract['target_ip']} ({contract['target_node_type'].upper()}) | "
                    f"payout {contract['reward']} Crypto"
                )
                print(f"    {contract['brief']}")
                print(f"    condition: {contract['condition_text']}\n")

            print("[0] Return to route mesh")
            choice = input("Open contract #: ").strip().lower()

            if choice in {"0", "q", "exit", "back"}:
                return

            if not choice.isdigit() or not (1 <= int(choice) <= len(menu_contracts)):
                print("[sys] Mail index invalid.")
                time.sleep(0.7)
                continue

            contract = menu_contracts[int(choice) - 1]
            self.clear_screen()
            print(f"[sys] Intercepted packet opened: ~/.mail/{contract['id'].replace(':', '_')}.msg\n")
            print(f"FROM:    {contract['sender']}")
            print(f"SUBJECT: {contract['subject']}")
            print(f"TARGET:  {contract['target_ip']} ({contract['target_node_type'].upper()})")
            print(f"PAYOUT:  {contract['reward']} Crypto\n")
            print(contract["body"])
            print(f"\nCondition: {contract['condition_text']}")

            status = self.get_contract_status(contract)
            if status == "AVAILABLE":
                prompt = "\n[A] Accept contract   [Enter] Return"
            else:
                prompt = f"\n[{status}] archived in ledger   [Enter] Return"
            action = input(prompt + "\n> ").strip().lower()
            if action == "a" and status == "AVAILABLE":
                self.state.accept_contract(contract["id"])
                self.checkpoint_progress()
                print(f"[sys] Contract accepted. Route marker pinned on {contract['target_ip']}.")
                time.sleep(1.0)

    def build_exploit_manual_text(self):
        if not self.state or not getattr(self.state, "exploit_catalog", None):
            return "\n=== MAN PAGE: EXPLOITS ===\n> No run signatures loaded.\n\n"

        known = self.state.get_known_exploits()
        total = len(self.state.exploit_catalog)
        lines = [
            "\n=== MAN PAGE: EXPLOITS ===",
            f"> Known signatures: {len(known)}/{total}",
        ]

        starter = self.state.get_tutorial_exploit()
        if starter:
            lines.extend(
                [
                    "",
                    f"> Starter zero-day: {starter['name']}",
                    f"> Chain: {starter['sequence_text']}",
                    f"> Condition: {starter['condition_text']}",
                    f"> Effect: {starter['effect_text']}",
                ]
            )

        for exploit in known:
            if starter and exploit["id"] == starter["id"]:
                continue
            lines.extend(
                [
                    "",
                    f"> {exploit['name']}",
                    f"> Chain: {exploit['sequence_text']}",
                    f"> Condition: {exploit['condition_text']}",
                    f"> Effect: {exploit['effect_text']}",
                ]
            )

        hidden = self.state.get_unknown_exploit_count()
        if hidden > 0:
            lines.extend(["", f"> {hidden} hidden signature(s) still undiscovered this run."])

        return "\n".join(lines) + "\n\n"

    def build_item_manual_text(self):
        if not self.item_library:
            return "\n=== MAN PAGE: ITEMS ===\n> No consumable ledger loaded.\n\n"

        visible_items = self.get_visible_item_ids()
        lines = [
            "\n=== MAN PAGE: ITEMS ===",
            "> Syntax: use <item> or use <item> -target <SUB>",
        ]
        if not visible_items:
            lines.extend(["", "> No carried consumables on this rig."])
            return "\n".join(lines) + "\n\n"

        for item_id in visible_items:
            data = self.item_library[item_id]
            amount = self.player.get_consumable_count(item_id) if self.player else 0
            lines.extend(
                [
                    "",
                    f"> {item_id} x{amount}",
                    f"> {data.get('description', 'No data.')}",
                    f"> Type man {item_id} for the full page.",
                ]
            )
        return "\n".join(lines) + "\n\n"

    @staticmethod
    def format_manual_page(title: str, sections: list[tuple[str, list[str] | str]]):
        lines = [f"\n=== MAN PAGE: {title.upper()} ==="]
        for heading, body in sections:
            lines.append(f"> {heading}")
            body_lines = body if isinstance(body, list) else [body]
            for line in body_lines:
                lines.append(f">   {line}")
            lines.append(">")
        if lines and lines[-1] == ">":
            lines.pop()
        return "\n".join(lines) + "\n\n"

    @staticmethod
    def normalize_manual_topic(topic: str):
        aliases = {
            "system": "subsystems",
            "systems": "subsystems",
            "subsystem": "subsystems",
            "recovery": "ram",
            "memory": "mem",
            "defence": "defense",
            "active-defense": "defense",
            "active_defense": "defense",
            "active": "defense",
            "tool": "commands",
            "tools": "commands",
            "payload": "commands",
            "payloads": "commands",
            "command": "commands",
            "shell": "shell",
            "terminal": "shell",
            "dev-terminal": "shell",
            "dev_terminal": "shell",
            "filesystem": "shell",
            "paths": "shell",
            "pwd": "pwd",
            "ls": "ls",
            "cat": "cat",
            "history": "history",
            "whoami": "whoami",
            "hostname": "hostname",
            "uname": "uname",
            "date": "date",
            "cls": "cls",
            "reset": "reset-terminal",
            "mods": "flags",
            "modifier": "flags",
            "modifiers": "flags",
            "bot": "bots",
            "trace-level": "trace",
            "trace_level": "trace",
            "heat": "trace",
            "noise": "noise",
            "bf": "noise",
            "ex": "noise",
            "brute-noise": "noise",
            "brute_noise": "noise",
            "exploit-noise": "noise",
            "exploit_noise": "noise",
            "hunter": "sweep",
            "hunt": "sweep",
            "sweeps": "sweep",
            "brute": "brute-force",
            "bruteforce": "brute-force",
            "brute_force": "brute-force",
            "rooted": "root",
            "bricked": "brick",
            "phase": "phases",
            "cleanup": "phases",
            "contract": "contracts",
            "contracts": "contracts",
            "domain": "domains",
            "domains": "domains",
            "estate": "domains",
            "bus": "buses",
            "buses": "buses",
            "backplane": "buses",
            "backplanes": "buses",
            "fabric": "buses",
            "bus-fabric": "buses",
            "bus_fabric": "buses",
        }
        return aliases.get(topic, topic)

    def build_topic_manual_text(self, target: str):
        topic = self.normalize_manual_topic(target)

        if not self.is_manual_topic_visible(topic):
            return None

        if topic in {"os", "sec", "net", "mem", "sto"}:
            return self.build_subsystem_manual_text(topic.upper())

        if topic == "commands":
            return self.build_command_index_manual_text()

        if topic == "flags":
            return self.build_flag_index_manual_text()

        topic_pages = {
            "subsystems": [
                (
                    "SUBSYSTEM MAP",
                    [
                        "OS = kill target.",
                        "SEC = firewall shell that soaks direct OS damage.",
                        "NET = scans, routing, disconnects, and recon quality.",
                        "MEM = RAM recovery plus effective max RAM.",
                        "STO = storage, caches, and loot value.",
                    ],
                ),
            ],
            "shell": [
                (
                    "DEV TERMINAL",
                    [
                        "This shell is meant to feel like a real Linux terminal, not just a log window.",
                        "It includes local helper commands for inspecting the run without touching the side panels.",
                        "Those helpers read from a pseudo-filesystem backed by live game state.",
                    ],
                ),
                (
                    "KEY PATHS",
                    [
                        "~/proc/player = your rig snapshot.",
                        "~/proc/target = current hostile brief.",
                        "~/proc/objective = live objective card.",
                        "~/proc/architecture = hostile subsystem lattice while linked.",
                        "~/net/routeweb = route mesh while roaming.",
                        "~/usr/share/databank = installed tools, flags, items, and targets.",
                            "~/var/log/session.log = formatted session archive that survives clear-screen.",
                        "~/var/log/history.log = commands typed this session.",
                    ],
                ),
                (
                    "LOCAL COMMANDS",
                    [
                        "pwd = show the shell path.",
                        "ls = list a virtual directory.",
                        "cat = print a virtual state file.",
                        "history = show commands typed this session.",
                        "whoami / hostname / uname / date = environment reads and flavor.",
                        "clear = wipe the terminal outside combat. cls or reset-terminal always wipe the viewport.",
                    ],
                ),
            ],
            "classes": [
                (
                    "CLASS OVERVIEW",
                    [
                        "scan = information. It tells you what the host is, what it plans to do, or where it is weak.",
                        "brute-force = loud direct damage. It ends fights once setup work is done.",
                        "exploit = opening lanes, precision pressure, or special board state changes.",
                        "utility = defense, repair, scrub, prediction, or control.",
                    ],
                ),
            ],
            "phases": [
                (
                    "TURN PHASES",
                    [
                        "Recon = passive intel gathering before breach, plus scan-class payloads used during a live link.",
                        "Execution = stack construction and queue commit.",
                        "Cleanup = hostile response, forensic residue, RAM recovery, and route-state stabilization before the next turn.",
                    ],
                ),
                (
                    "CONTEXT-AWARE TOOLS",
                    [
                        "nmap, enum, whois, and dirb behave differently depending on whether you use them during passive recon or inside a live combat link.",
                        "dry_run clones the current stack against a ghost copy of the target and never wakes the real hostile routine.",
                    ],
                ),
            ],
            "root": [
                (
                    "ROOT ACCESS",
                    [
                        "A clean core finish grants rooted control instead of wrecking the host.",
                        "Rooted nodes keep their route value, yield recoverable loot, and store module slots for later systems.",
                    ],
                ),
            ],
            "brick": [
                (
                    "BRICKED NODE",
                    [
                        "A sloppy kill chain or destabilized core finish bricks the node.",
                        "Bricked nodes still clear the route, but their data image is dead and no rewards are recovered.",
                    ],
                ),
            ],
            "dry_run": [
                (
                    "SANDBOX",
                    [
                        "dry_run clones the current hostile state and resolves the queued stack against that ghost copy.",
                        "It prints predicted RAM flow, payload order, and the likely node outcome without triggering the real enemy AI.",
                        "This feature is unlocked later in the run ladder and does not spend the turn when used from planning.",
                    ],
                ),
            ],
            "contracts": [
                (
                    "CONTRACT PIPELINE",
                    [
                        "mail opens newly issued offers for the current route mesh.",
                        "Accepting a job moves it into the active contract ledger until you resolve or fail it.",
                        "Tracked contracts appear in the objective tracker, node intel, and the contracts shell command.",
                    ],
                ),
                (
                    "SHELL ACCESS",
                    [
                        "Type mail to review offers in the dead drop.",
                        "Type contracts to print tracked jobs plus any waiting offers.",
                        "cat ~/proc/contracts prints the same ledger through the pseudo-filesystem.",
                    ],
                ),
            ],
            "domains": [
                (
                    "ROOTED NODES",
                    [
                        "A rooted node keeps one infrastructure slot until a later upgrade expands it.",
                        "Bricked nodes keep zero slots and zero retained infrastructure value.",
                        "Installing a module burns that one slot until the node is upgraded in a later system pass.",
                    ],
                ),
                (
                    "MODULE TYPES",
                    [
                        "vpn_tunnel = fast travel back into that rooted node shell.",
                        "botnet_seed = permanent remote traffic that scales DDOS output globally.",
                        "crypto_miner = passive Crypto yield when the route mesh rolls forward.",
                    ],
                ),
            ],
            "scan": [
                (
                    "SCAN CLASS",
                    [
                        "They reveal topology, ownership, telemetry, or hostile intent depending on the tool.",
                        "Scans also matter before combat: the recon shell can reveal intel at the cost of exposure.",
                    ],
                ),
                (
                    "KEY TOOLS",
                    [
                        "nmap = banner, weapon, and layout.",
                        "enum = exact HP on one subsystem plus cleaner hostile intent.",
                        "whois = safer breadcrumb recon.",
                        "dirb = lower-exposure targeted telemetry.",
                    ],
                ),
            ],
            "brute-force": [
                (
                    "BRUTE-FORCE CLASS",
                    [
                        "They are louder, more predictable, and easier for the host to adapt to if you spam them.",
                        "They convert access and timing windows into direct subsystem pressure.",
                    ],
                ),
            ],
            "exploit": [
                (
                    "EXPLOIT CLASS",
                    [
                        "Exploit scripts are not always pure damage.",
                        "They can open SEC, pressure specific architectures, or set up stronger later hits.",
                        "Many exploits care about services, endpoint hits, or exposed lanes rather than raw force alone.",
                    ],
                ),
            ],
            "utility": [
                (
                    "UTILITY CLASS",
                    [
                        "They usually do not race OS damage directly, but they stop the enemy from dictating the fight.",
                        "This class includes hardening, deception, buffering, repair, and session control routines.",
                    ],
                ),
            ],
            "recon": [
                (
                    "PRE-BREACH RECON",
                    [
                        "Before combat, you know nothing by default if the node has not already been scanned.",
                        "Running recon scripts in the recon shell can reveal layout, telemetry, or identity, but it also builds exposure.",
                        "Too much exposure starts combat warmer or hotter because the host noticed you first.",
                    ],
                ),
                (
                    "RECON LADDER",
                    [
                        "nmap = banner, weapon, layout.",
                        "enum -target <SUB> = exact HP on one subsystem and better intent read.",
                        "airmon-ng -target SEC = open the firewall shell.",
                        "nmap -target <SUB> = fingerprint a weakness once the firewall is open.",
                    ],
                ),
            ],
            "combat": [
                (
                    "TURN FLOW",
                    [
                        "Queue commands during planning.",
                        "Type execute to run them in order.",
                        "After your queue resolves, the host takes its turn.",
                        "Then RAM recovers on later turns based on MEM health.",
                    ],
                ),
                (
                    "TACTICAL RULES",
                    [
                        "RAM does not fully reset every turn.",
                        "Flags stack if the script and your rig both support them.",
                        "Disconnect is legal, but it costs trace and Core OS integrity.",
                        "If the host adapts to repeated loud lines, mix your tempo or change lanes.",
                    ],
                ),
            ],
            "defense": [
                (
                    "ACTIVE DEFENSE",
                    [
                        "Defense tools are prediction tools. They are strongest when you read hostile intent correctly.",
                        "Most of them are better one turn early than one turn late.",
                    ],
                ),
                (
                    "DEFENSE KIT",
                    [
                        "harden = put temporary integrity on one subsystem.",
                        "honeypot = burn the next hostile scan into fake telemetry.",
                        "canary = punish the next hostile commit to the chosen lane.",
                        "sinkhole = reflect the next hostile move on the chosen lane.",
                        "rekey = clear RAM lock residue and peel back one recon stage.",
                        "spoof = corrupt hostile recon after they already learned something.",
                    ],
                ),
            ],
            "ram": [
                (
                    "RAM RECOVERY",
                    [
                        "The stat that controls RAM recovery is MEM.",
                        "MEM also reduces your effective max RAM as it gets damaged.",
                        "So MEM damage hurts you twice: you recover slower and your ceiling shrinks.",
                    ],
                ),
                (
                    "EXACT RECOVERY TIERS",
                    [
                        "MEM above 67% HP -> 4 RAM per turn.",
                        "MEM at 34% to 67% HP -> 3 RAM per turn.",
                        "MEM at 1% to 33% HP -> 2 RAM per turn.",
                        "MEM destroyed -> 1 RAM per turn.",
                    ],
                ),
                (
                    "MAX RAM PENALTY",
                    [
                        "Every 4 missing MEM HP removes 1 point from effective max RAM.",
                        "Support bots also reserve RAM, so bad MEM plus too many bots can choke your action budget hard.",
                    ],
                ),
            ],
            "trace": [
                (
                    "TRACE",
                    [
                        "Trace is the cost of being loud in the network.",
                        "Brute-force and exploit scripts usually add threat-ledger noise unless a stealth wrapper prevents it.",
                        "Flags like --burst and --volatile make the trace bill worse.",
                    ],
                ),
                (
                    "WHY IT MATTERS",
                    [
                        "Trace is a run-level pressure stat, not just a single-fight number.",
                        "If trace climbs too far, the run gets hotter and riskier.",
                        "Fleeing under fire also spikes trace.",
                    ],
                ),
            ],
            "noise": [
                (
                    "NOISE LEDGER",
                    [
                        "Noise is the network's memory of how you have been operating across the run.",
                        "The ledger is split into BF and EX.",
                        "BF means brute-force noise. EX means exploit noise.",
                    ],
                ),
                (
                    "WHAT BF AND EX MEAN",
                    [
                        "BF climbs when you lean on loud direct pressure like brute-force payloads and noisy flags.",
                        "EX climbs when you lean on exploit-style access abuse, injection, and similar exploit traffic.",
                        "The higher bucket becomes your visible style profile for scaling, events, and some hostile adaptation.",
                    ],
                ),
            ],
            "sweep": [
                (
                    "SWEEP",
                    [
                        "Sweep is the current subnet's hunt pressure.",
                        "It represents defenders, scanners, or hunter-net activity tightening around your local route mesh.",
                        "It is local to the current subnet, while trace is global to the run.",
                    ],
                ),
                (
                    "WHY IT MATTERS",
                    [
                        "Higher sweep means hotter breaches and more route pressure while you stay in that subnet.",
                        "You can think of it as the local timer pushing the mesh toward a worse security posture.",
                    ],
                ),
            ],
            "buses": [
                (
                    "WHAT BUSES ARE",
                    [
                        "Buses are the internal links between subsystems inside one host.",
                        "They are shown as arrows or links because they are the paths traffic, state, and hardware fallout can travel through.",
                        "A bus is not another subsystem to kill. It is the route between subsystems.",
                    ],
                ),
                (
                    "WHY YOU CARE",
                    [
                        "Splash and crash effects can travel across live buses.",
                        "If you blow up one subsystem hard enough, nearby linked subsystems can get clipped too.",
                        "That can help you spread pressure, or accidentally brick a fragile host if you get sloppy.",
                    ],
                ),
                (
                    "HOW TO READ THEM",
                    [
                        "SEC <-> NET usually means perimeter traffic and session handoff.",
                        "OS <-> MEM means runtime and working-state pressure.",
                        "OS <-> STO means filesystem or cache traffic.",
                        "If a connected subsystem dies, that route can cut or cascade depending on the effect that hit it.",
                    ],
                ),
            ],
            "syntax": [
                (
                    "COMMAND SYNTAX",
                    [
                        "Basic form: <script> <flags> -target <SUBSYSTEM>",
                        "Example: hydra --burst --volatile -target MEM",
                        "Flags can be stacked if the script supports them and your current rig owns them.",
                        "If a damage script has no target, it usually defaults to OS.",
                    ],
                ),
                (
                    "SPECIAL CASES",
                    [
                        "use <item> or use <item> -target <SUB> spends a consumable.",
                        "execute runs the queued turn.",
                        "clear wipes the current queue.",
                        "wait or pass yields the turn without spending RAM.",
                        "defend <SUB> grants a free short ACL shell on that subsystem.",
                        "repair <SUB> spends the turn restoring a little integrity to your own rig.",
                        "disconnect attempts to flee the encounter.",
                    ],
                ),
            ],
            "bots": [
                (
                    "SUPPORT BOTS",
                    [
                        "Bots reserve part of your RAM budget permanently.",
                        "In exchange, they can fire a configured payload on their cadence after your queue resolves.",
                        "Their payload still has to fit their RAM cap and your installed toolkit.",
                    ],
                ),
                (
                    "WHY THEY EXIST",
                    [
                        "Bots are the future home for partial exploit automation.",
                        "They are best at repeating a useful line without spending your own planning slot every turn.",
                    ],
                ),
            ],
        }

        sections = topic_pages.get(topic)
        if not sections:
            return None
        return self.format_manual_page(topic, sections)

    def build_command_index_manual_text(self):
        installed_scripts = []
        installed_flags = []
        if self.arsenal:
            for script_id in self.get_installed_script_ids():
                data = self.arsenal.scripts[script_id]
                label = f"{script_id} ({data.get('type', 'tool').replace('_', '-')}, {data.get('ram', 0)} RAM)"
                installed_scripts.append(label)
            for flag_id in self.get_installed_flag_ids():
                data = self.arsenal.flags[flag_id]
                label = f"{flag_id} (+{data.get('ram', 0)} RAM)"
                installed_flags.append(label)

        shell_helpers = [
            "pwd, ls, cat, history, whoami, hostname, uname, date, clear, cls, reset-terminal, dev.",
            "These do not spend RAM and are meant to make the terminal feel like a real machine.",
        ]
        if self.state and self.state.has_meta("dry_run"):
            shell_helpers.insert(0, "dry_run = resolve the queued stack against a ghost copy of the current host.")

        return self.format_manual_page(
            "commands",
            [
                ("WHAT THIS IS", "Index of payloads, modifiers, and local shell helpers currently exposed on this rig."),
                ("INSTALLED SCRIPTS", installed_scripts or ["none installed"]),
                ("INSTALLED FLAGS", installed_flags or ["none installed"]),
                ("LOCAL SHELL HELPERS", shell_helpers),
            ],
        )

    def build_flag_index_manual_text(self):
        installed_flags = []
        if self.arsenal:
            for flag_id in self.get_installed_flag_ids():
                data = self.arsenal.flags[flag_id]
                installed_flags.append(f"{flag_id} = {data.get('description', 'No data.')}")

        return self.format_manual_page(
            "flags",
            [
                (
                    "FLAG BASICS",
                    [
                        "Flags are modifiers added to scripts in the same command line.",
                        "They only work if the script supports them and this rig actually owns them.",
                        "Queue execution prints stacked modifiers one by one during commit.",
                    ],
                ),
                ("INSTALLED FLAGS", installed_flags or ["none installed"]),
            ],
        )

    def build_subsystem_manual_text(self, subsystem_id: str):
        subsystem_id = subsystem_id.upper()
        current_lines = []
        if self.player and subsystem_id in self.player.subsystems:
            subsystem = self.player.subsystems[subsystem_id]
            current_lines.append(f"Current rig value: {subsystem.current_hp}/{subsystem.max_hp} HP.")
            if subsystem_id == "MEM":
                current_lines.append(f"Current RAM recovery: {self.player.get_ram_regen()} per turn.")
                mem_penalty = max(0, (subsystem.max_hp - subsystem.current_hp) // 4)
                current_lines.append(f"Current max RAM penalty from MEM damage: {mem_penalty}.")

        subsystem_pages = {
            "OS": [
                ("ROLE", ["Core kill target. If OS reaches 0, that side loses the fight."]),
                ("HOW IT BEHAVES", ["If SEC is still online, most direct OS damage gets intercepted first.", "Subsystem collapses can still splash extra pressure into OS."]),
            ],
            "SEC": [
                ("ROLE", ["Firewall shell. It absorbs most direct OS pressure while it is standing."]),
                ("HOW IT BEHAVES", ["Breaking SEC opens cleaner routes for direct damage.", "Breaking or disrupting SEC also enables deeper weakness fingerprinting with targeted nmap.", "airmon-ng is the main dedicated tool for opening this lane."]),
            ],
            "NET": [
                ("ROLE", ["Network and routing layer. It powers scans, trace pressure, and clean disconnects."]),
                ("HOW IT BEHAVES", ["If your NET dies, you lose scan reliability and even disconnect can fail.", "Damaging enemy NET weakens their recon and routing quality."]),
            ],
            "MEM": [
                ("ROLE", ["Memory fabric. This is the stat that controls RAM recovery."]),
                ("EXACT RAM RECOVERY", ["Above 67% HP -> 4 RAM per turn.", "34% to 67% HP -> 3 RAM per turn.", "1% to 33% HP -> 2 RAM per turn.", "0 HP -> 1 RAM per turn."]),
                ("EXACT MAX RAM LOSS", ["For every 4 missing MEM HP, you lose 1 effective max RAM.", "That penalty stacks with bot reservations and temporary RAM lock effects."]),
            ],
            "STO": [
                ("ROLE", ["Storage, caches, and loot-bearing state."]),
                ("HOW IT BEHAVES", ["Breaking STO can spill extra Crypto or value without ending the encounter.", "It is usually an economy target or a precision exploit target, not the main kill lane."]),
            ],
        }

        sections = list(subsystem_pages.get(subsystem_id, [("ROLE", ["Unknown subsystem."])]))
        if current_lines:
            sections.insert(0, ("CURRENT STATE", current_lines))
        return self.format_manual_page(subsystem_id, sections)

    def build_payload_manual_text(self, target: str):
        if not self.arsenal:
            return None

        if target in self.arsenal.scripts:
            installed = not self.player or self.player.owns_script(target)
            if not installed:
                return None
            return self.build_script_manual_text(target, self.arsenal.scripts[target], installed=installed)

        if target in self.arsenal.flags:
            installed = not self.player or self.player.owns_flag(target)
            if not installed:
                return None
            return self.build_flag_manual_text(target, self.arsenal.flags[target], installed=installed)

        if target in self.item_library:
            if self.player and self.player.get_consumable_count(target) <= 0:
                return None
            data = self.item_library[target]
            return self.build_item_entry_manual_text(target, data)

        return None

    def build_script_manual_text(self, script_id: str, data: dict, *, installed: bool = True):
        allowed_flags = self.arsenal.get_owned_allowed_flags(script_id, self.player) if installed else []
        synopsis = script_id
        if data.get("supports_target", True):
            if data.get("default_target"):
                synopsis += f" [-target {str(data.get('default_target')).upper()}]"
            else:
                synopsis += " -target <OS|SEC|NET|MEM|STO>"
        if allowed_flags:
            synopsis += " [" + " ".join(allowed_flags) + "]"

        sections = [
            (
                "IDENTITY",
                [
                    f"Class: {str(data.get('type', 'tool')).replace('_', '-')}.",
                    f"RAM cost: {data.get('ram', 0)}.",
                    f"Status on this rig: {'installed' if installed else 'not installed'}.",
                ],
            ),
            ("SYNOPSIS", [synopsis]),
            ("DESCRIPTION", [data.get("description", "No data.")]),
            ("PHASE BEHAVIOR", self.describe_script_phase_behavior(script_id, data)),
            ("TARGETING", self.describe_script_targeting(script_id, data)),
            ("EFFECTS", self.describe_script_manual_effects(script_id, data)),
        ]
        if installed:
            sections.append(("INSTALLED FLAGS", [", ".join(allowed_flags) if allowed_flags else "none"]))
        else:
            sections.append(("INSTALLED FLAGS", ["not shown because this payload is not installed on the current rig"]))
        return self.format_manual_page(script_id, sections)

    @staticmethod
    def describe_script_targeting(script_id: str, data: dict):
        supports_target = data.get("supports_target", True)
        default_target = data.get("default_target")
        script_type = str(data.get("type", "tool"))

        if not supports_target:
            return [
                "This payload does not accept -target.",
                "It always acts on its own built-in domain rather than a chosen subsystem.",
            ]

        if default_target:
            target_name = str(default_target).upper()
            return [
                f"This payload accepts -target <OS|SEC|NET|MEM|STO>.",
                f"If you omit -target, it defaults to [{target_name}].",
            ]

        if script_type in {"brute_force", "exploit"}:
            return [
                "This payload accepts -target <OS|SEC|NET|MEM|STO>.",
                "If you omit -target, it defaults to [OS].",
            ]

        return [
            "This payload accepts -target <OS|SEC|NET|MEM|STO>.",
            "If you omit -target, the command keeps its current generic routing behavior and may rely on its own internal defaults.",
        ]

    @staticmethod
    def describe_script_phase_behavior(script_id: str, data: dict):
        script_type = str(data.get("type", "tool"))
        if script_type == "scan":
            return [
                "During passive recon, this stays in the recon phase and raises exposure instead of waking the full hostile combat loop.",
                "During a live encounter, it resolves inside the execution stack and can set up adjacency-sensitive follow-through.",
            ]
        if script_id in {"stager", "buffer", "jmp"}:
            return [
                "This is an execution-phase stack-control tool.",
                "It does not damage the host directly; it changes how the immediate nearby payloads resolve.",
            ]
        if script_type == "utility":
            return [
                "Utility payloads resolve in the execution phase and usually change board state rather than raw damage.",
            ]
        return [
            "This payload resolves in the execution phase during a live hostile link.",
        ]

    def build_flag_manual_text(self, flag_id: str, data: dict, *, installed: bool = True):
        sections = [
            (
                "IDENTITY",
                [
                    "Class: modifier.",
                    f"RAM cost: +{data.get('ram', 0)}.",
                    f"Status on this rig: {'installed' if installed else 'not installed'}.",
                ],
            ),
            ("SYNOPSIS", [f"{flag_id} <script> [-target <SUB>]"]),
            ("DESCRIPTION", [data.get("description", "No data.")]),
            ("EFFECTS", self.describe_flag_manual_effects(flag_id, data)),
        ]
        return self.format_manual_page(flag_id, sections)

    def build_item_entry_manual_text(self, item_id: str, data: dict):
        amount = self.player.get_consumable_count(item_id) if self.player else 0
        synopsis = f"use {item_id}"
        if data.get("requires_target"):
            synopsis += " -target <OS|SEC|NET|MEM|STO>"
        sections = [
            ("IDENTITY", [f"Class: consumable.", f"Inventory on this rig: {amount}."]),
            ("SYNOPSIS", [synopsis]),
            ("DESCRIPTION", [data.get("description", "No data.")]),
            ("EFFECTS", self.describe_item_manual_effects(data)),
        ]
        return self.format_manual_page(item_id, sections)

    @staticmethod
    def describe_script_manual_effects(script_id: str, data: dict):
        return script_effect_lines(script_id, data)

    @staticmethod
    def describe_flag_manual_effects(flag_id: str, data: dict):
        return flag_effect_lines(flag_id, data)

    @staticmethod
    def describe_item_manual_effects(data: dict):
        return item_effect_lines(data)

    def build_drone_tutorial_objective(self, enemy):
        card = build_drone_tutorial_card(enemy)
        return card.title, card.body, card.tone, card.command, card.detail

    def get_manual_entry(self, target: str):
        topic = self.normalize_manual_topic(target)
        if not self.is_manual_topic_visible(topic):
            return None
        manuals = {
            "os": "OS is the core execution plane. If it reaches zero, that side loses. Direct OS pressure is inefficient while SEC is still intercepting traffic.",
            "sec": "SEC is the perimeter and access-control layer. It catches most direct OS pressure and often has to be peeled back before deeper fingerprinting works.",
            "net": "NET is the routing and scan plane. It governs recon quality, trace routines, and whether you can still disconnect cleanly.",
            "mem": "MEM is the runtime state and allocator pool. It controls RAM recovery per turn and every 4 missing MEM HP also cuts 1 effective max RAM.",
            "sto": "STO is storage, archives, and cached value. It often holds crypto, loot, exports, and other side rewards without being the primary kill target.",
            "trace": "Trace is your run-wide heat. It rises when you are loud, sloppy, or forced to cut out under pressure, and it makes the whole run more dangerous.",
            "noise": "Noise is the style ledger. BF means brute-force noise and EX means exploit noise. Those buckets tell the world what kind of operator you have been acting like.",
            "sweep": "Sweep is local hunt pressure inside the current subnet. It is the local search net tightening around your current route mesh.",
            "buses": "Buses are the internal links between subsystems inside one host. They matter because splash and cascade effects can travel along them.",
            "classes": "Scripts fall into four operational groups: scan collects telemetry, exploit abuses an exposed surface, brute-force applies loud direct pressure, and utility manages defense or board control.",
            "scan": "Scan scripts collect topology, services, ownership data, or process telemetry. They are how you turn an unknown host into a readable target.",
            "brute": "Brute-force scripts are noisy direct pressure. They force access paths or pound exposed lanes once the host surface is known.",
            "brute-force": "Brute-force scripts are noisy direct pressure. They force access paths or pound exposed lanes once the host surface is known.",
            "brute_force": "Brute-force scripts are noisy direct pressure. They force access paths or pound exposed lanes once the host surface is known.",
            "bruteforce": "Brute-force scripts are noisy direct pressure. They force access paths or pound exposed lanes once the host surface is known.",
            "utility": "Utility scripts handle defense, repair, deception, and control-plane disruption instead of raw damage.",
        }
        return manuals.get(topic)

    def build_black_ice_objective(self, enemy):
        card = build_black_ice_tutorial_card(enemy)
        return card.title, card.body, card.tone, card.command, card.detail

    def make_tutorial_objective_callback(self, stage: str):
        def callback(_phase, enemy, _player, _state):
            if stage == "drone":
                title, body, tone, command, detail = self.build_drone_tutorial_objective(enemy)
            else:
                title, body, tone, command, detail = self.build_black_ice_objective(enemy)
            self.set_objective(title, body, tone, command=command, detail=detail, tutorial=True)

        return callback

    def clear_screen(self):
        with self.io_lock:
            self.log_lines = []
            self.stdout_buffer = ""

    def write(self, text):
        if not text:
            return

        if "Loading external configuration data via PyYAML..." in text:
            text = text.replace(
                "Loading external configuration data via PyYAML...",
                "Decrypting distributed botnet payloads... [OK]\n[sys] Synthesizing zero-day configurations...",
            )

        if (
            "[RUNNING" in text
            or "[COUNTER-ATTACK]" in text
            or "[QUEUE EXECUTION]" in text
            or "[COMBAT LOOP]" in text
            or "--- TARGET:" in text
        ):
            text = "\n" + text.lstrip("\n")

        text = text.replace("\n\n\n", "\n\n")

        with self.io_lock:
            self.stdout_buffer += text
            lines = self.stdout_buffer.split("\n")
            self.stdout_buffer = lines.pop()
            for raw_line in lines:
                color = self.pick_line_color(raw_line)
                plain = strip_ansi(raw_line).replace("\r", "")
                self.log_lines.append((plain, color))
                self.archive_session_line(plain, color)
            if len(self.log_lines) > self.max_log_lines:
                self.log_lines = self.log_lines[-self.max_log_lines :]

    def flush(self):
        pass

    def pick_line_color(self, raw_line: str) -> str:
        for ansi, tone in ANSI_COLOR_HINTS.items():
            if ansi in raw_line:
                return tone

        plain = strip_ansi(raw_line).strip().lower()
        if not plain:
            return "muted"
        if "[err" in plain:
            return "red"
        if "[warn" in plain:
            return "yellow"
        if "[ok" in plain:
            return "green"
        if "[sys" in plain or "[cmd" in plain:
            return "cyan"
        if "[bot" in plain or "[note" in plain:
            return "magenta"
        if "[ops" in plain or "session log //" in plain:
            return "white"
        if "tutorial" in plain or plain.startswith("try :") or plain.startswith("why :"):
            return "magenta"
        if "archive//echo" in plain or "field note" in plain or "burn notice" in plain or "survival primer" in plain:
            return "magenta"
        if "error" in plain or "[!]" in plain or "failed" in plain:
            return "red"
        if plain.startswith("[+]") or "success" in plain or "access granted" in plain:
            return "green"
        if plain.startswith("[sys]") or plain.startswith(">"):
            return "cyan"
        if "trace" in plain or "warning" in plain or "counter-intel" in plain:
            return "yellow"
        if "bot" in plain or "support" in plain:
            return "magenta"
        return "text"

    def custom_input(self, prompt=""):
        stripped = strip_ansi(prompt).replace("\r", "")
        display = " ".join(part.strip() for part in stripped.splitlines() if part.strip())
        self.current_input = ""

        if "root@player:~$" in display:
            parts = display.split("root@player:~$", 1)
            if parts[0].strip():
                self.write(parts[0].strip() + "\n")
            self.active_prompt = self.get_shell_prompt()
        elif "recon@link:~$" in display:
            parts = display.split("recon@link:~$", 1)
            if parts[0].strip():
                self.write(parts[0].strip() + "\n")
            self.active_prompt = self.get_recon_prompt()
        else:
            self.active_prompt = display + (" " if display and not display.endswith(" ") else "")

        response = self.input_queue.get()
        self.active_prompt = ""
        self.current_input = ""
        return response

    def save_progress(self):
        print("\n[sys] Writing autosave checkpoint to local storage...")
        time.sleep(0.5)
        try:
            self.checkpoint_progress()
            print("[sys] Autosave checkpoint updated.")
            time.sleep(1)
            return True
        except Exception as exc:
            print(f"[sys] Critical Error: Save failed. {exc}")
            time.sleep(1)
            return False

    def write_named_save(self, slot_key: str, display_name: str | None = None):
        if not self.state or not self.player:
            raise ValueError("No live session state to save.")
        with self.io_lock:
            self.state.ensure_runtime_defaults()
            if hasattr(self.player, "ensure_runtime_defaults"):
                self.player.ensure_runtime_defaults()
            GameState.save_session(
                self.state,
                self.player,
                slot_key=slot_key,
                display_name=display_name,
            )
            self.active_save_reference = slot_key
        return True

    def checkpoint_progress(self):
        if not self.state or not self.player:
            return False
        self.state.ensure_runtime_defaults()
        if hasattr(self.player, "ensure_runtime_defaults"):
            self.player.ensure_runtime_defaults()
        GameState.save_session(
            self.state,
            self.player,
            slot_key=GameState.AUTOSAVE_SLOT_KEY,
            display_name="autosave",
        )
        return True

    def shutdown_game(self):
        print("\nShutting down Terminal Rogue...")
        time.sleep(1.2)
        self.running = False

    def request_dev_console(self):
        self.dev_console_requested = True

    def consume_dev_console_request(self):
        requested = self.dev_console_requested
        self.dev_console_requested = False
        return requested

    def request_return_to_main_menu(self):
        if self.state and self.player and not getattr(self.state, "game_over", False):
            try:
                self.checkpoint_progress()
            except Exception:
                pass
        self.return_to_menu_requested = True
        if self.active_prompt:
            self.input_queue.put("")

    def reset_frontend_state(self):
        self.state = None
        self.player = None
        self.arsenal = None
        self.current_enemy = None
        self.active_tap_node_index = None
        self.active_prompt = ""
        self.current_input = ""
        self.stdout_buffer = ""
        self.log_lines = []
        self.databank_lines = ["TOOLS", " booting...", "", "FLAGS", " offline"]
        self.map_world = None
        self.map_cleared = set()
        self.map_active = None
        self.map_status = "Awaiting active subnet."
        self.map_network = None
        self.map_subnet_id = None
        self.map_domain_id = None
        self.route_sweep_level = 0
        self.route_sweep_max = 0
        self.command_history = []
        initial_objective = boot_layout_card()
        self.objective_title = initial_objective.title
        self.objective_body = initial_objective.body
        self.objective_tone = initial_objective.tone
        self.objective_command = initial_objective.command
        self.objective_detail = initial_objective.detail
        self.objective_is_tutorial = initial_objective.tutorial
        self.combat_engine = None
        self.return_to_menu_requested = False
        self.selected_save_reference = None
        self.active_save_reference = None

    def purge_live_save_archives(self):
        GameState.delete_session(slot_key=GameState.AUTOSAVE_SLOT_KEY)
        if self.active_save_reference and self.active_save_reference != GameState.AUTOSAVE_SLOT_KEY:
            GameState.delete_session(slot_key=self.active_save_reference)

    def handle_permadeath(self):
        final_day = self.state.day if self.state else 1
        final_crypto = self.state.player_crypto if self.state else 0
        self.purge_live_save_archives()
        self.clear_screen()
        self.apply_objective_card(run_burned_card())
        print("\n" + "#" * 58)
        print("                 RUN TERMINATED // PERMADEATH")
        print("#" * 58 + "\n")
        print("[!] Your burner rig is gone.")
        print("[!] Cold wallet links are severed.")
        print("[!] The save archive for this run has been erased.")
        print(f"[!] Final reach: Day {final_day}")
        print(f"[!] Crypto lost with the run: {final_crypto}")
        input("\n[Press Enter to return to the boot menu...]")
        self.reset_frontend_state()

    def show_message_log(self, filename, message, continue_prompt, art_key=None):
        self.clear_screen()
        art = self.get_ascii_art(art_key) if art_key else ""
        if art:
            art_color = "\033[96m"
            if art_key == "burn_notice":
                art_color = "\033[91m"
            elif art_key == "survival":
                art_color = "\033[92m"
            elif art_key == "archive_echo":
                art_color = "\033[95m"
            print(f"{art_color}{art}\033[0m")
        print(message)
        input(continue_prompt)

    def collapse_from_prologue(self, combat):
        GameState.delete_session(slot_key=GameState.AUTOSAVE_SLOT_KEY)
        self.state.threat_ledger = ThreatLedger()
        self.state.player_crypto = 0
        self.state.trace_level = 0
        self.state.day = 1
        self.state.game_over = False
        self.state.prologue_complete = True
        self.state.origin_story = "rookie"
        self.player = Player(profile="rookie")
        combat.player = self.player

    def run_tutorial_sequence(self, combat, enemies_data, ability_library):
        if not self.state.lore_intro_complete:
            self.state.lore_intro_complete = True
            if not hasattr(self, "boot_menu"):
                self.show_message_log(
                    "orientation.txt",
                    lab_orientation_message(),
                    "[Press Enter to continue...]",
                )
                self.show_message_log(
                    "lab_rules.txt",
                    sandbox_rules_message(),
                    "[Press Enter to bring the workstation online...]",
                )
        self.apply_objective_card(tutorial_bootstrap_card())
        self.clear_screen()
        input("[Press Enter to run the warm-up node...]")

        tutorial_data = enemies_data.get("training_drone", {"name": "Training Drone", "base_os": 8, "budget": 0})
        tutorial_target = Enemy(
            "training_drone",
            tutorial_data,
            self.state.threat_ledger,
            ability_library=ability_library,
        )
        tutorial_target.subsystems["SEC"].max_hp = 4
        tutorial_target.subsystems["SEC"].current_hp = 4
        tutorial_target.subsystems["SEC"].is_destroyed = False
        tutorial_target.subsystems["OS"].max_hp = 8
        tutorial_target.subsystems["OS"].current_hp = 8
        self.current_enemy = tutorial_target
        result = combat.start_encounter(
            tutorial_target,
            objective_callback=self.make_tutorial_objective_callback("drone"),
        )
        self.current_enemy = None

        if result.outcome != "victory":
            return False

        self.apply_objective_card(sandbox_alert_card())
        self.show_message_log(
            "prologue_heist.txt",
            prologue_heist_message(),
            "[Press Enter to breach the relay...]",
            art_key="black_ice",
        )
        self.player.unlock_black_ice_suite()
        self.update_arsenal_display(self.arsenal)

        self.show_message_log(
            "defense_notes.txt",
            defense_notes_message(),
            "[Press Enter to test those systems under pressure...]",
            art_key="black_ice",
        )

        boss_data = enemies_data.get("aegis_black_ice", enemies_data.get("omnicorp_gateway", {}))
        boss_target = Enemy(
            "aegis_black_ice",
            boss_data,
            self.state.threat_ledger,
            ability_library=ability_library,
        )
        self.current_enemy = boss_target
        combat_result = combat.start_encounter(
            boss_target,
            objective_callback=self.make_tutorial_objective_callback("black_ice"),
        )
        self.current_enemy = None

        self.apply_objective_card(sim_breach_card())
        self.show_message_log(
            "burn_notice.txt",
            burn_notice_message(),
            "[Press Enter to reboot into the live grid...]",
            art_key="burn_notice",
        )

        self.collapse_from_prologue(combat)
        self.apply_day_unlocks()
        self.update_arsenal_display(self.arsenal)
        self.clear_objective()
        self.show_message_log(
            "survival_primer.txt",
            survival_primer_message(),
            "[Press Enter to enter the grid again...]",
            art_key="survival",
        )
        print("\n[sys] Tutorial instance gone. Live grid session open.")
        print("[sys] You came here to mess around in a training sim. Now you're learning for real.")
        return combat_result.outcome in {"defeat", "victory"}

    def build_enemy_for_node(self, node, enemies_data, modifiers, ability_library):
        cached_enemy = getattr(node, "cached_enemy", None)
        if cached_enemy is not None:
            if hasattr(cached_enemy, "ensure_runtime_defaults"):
                cached_enemy.ensure_runtime_defaults()
            self.apply_pending_node_damage(node, cached_enemy)
            if cached_enemy.subsystems["OS"].current_hp <= 0:
                node.compromise_state = "bricked"
                node.locked_data = True
                node.root_access = False
                node.module_slots = 0
                node.forensic_complete = False
            return cached_enemy

        pressure = self.state.get_difficulty_pressure() if self.state and hasattr(self.state, "get_difficulty_pressure") else 1
        progression_tier = self.state.get_progression_tier() if self.state and hasattr(self.state, "get_progression_tier") else 0
        low_pressure = pressure <= 2 and progression_tier <= 1
        rng_seed = getattr(node, "spawn_seed", 0) or (self.state.make_seed("enemy", node.ip_address, node.node_type, node.difficulty) if self.state and hasattr(self.state, "make_seed") else f"{node.ip_address}:{node.node_type}:{node.difficulty}")
        rng = random.Random(rng_seed)

        template_map = {
            "civilian": (
                ["grandma_pc", "sleepy_laptop", "streamer_rig", "smart_tv_wall"],
                [None, "legacy", "backdoored", "corrupted"],
                1,
            ),
            "personal": (
                ["sleepy_laptop", "grandma_pc", "streamer_rig", "family_nas", "router_hub"],
                [None, "legacy", "backdoored", "corrupted"],
                1,
            ),
            "minecraft": (["minecraft_server", "sleepy_laptop", "family_nas"], [None, "legacy", "backdoored"], 1),
            "iot": (
                ["watcher_ipcam", "smart_fridge_mesh", "office_printer", "smart_tv_wall", "weather_station"],
                [None, "corrupted", "monitored"],
                1,
            ),
            "server": (
                ["budget_rack", "mail_spool", "office_printer", "backup_tape_library", "warehouse_plc"],
                [None, "hardened", "monitored", "corrupted"],
                1,
            ),
            "corporate": (
                ["omnicorp_gateway", "research_cluster", "mail_spool", "campus_vpn", "warehouse_plc"],
                [None, "hardened", "corrupted", "monitored"],
                1,
            ),
            "lab": (
                ["research_cluster", "sandbox_array", "backup_tape_library"],
                [None, "hardened", "monitored"],
                2,
            ),
            "relay": (
                ["mail_spool", "relay_exchange", "campus_vpn"],
                [None, "legacy", "monitored", "backdoored"],
                1,
            ),
            "media": (
                ["streamer_rig", "cdn_edge", "smart_tv_wall"],
                [None, "backdoored", "corrupted"],
                1,
            ),
            "honeypot": (
                ["omnicorp_gateway", "watcher_ipcam", "research_cluster", "campus_vpn"],
                ["monitored", "air_gapped", "hardened", "corrupted"],
                2,
            ),
            "gatekeeper": (
                ["omnicorp_gateway", "budget_rack", "watcher_ipcam", "sentinel_fabric", "research_cluster", "civic_backbone"],
                ["hardened", "monitored", "air_gapped", "corrupted"],
                2,
            ),
        }
        if low_pressure:
            template_map["personal"] = (
                ["grandma_pc", "sleepy_laptop"],
                [None],
                0,
            )
            template_map["minecraft"] = (
                ["minecraft_server"],
                [None],
                0,
            )
            template_map["gatekeeper"] = (
                ["budget_rack", "mail_spool"],
                [None],
                0,
            )
        bonus_ability_map = {
            "civilian": ["memory_spike", "packet_storm", "trace_route", "dns_maze"],
            "personal": ["memory_spike", "packet_storm", "trace_route", "sector_chew", "dns_maze"],
            "minecraft": ["miner_leech", "chunk_overflow", "sector_chew"],
            "iot": ["proxy_splitter", "lens_burn", "trace_route", "defense_breach", "packet_storm", "dns_maze"],
            "server": ["memory_spike", "patch_cycle", "trace_route", "ram_lock", "data_reaper", "defense_breach", "cache_patch", "tls_needle"],
            "corporate": ["memory_spike", "patch_cycle", "trace_route", "ram_lock", "data_reaper", "lens_burn", "defense_breach", "kernel_jab", "dns_maze", "tls_needle"],
            "lab": ["heap_shred", "memory_spike", "cache_patch", "ram_lock", "tls_needle"],
            "relay": ["dns_maze", "trace_route", "packet_storm", "proxy_splitter", "tls_needle"],
            "media": ["packet_storm", "dns_maze", "trace_route", "chunk_overflow"],
            "honeypot": ["trace_route", "ram_lock", "data_reaper", "patch_cycle", "proxy_splitter", "lens_burn", "defense_breach", "dns_maze"],
            "gatekeeper": ["trace_route", "ram_lock", "data_reaper", "patch_cycle", "proxy_splitter", "lens_burn", "memory_spike", "defense_breach", "kernel_jab", "dns_maze", "tls_needle"],
        }

        template_pool, modifier_pool, bonus_cap = template_map.get(node.node_type, (["grandma_pc"], [None], 1))
        template_key = rng.choice(template_pool)
        enemy_template = dict(enemies_data.get(template_key, {}))
        difficulty_delta = max(0, node.difficulty - 1)
        scale_map = {
            "civilian": (1, 1),
            "personal": (1, 1),
            "minecraft": (1, 0),
            "iot": (1, 1),
            "server": (2, 1),
            "corporate": (2, 1),
            "lab": (2, 1),
            "relay": (1, 1),
            "media": (1, 1),
            "honeypot": (2, 1),
            "gatekeeper": (2, 1),
        }
        os_scale, budget_scale = scale_map.get(node.node_type, (2, 1))
        if low_pressure:
            os_scale = min(os_scale, 1)
            budget_scale = 0
        if getattr(node, "lockdown_turns", 0) > 0:
            enemy_template["base_os"] = enemy_template.get("base_os", 10) + max(1, node.lockdown_turns)
            enemy_template["budget"] = enemy_template.get("budget", 0) + node.lockdown_turns
        enemy_template["base_os"] = enemy_template.get("base_os", 10) + (difficulty_delta * os_scale)
        enemy_template["budget"] = enemy_template.get("budget", 0) + (difficulty_delta * budget_scale)
        base_name = enemy_template.get("name", "Unknown Node")
        if node.node_type == "gatekeeper":
            enemy_template["name"] = f"Gatekeeper // {base_name} [{node.ip_address}]"
        else:
            enemy_template["name"] = f"{base_name} [{node.ip_address}]"

        modifier_key = rng.choice(modifier_pool) if modifier_pool else None
        if low_pressure:
            modifier_key = None
        if getattr(node, "lockdown_turns", 0) > 0 and "monitored" in modifier_pool:
            modifier_key = "monitored"
        if node.node_type == "gatekeeper" and modifier_key is None and not low_pressure:
            non_null_modifiers = [item for item in modifier_pool if item]
            if non_null_modifiers:
                modifier_key = rng.choice(non_null_modifiers)
        modifier_data = modifiers.get(modifier_key) if modifier_key else None

        ability_list = list(enemy_template.get("abilities", []))
        bonus_pool = [ability for ability in bonus_ability_map.get(node.node_type, []) if ability not in ability_list]
        if bonus_pool:
            if bonus_cap <= 0:
                bonus_count = 0
            elif node.node_type == "gatekeeper":
                bonus_count = min(len(bonus_pool), rng.randint(1, bonus_cap))
            else:
                bonus_count = min(len(bonus_pool), rng.randint(0, bonus_cap))
            if low_pressure:
                bonus_count = 0
            if bonus_count > 0:
                ability_list.extend(rng.sample(bonus_pool, bonus_count))
        enemy_template["abilities"] = ability_list

        enemy_id = f"{node.node_type}_{node.ip_address.replace('.', '_')}"
        random_state = random.getstate()
        random.seed(rng_seed)
        try:
            node.cached_enemy = Enemy(enemy_id, enemy_template, self.state.threat_ledger, modifier_data, ability_library)
        finally:
            random.setstate(random_state)
        self.apply_pending_node_damage(node, node.cached_enemy)
        if node.cached_enemy.subsystems["OS"].current_hp <= 0:
            node.compromise_state = "bricked"
            node.locked_data = True
            node.root_access = False
            node.module_slots = 0
            node.forensic_complete = False
        if self.route_sweep_level > 1 and node.node_type != "gatekeeper":
            ambient_exposure = min(65, (self.route_sweep_level - 1) * 12)
            node.cached_enemy.apply_recon_exposure(ambient_exposure)
        return node.cached_enemy

    @staticmethod
    def get_node_scan_label(enemy):
        if not enemy or not enemy.topology_revealed:
            return "HOSTILE"
        if enemy.identity_revealed:
            clean_name = enemy.get_visible_name().split("[")[0].strip().upper()
            return (clean_name[:10] or "SCANNED").ljust(10)[:10]
        return "SCANNED"

    def get_node_status_text(self, node_index, node, cleared_nodes):
        if node_index in cleared_nodes:
            if getattr(node, "revolt_state", None) and getattr(node, "root_access", False):
                return "CONTESTED"
            if getattr(node, "compromise_state", "") == "rooted":
                return "ROOTED"
            if getattr(node, "compromise_state", "") == "bricked":
                if not getattr(node, "forensic_complete", False):
                    return "FORENSIC"
                return "BRICKED"
            return "CLEARED"
        if self.map_world:
            anchor_index = self.map_active
            if anchor_index is None and self.map_world.entry_links:
                anchor_index = min(self.map_world.entry_links)
            if not self.map_world.can_traverse_from(anchor_index, node_index, cleared_nodes):
                return "LOCKED"
        if node.node_type == "shop":
            return "MARKET"
        if node.node_type == "gatekeeper":
            return "BORDER"
        if getattr(node, "compromise_state", "") == "bricked":
            return "FORENSIC" if not getattr(node, "forensic_complete", False) else "BRICKED"
        if getattr(node, "worm_level", 0) > 0:
            return "INFECTED"
        if getattr(node, "lockdown_turns", 0) > 0:
            return "LOCKDOWN"

        enemy = getattr(node, "cached_enemy", None)
        if not enemy or not enemy.topology_revealed:
            return "LIVE"

        alert_stage = enemy.get_recon_alert_stage()
        if alert_stage == 2:
            return "HOT"
        if alert_stage == 1:
            return "WARM"
        return "SCANNED"

    def build_node_intel_summary(self, node):
        enemy = getattr(node, "cached_enemy", None)
        contract_summary = self.build_contract_node_summary(node.ip_address, accepted_only=True)
        if not enemy:
            revolt_state = getattr(node, "revolt_state", None)
            if getattr(node, "compromise_state", "") == "rooted":
                base = "intel: root access retained"
                if getattr(node, "installed_module", None):
                    base += f" // {node.installed_module}"
                if revolt_state:
                    base += f" // contested by {revolt_state.get('faction', 'reclaimers')}"
                return f"{base} | {contract_summary}" if contract_summary else base
            if getattr(node, "compromise_state", "") == "bricked":
                base = "intel: forensic image open" if not getattr(node, "forensic_complete", False) else "intel: node bricked // data locked"
                return f"{base} | {contract_summary}" if contract_summary else base
            if getattr(node, "worm_level", 0) > 0:
                base = f"intel: worm pressure {node.worm_level}"
                return f"{base} | {contract_summary}" if contract_summary else base
            if getattr(node, "lockdown_turns", 0) > 0:
                base = f"intel: fresh route hardening // {node.lockdown_turns} step(s)"
                return f"{base} | {contract_summary}" if contract_summary else base
            return contract_summary

        bits = []
        revolt_state = getattr(node, "revolt_state", None)
        if getattr(node, "compromise_state", "") == "rooted":
            bits.append("root access retained")
            if getattr(node, "installed_module", None):
                bits.append(f"module {node.installed_module}")
            if revolt_state:
                bits.append(f"contested by {revolt_state.get('faction', 'reclaimers')}")
            if getattr(node, "worm_level", 0) > 0:
                bits.append(f"worm pressure {node.worm_level}")
        elif getattr(node, "compromise_state", "") == "bricked":
            bits.append("forensic image open" if not getattr(node, "forensic_complete", False) else "data image bricked")
        elif getattr(node, "worm_level", 0) > 0:
            bits.append(f"worm pressure {node.worm_level}")
        if getattr(node, "lockdown_turns", 0) > 0:
            bits.append(f"route hardening {node.lockdown_turns}")
        if enemy.identity_revealed:
            bits.append(enemy.get_visible_name().split("[")[0].strip())
        elif enemy.topology_revealed:
            bits.append("port map resolved")

        if enemy.weapon_revealed:
            bits.append(enemy.get_visible_weapon())

        telemetry_bits = []
        for key in ["OS", "SEC", "NET", "MEM", "STO"]:
            if enemy.has_telemetry_for(key):
                subsystem = enemy.subsystems[key]
                telemetry_bits.append(f"{key} {subsystem.current_hp}/{subsystem.max_hp}")

        if telemetry_bits:
            bits.append(", ".join(telemetry_bits[:2]))

        if enemy.weakness_revealed:
            bits.append(f"weak {enemy.weakness}")
        elif enemy.topology_revealed and (enemy.subsystems["SEC"].is_destroyed or enemy.security_breach_turns > 0):
            bits.append("perimeter open")

        alert_stage = enemy.get_recon_alert_stage()
        if alert_stage == 2:
            bits.append("entry hot")
        elif alert_stage == 1:
            bits.append("entry warm")

        if contract_summary:
            bits.append(contract_summary.replace("contracts: ", ""))

        if not bits:
            return None

        return "intel: " + " | ".join(bits[:4])

    def build_subnet_registry_lines(self, network, current_subnet_id):
        if not network:
            return ["[sys] No macro route mesh is loaded."]
        lines = [f"=== ROUTE REGISTRY // {network.name} ===", ""]
        for domain in network.domains.values():
            lines.append(f"[{domain.domain_id}] {domain.name}")
            lines.append(f"  {'ID':<6}{'SUBNET':<22}{'STATE':<12}{'LINKS'}")
            for subnet_id in domain.subnet_ids:
                subnet = network.get_subnet(subnet_id)
                if not subnet:
                    continue
                status = "CONQUERED" if subnet.is_conquered() else "ACTIVE"
                if subnet_id == current_subnet_id:
                    status = "CURRENT"
                neighbor_preview = ", ".join(sorted(subnet.neighbors)) or "none"
                lines.append(
                    f"  {subnet.subnet_id:<6}{subnet.subnet_name:<22}{status:<12}{neighbor_preview}"
                )
            lines.append("")
        return lines[:-1] if lines and not lines[-1] else lines

    def build_route_status_text(self, subnet):
        domain = None
        if self.map_network:
            domain = self.map_network.get_domain(subnet.domain_id)
        domain_label = domain.name if domain else subnet.domain_id
        return (
            f"{domain_label} | {subnet.subnet_id} | {subnet.subnet_name} | "
            f"sweep {subnet.sweep_level}/{subnet.sweep_max} | "
            f"foothold {subnet.world_map.nodes[subnet.current_anchor].ip_address}"
        )

    def sync_active_subnet_view(self, network, subnet):
        self.route_sweep_level = subnet.sweep_level
        self.route_sweep_max = subnet.sweep_max
        self.state.current_subnet_id = subnet.subnet_id
        self.state.current_domain_id = subnet.domain_id
        self.map_network = network
        self.set_network_world(
            subnet.world_map,
            subnet.cleared_nodes,
            subnet.current_anchor,
            status_text=self.build_route_status_text(subnet),
            network=network,
            subnet_id=subnet.subnet_id,
            domain_id=subnet.domain_id,
        )

    @staticmethod
    def subnet_is_locked_for_standard_travel(subnet):
        return not subnet.is_conquered()

    def apply_supercruise_penalty(self, network, current_subnet_id, target_subnet_id):
        path = network.shortest_path(current_subnet_id, target_subnet_id)
        if not path:
            return False, ["[sys] Supercruise failed. No route solution exists for that target."]

        current_subnet = network.get_subnet(current_subnet_id)
        target_subnet = network.get_subnet(target_subnet_id)
        distance = max(0, len(path) - 1)
        domain_cross = 1 if current_subnet.domain_id != target_subnet.domain_id else 0
        unconquered_crossings = sum(
            1
            for subnet_id in path[1:-1]
            if not network.is_subnet_conquered(subnet_id)
        )
        risk_score = distance + (domain_cross * 3) + (unconquered_crossings * 2)
        messages = [
            f"[SUPERCRUISE] path {current_subnet_id} -> {target_subnet_id} // hops {distance} // risk {risk_score}"
        ]

        trace_gain = 4 + (distance * 3) + (domain_cross * 8) + (unconquered_crossings * 4)
        self.state.trace_level += trace_gain
        messages.append(f"[SUPERCRUISE] Trace spiked by +{trace_gain}.")

        os_damage = 1 + distance + (domain_cross * 3) + unconquered_crossings
        os_core = self.player.subsystems["OS"]
        lost = min(os_core.current_hp, os_damage)
        os_core.current_hp = max(0, os_core.current_hp - lost)
        messages.append(f"[SUPERCRUISE] Tunnel turbulence shaved {lost} Core OS.")
        if os_core.current_hp <= 0:
            self.state.game_over = True
            messages.append("[SUPERCRUISE] Core process image collapsed during transit.")
            return False, messages

        ram_loss = min(self.player.current_ram, max(1, distance + domain_cross + unconquered_crossings))
        self.player.current_ram -= ram_loss
        messages.append(f"[SUPERCRUISE] Buffer desync dumped {ram_loss} RAM.")

        target_subnet.sweep_level = min(target_subnet.sweep_max, max(target_subnet.sweep_level, 1 + risk_score))
        target_subnet.supercruise_heat = max(target_subnet.supercruise_heat, risk_score)

        if risk_score >= 7 and random.random() < 0.3:
            self.state.trace_level += 6
            messages.append("[SUPERCRUISE] Border watchdog clipped the jump. You stayed in the current subnet.")
            return False, messages

        messages.append(f"[SUPERCRUISE] Jump solution held. Routed into {target_subnet.subnet_name}.")
        return True, messages

    @staticmethod
    def get_dynamic_event_config(events_data):
        return dict(events_data.get("dynamic_events", {})) if events_data else {}

    def advance_world_dynamics(self, network, events_data):
        if not network:
            return []
        return advance_dynamic_events(
            network,
            self.state,
            self.get_dynamic_event_config(events_data),
            current_subnet_id=self.state.current_subnet_id,
        )

    @staticmethod
    def apply_pending_node_damage(node, enemy):
        pending = dict(getattr(node, "pending_subsystem_damage", {}) or {})
        if not pending:
            return
        if hasattr(enemy, "ensure_runtime_defaults"):
            enemy.ensure_runtime_defaults()
        for subsystem_key, amount in pending.items():
            if amount <= 0 or subsystem_key not in enemy.subsystems:
                continue
            dealt = enemy.subsystems[subsystem_key].take_damage(amount)
            if dealt > 0 and enemy.subsystems[subsystem_key].is_destroyed and subsystem_key != "OS":
                enemy.subsystems["OS"].take_damage(2)
        node.pending_subsystem_damage = {}

    def build_revolt_enemy_for_node(self, node, enemies_data, ability_library):
        revolt_state = getattr(node, "revolt_state", None) or {}
        faction = revolt_state.get("faction", "antivirus")
        template_key = "white_hat_reclaimer" if faction == "white_hat" else "antivirus_reclaimer"
        enemy_template = dict(enemies_data.get(template_key, enemies_data.get("budget_rack", {})))
        strength = max(1, int(revolt_state.get("strength", node.difficulty + 1)))
        enemy_template["base_os"] = enemy_template.get("base_os", 12) + strength
        enemy_template["budget"] = enemy_template.get("budget", 8) + max(1, strength // 2)
        enemy_template["name"] = f"{enemy_template.get('name', 'Route Reclaimer')} [{node.ip_address}]"
        enemy = Enemy(
            f"revolt_{node.ip_address.replace('.', '_')}",
            enemy_template,
            self.state.threat_ledger,
            ability_library=ability_library,
        )
        enemy.reveal_surface()
        return enemy

    def defend_rooted_node(self, node, node_index, current_subnet, world, combat, enemies_data, ability_library, events_data):
        revolt_state = getattr(node, "revolt_state", None)
        if not revolt_state:
            self.manage_rooted_node(node, world, events_data)
            return

        faction = revolt_state.get("faction", "antivirus")
        self.clear_screen()
        print(f"[sys] Rooted shell at {node.ip_address} is under active challenge.")
        print(f"[sys] Incoming claimant: {faction}.")
        input("[Press Enter to jack into the defense feed...]")

        enemy = self.build_revolt_enemy_for_node(node, enemies_data, ability_library)
        self.current_enemy = enemy
        result = combat.start_encounter(enemy)
        self.current_enemy = None

        if self.state.game_over:
            return

        if result.outcome == "fled":
            print("[sys] You cut the defense feed. The contest on that node is still live.")
            input("[Press Enter to return to the route mesh...]")
            return

        if enemy.subsystems["OS"].current_hp > 0:
            print("[sys] The reclaiming traffic is still live on that node.")
            input("[Press Enter to return to the route mesh...]")
            return

        if result.reason == "bricked":
            mark_node_bricked(node, current_subnet, node_index, self.state, "defense")
            print("[sys] You held the line, but the rooted node was bricked in the crossfire.")
            input("[Press Enter to return to the route mesh...]")
            return

        node.revolt_state = None
        node.compromise_state = "rooted"
        node.root_access = True
        node.locked_data = False
        node.module_slots = max(1, getattr(node, "module_slots", 1))
        self.state.claim_rooted_node(node)
        print("[sys] Reclaimer traffic cleared. Root access retained.")
        input("[Press Enter to reopen the rooted shell...]")
        self.manage_rooted_node(node, world, events_data)

    def investigate_forensic_node(
        self,
        node,
        node_index,
        current_subnet,
        enemies_data,
        modifiers,
        ability_library,
        events_data,
    ):
        config = self.get_dynamic_event_config(events_data)
        self.clear_screen()
        print("=== FORENSIC NODE IMAGE ===\n")
        print(f"Target: {node.ip_address} ({node.node_type.upper()})")
        print("Status: destroyed hardware // no live hostile process remains\n")

        enemy = getattr(node, "cached_enemy", None)
        if enemy is not None and hasattr(enemy, "ensure_runtime_defaults"):
            enemy.ensure_runtime_defaults()
            enemy.reveal_surface()
            enemy.reveal_telemetry()
            print(f"Recovered chassis: {enemy.get_visible_name()}")
            print(f"Last visible countermeasure: {enemy.get_visible_weapon()}")
            print("Bus fabric:")
            for line in enemy.get_bus_report_lines()[:5]:
                print(line)
            print("")

        if not getattr(node, "forensic_complete", False):
            scrap_min = int(config.get("forensic_scrap_min", 10))
            scrap_max = int(config.get("forensic_scrap_max", 26))
            reward = random.randint(scrap_min, max(scrap_min, scrap_max))
            self.state.player_crypto += reward
            print(f"[FORENSICS] Pulled {reward} Crypto in salvageable residue.")

            reveal_cap = int(config.get("forensic_neighbor_reveal", 2))
            neighbors = list(current_subnet.world_map.links.get(node_index, set()))
            random.shuffle(neighbors)
            revealed = []
            for neighbor_index in neighbors[:reveal_cap]:
                neighbor = current_subnet.world_map.nodes[neighbor_index]
                if neighbor.node_type == "shop":
                    continue
                neighbor_enemy = self.build_enemy_for_node(neighbor, enemies_data, modifiers, ability_library)
                neighbor_enemy.reveal_surface()
                revealed.append(f"{neighbor.ip_address} -> {neighbor_enemy.get_visible_name()}")
            if revealed:
                print("[FORENSICS] Route scraps leaked neighboring identities:")
                for line in revealed:
                    print(f" - {line}")

            module_library = events_data.get("modules", {})
            salvage_chance = float(config.get("forensic_module_salvage_chance", 0.18))
            if module_library and random.random() < salvage_chance:
                module_id = random.choice(list(module_library.keys()))
                self.state.grant_module_inventory(module_id, 1)
                print(f"[FORENSICS] Salvaged module package: {module_library[module_id].get('name', module_id)}.")

            node.forensic_complete = True
        else:
            print("[FORENSICS] Crash image already archived. No fresh residue remains.")

        input("\n[Press Enter to return to the route mesh...]")

    def reward_node_clear(self, node, events_data, *, rooted: bool = False):
        node_rewards = events_data.get("nodes", {}).get(node.node_type, {})
        if not rooted:
            node.locked_data = True
            print("[!] Node bricked. Loot channels collapsed and the data image is unrecoverable.")
            return
        reward_min = node_rewards.get("reward_min", 20)
        reward_max = node_rewards.get("reward_max", reward_min)
        difficulty_bonus = node_rewards.get("difficulty_bonus", 0)

        reward = random.randint(reward_min, reward_max) + (max(0, node.difficulty - 1) * difficulty_bonus)
        self.state.player_crypto += reward
        print(f"[+] Loot secured: {reward} Crypto transferred to your wallet.")

        repair_min = node_rewards.get("repair_min", 0)
        repair_max = node_rewards.get("repair_max", repair_min)
        repair_roll = random.randint(repair_min, repair_max) if repair_max > 0 else 0

        if repair_roll > 0:
            os_core = self.player.subsystems["OS"]
            restored = min(os_core.max_hp - os_core.current_hp, repair_roll)
            if restored > 0:
                os_core.current_hp += restored
                print(f"[+] Core OS patched for {restored} integrity.")

    @staticmethod
    def classify_day_style(brute_delta: int, exploit_delta: int) -> str:
        if brute_delta <= 0 and exploit_delta <= 0:
            return "low-signature drift"
        if brute_delta >= exploit_delta * 2 and brute_delta > 0:
            return "brute-force heavy"
        if exploit_delta >= brute_delta * 2 and exploit_delta > 0:
            return "exploit-heavy"
        return "mixed intrusion profile"

    def advance_counter_sweep(self):
        if self.route_sweep_max <= 0:
            return

        self.route_sweep_level = min(self.route_sweep_max, self.route_sweep_level + 1)
        print(f"[sys] Counter-sweep advanced: {self.route_sweep_level}/{self.route_sweep_max}.")

        trace_gain = max(0, (self.route_sweep_level - 2) * 2)
        if trace_gain > 0:
            self.state.trace_level += trace_gain
            print(f"[sys] Sweep pressure added +{trace_gain} Trace.")

        if self.route_sweep_level >= self.route_sweep_max:
            print("[sys] Hunter net is closing. Future breaches will start warm.")

    def play_day_transition(
        self,
        completed_day: int,
        next_day: int,
        world,
        cleared_count: int,
        day_start_crypto: int,
        day_start_trace: int,
        day_start_brute: int,
        day_start_exploit: int,
    ):
        crypto_gain = self.state.player_crypto - day_start_crypto
        current_trace = self.state.trace_level
        trace_delta = current_trace - day_start_trace
        brute_delta = self.state.threat_ledger.brute_force_noise - day_start_brute
        exploit_delta = self.state.threat_ledger.exploit_noise - day_start_exploit
        style_label = self.classify_day_style(brute_delta, exploit_delta)
        effective_ram = self.player.get_effective_max_ram()

        self.clear_screen()
        self.apply_objective_card(day_wrap_card(completed_day))
        print("\n" + "=" * 58)
        print(f"                DAY {completed_day} // SESSION WRAP")
        print("=" * 58 + "\n")
        time.sleep(0.4)
        print(f"[+] Gatekeeper tunnel broken. {world.subnet_name} is behind you now.")
        time.sleep(0.5)
        print(f"[+] Nodes resolved: {cleared_count}/{len(world.nodes)}")
        print(f"[+] Crypto secured today: +{crypto_gain}")
        if trace_delta >= 0:
            print(f"[+] Trace movement before scrub: +{trace_delta}")
        else:
            print(f"[+] Trace movement before scrub: {trace_delta}")
        print(f"[+] Noise logged: BF +{brute_delta} | EX +{exploit_delta} | style {style_label}")
        print(
            f"[+] Rig status: OS {self.player.subsystems['OS'].current_hp}/{self.player.subsystems['OS'].max_hp} | "
            f"RAM {self.player.current_ram}/{effective_ram} | bots {len(self.player.support_bots)}"
        )
        input("\n[Press Enter to sync the ledger...]")

        self.clear_screen()
        print("root@burner:~$ sync --ledger --compress")
        time.sleep(0.5)
        print("[sys] Contract residue archived.")
        time.sleep(0.4)
        print("[sys] Wallet mirrored into cold storage.")
        time.sleep(0.4)
        print("[sys] Route history salted and burned.")
        time.sleep(0.5)
        print("\nroot@burner:~$ logout")
        time.sleep(0.5)
        print("[sys] Session ghosted. Rolling keys for the next subnet...")
        time.sleep(0.7)
        unlock_lines = self.apply_day_unlocks()
        for line in unlock_lines:
            print(line)
            time.sleep(0.3)
        print(f"[sys] Trace scrub complete. Gatekeeper fallout shaved 10 off the heat. Current Trace: {current_trace}")
        time.sleep(0.6)
        print(f"[sys] Day {next_day} link window opening now.")
        input("\n[Press Enter to jack into the next day...]")

    def visit_shop(self, events_data):
        consumable_library = events_data.get("consumables", {})
        module_library = events_data.get("modules", {})
        shop_stock = self.build_shop_stock(events_data)
        if not shop_stock:
            print("[sys] Black market relay offline. No goods available.")
            input("[Press Enter to return to the subnet map...]")
            return

        self.set_shop_databank(shop_stock, consumable_library, module_library)
        try:
            while True:
                self.clear_screen()
                print("=== BLACK MARKET RELAY ===\n")
                print(f"Wallet: {self.state.player_crypto} Crypto")
                print(f"Trace:  {self.state.trace_level}\n")
                if self.state.module_inventory:
                    module_stock = ", ".join(
                        f"{module_id}x{count}" for module_id, count in sorted(self.state.module_inventory.items())
                    )
                    print(f"Cached module stock: {module_stock}\n")

                for idx, offer in enumerate(shop_stock, start=1):
                    stock_kind = offer.get("stock_kind", offer.get("type", "unknown"))
                    amount = offer.get("amount", 0)
                    title = offer.get(
                        "name",
                        offer.get("item_id", offer.get("script_id", offer.get("flag_id", offer.get("module_id", offer.get("offer_id", "offer"))))),
                    )
                    if stock_kind == "script":
                        script_id = offer.get("script_id", title)
                        script_data = self.arsenal.scripts.get(script_id, {}) if self.arsenal else {}
                        desc = f"{script_data.get('type', 'script').replace('_', '-')} | {script_data.get('ram', 0)} RAM"
                    elif stock_kind == "flag":
                        flag_id = offer.get("flag_id", title)
                        flag_data = self.arsenal.flags.get(flag_id, {}) if self.arsenal else {}
                        desc = f"modifier | +{flag_data.get('ram', 0)} RAM"
                    elif stock_kind == "heal":
                        desc = f"Restore {amount} Core OS"
                    elif stock_kind == "ram":
                        desc = f"+{amount} Max RAM permanently"
                    elif stock_kind == "trace":
                        desc = f"Reduce Trace by {amount}"
                    elif stock_kind == "bot":
                        desc = (
                            f"Support bot ({offer.get('ram_reservation', 1)} RAM reserved, "
                            f"{offer.get('script_ram_cap', 2)} RAM cap)"
                        )
                    elif stock_kind == "consumable":
                        item_ref = consumable_library.get(offer.get("item_id", ""), {})
                        qty = offer.get("quantity", 1)
                        desc = f"{item_ref.get('name', offer.get('item_id', title))} x{qty}"
                    elif stock_kind == "module":
                        module_ref = module_library.get(offer.get("module_id", ""), {})
                        qty = offer.get("quantity", 1)
                        desc = f"{module_ref.get('name', offer.get('module_id', title))} x{qty}"
                    else:
                        desc = "Unknown payload"

                    print(f"[{idx}] {title} | {offer.get('cost', 0)} Crypto | {desc}")

                disconnect_idx = len(shop_stock) + 1
                print(f"\n[{disconnect_idx}] Disconnect from relay")
                choice = input("Select a purchase: ").strip()

                if choice == str(disconnect_idx):
                    return

                if not choice.isdigit() or not (1 <= int(choice) <= len(shop_stock)):
                    print("[sys] Invalid purchase order. Try again.")
                    time.sleep(0.8)
                    continue

                selected_index = int(choice) - 1
                offer = shop_stock[selected_index]
                cost = offer.get("cost", 0)
                if self.state.player_crypto < cost:
                    print("[sys] Insufficient Crypto for that transaction.")
                    time.sleep(0.8)
                    continue

                self.state.player_crypto -= cost
                stock_kind = offer.get("stock_kind", offer.get("type", "unknown"))
                amount = offer.get("amount", 0)
                purchase_ok = True

                if stock_kind == "script":
                    script_id = offer.get("script_id")
                    if not self.arsenal or script_id not in self.arsenal.scripts:
                        purchase_ok = False
                    else:
                        self.player.grant_script(script_id)
                        script_data = self.arsenal.scripts.get(script_id, {})
                        print(f"[+] Installed {script_id}. {script_data.get('description', '').strip()}")
                elif stock_kind == "flag":
                    flag_id = offer.get("flag_id")
                    if not self.arsenal or flag_id not in self.arsenal.flags:
                        purchase_ok = False
                    else:
                        self.player.grant_flag(flag_id)
                        flag_data = self.arsenal.flags.get(flag_id, {})
                        print(f"[+] Installed {flag_id}. {flag_data.get('description', '').strip()}")
                elif stock_kind == "heal":
                    os_core = self.player.subsystems["OS"]
                    restored = min(os_core.max_hp - os_core.current_hp, amount)
                    os_core.current_hp += restored
                    print(f"[+] Applied {offer.get('name', offer.get('offer_id', 'patch'))}. Restored {restored} Core OS.")
                elif stock_kind == "ram":
                    self.player.max_ram += amount
                    self.player.current_ram = self.player.max_ram
                    print(f"[+] Overclock stable. Max RAM increased to {self.player.max_ram} GB.")
                elif stock_kind == "trace":
                    old_trace = self.state.trace_level
                    self.state.trace_level = max(0, self.state.trace_level - amount)
                    removed = old_trace - self.state.trace_level
                    print(f"[+] Trace scrub complete. Reduced Trace by {removed}.")
                elif stock_kind == "bot":
                    bot = self.player.install_support_bot(
                        name=offer.get("name", offer.get("offer_id", "bot")),
                        ram_reservation=offer.get("ram_reservation", 1),
                        script_ram_cap=offer.get("script_ram_cap", 2),
                        cadence=offer.get("cadence", 2),
                    )
                    print(
                        f"[+] {bot.name} installed. It reserves {bot.ram_reservation} RAM and can run "
                        f"payloads up to {bot.script_ram_cap} RAM every {bot.cadence} turns."
                    )
                    print("[sys] Support bot installed. Payload bay is idle until configured.")
                elif stock_kind == "consumable":
                    item_ref = offer.get("item_id")
                    qty = offer.get("quantity", 1)
                    if item_ref not in consumable_library:
                        purchase_ok = False
                    else:
                        self.player.grant_consumable(item_ref, qty)
                        label = consumable_library[item_ref].get("name", item_ref)
                        print(f"[+] Stocked {label} x{qty}.")
                elif stock_kind == "module":
                    module_id = offer.get("module_id")
                    qty = offer.get("quantity", 1)
                    if module_id not in module_library:
                        purchase_ok = False
                    else:
                        self.state.grant_module_inventory(module_id, qty)
                        label = module_library[module_id].get("name", module_id)
                        print(f"[+] Cached {label} x{qty}. Install it from a rooted node shell.")
                else:
                    purchase_ok = False

                if not purchase_ok:
                    self.state.player_crypto += cost
                    print("[sys] Vendor payload corrupted. Refunding transaction.")
                else:
                    shop_stock.pop(selected_index)
                    self.checkpoint_progress()

                if shop_stock:
                    self.set_shop_databank(shop_stock, consumable_library, module_library)
                else:
                    self.clear_shop_databank()
                    print("[sys] Relay inventory exhausted.")
                    time.sleep(1.0)
                    return
                time.sleep(1.0)
        finally:
            self.clear_shop_databank()

    def manage_rooted_node(self, node, world, events_data):
        module_library = events_data.get("modules", {})
        if not node.root_access:
            print("[sys] This node is resolved but offers no retained shell access.")
            input("[Press Enter to return to the route mesh...]")
            return

        self.state.claim_rooted_node(node)
        while True:
            self.clear_screen()
            print("=== ROOTED NODE SHELL ===\n")
            print(f"Node:   {node.ip_address} ({node.node_type.upper()})")
            print(f"Subnet: {world.subnet_name}")
            print(f"Flags:  {', '.join(node.map_flags) if node.map_flags else 'none'}")
            print(f"Slot:   {node.installed_module or 'open'} / {node.module_slots}\n")

            if node.installed_module:
                module_data = module_library.get(node.installed_module, {})
                print(f"Installed: {module_data.get('name', node.installed_module)}")
                print(f"          {module_data.get('description', 'No module notes loaded.')}\n")
            else:
                print("Installed: none\n")

            if self.state.module_inventory:
                print("Module inventory:")
                for idx, (module_id, count) in enumerate(sorted(self.state.module_inventory.items()), start=1):
                    module_data = module_library.get(module_id, {})
                    print(
                        f"[{idx}] {module_data.get('name', module_id)} x{count} | "
                        f"{module_data.get('description', 'No notes loaded.')}"
                    )
                print("")
            else:
                print("Module inventory: empty\n")

            print("[A] Hop here")
            print("[X] Return to route mesh")
            choice = input("Install module #: ").strip().lower()

            if choice in {"x", ""}:
                return
            if choice == "a":
                print(f"[sys] Hop pinned to {node.ip_address}.")
                time.sleep(0.8)
                return
            if not choice.isdigit():
                print("[sys] Invalid module order.")
                time.sleep(0.8)
                continue

            inventory_items = sorted(self.state.module_inventory.items())
            index = int(choice) - 1
            if not (0 <= index < len(inventory_items)):
                print("[sys] Invalid module order.")
                time.sleep(0.8)
                continue

            module_id, _count = inventory_items[index]
            success, message = self.state.install_module_on_node(node, module_id)
            print(f"[sys] {message}")
            if success:
                self.checkpoint_progress()
            time.sleep(1.0)

    def configure_single_support_bot(self, bot):
        while True:
            self.clear_screen()
            print("=== SUPPORT BOT CONFIG ===\n")
            print(f"Bot:          {bot.name}")
            print(f"Reserved RAM: {bot.ram_reservation}")
            print(f"Payload Cap:  {bot.script_ram_cap} RAM")
            print(f"Cadence:      every {bot.cadence} turn(s)")
            print(f"Payload:      {bot.payload or 'STANDBY'}\n")
            print("Choose a script. Beginner bots only accept payloads within their RAM cap.\n")
            print("[0] Put bot on standby")

            script_options = []
            for script_name, script_data in sorted(self.arsenal.scripts.items()):
                if self.player and not self.player.owns_script(script_name):
                    continue
                if script_data.get("ram", 0) <= bot.script_ram_cap:
                    script_options.append((script_name, script_data))

            for idx, (script_name, script_data) in enumerate(script_options, start=1):
                suffix = " | targetable" if script_data.get("supports_target", True) else ""
                print(f"[{idx}] {script_name:<10} | {script_data.get('ram', 0)} RAM{suffix}")

            print("\n[X] Return to bot bay")
            choice = input("Select payload: ").strip().lower()

            if choice in {"x", ""}:
                return

            if choice == "0":
                bot.payload = None
                print("[+] Bot set to standby.")
                time.sleep(0.8)
                continue

            if not choice.isdigit() or not (1 <= int(choice) <= len(script_options)):
                print("[sys] Invalid payload selection.")
                time.sleep(0.8)
                continue

            script_name, script_data = script_options[int(choice) - 1]
            payload = script_name
            if script_data.get("supports_target", True):
                default_target = script_data.get("default_target")
                target_hint = default_target if default_target else "none"
                target = input(f"Target subsystem [OS/SEC/NET/MEM/STO] (blank = {target_hint}): ").strip().upper()
                if target:
                    if target not in {"OS", "SEC", "NET", "MEM", "STO"}:
                        print("[sys] Invalid target subsystem.")
                        time.sleep(0.8)
                        continue
                    payload = f"{script_name} -target {target}"
                elif default_target:
                    payload = f"{script_name} -target {default_target.upper()}"

            cadence_input = input(f"Run cadence in turns (1-4, blank keeps {bot.cadence}): ").strip()
            new_cadence = bot.cadence
            if cadence_input:
                if not cadence_input.isdigit():
                    print("[sys] Cadence must be a number.")
                    time.sleep(0.8)
                    continue
                new_cadence = clamp(int(cadence_input), 1, 4)

            try:
                command_cost = self.arsenal.get_command_cost(payload, owner=self.player)
            except ValueError as exc:
                print(f"[sys] Invalid payload: {exc}")
                time.sleep(1.0)
                continue

            if command_cost > bot.script_ram_cap:
                print(
                    f"[sys] Payload too heavy. Bot cap is {bot.script_ram_cap} RAM, "
                    f"but this loadout needs {command_cost}."
                )
                time.sleep(1.0)
                continue

            bot.payload = payload
            bot.cadence = new_cadence
            print(f"[+] {bot.name} rewired: {bot.payload} every {bot.cadence} turn(s).")
            time.sleep(0.9)

    def configure_support_bots(self):
        if not self.player.support_bots:
            print("[sys] Bot bay empty. Buy a helper chassis from a market relay first.")
            input("[Press Enter to return to the subnet map...]")
            return

        while True:
            self.clear_screen()
            print("=== SUPPORT BOT BAY ===\n")
            print("Bots reserve RAM permanently, then execute after your queue on their cadence.\n")
            for idx, bot in enumerate(self.player.support_bots, start=1):
                payload = bot.payload or "STANDBY"
                print(
                    f"[{idx}] {bot.name} | reserve {bot.ram_reservation} RAM | "
                    f"cap {bot.script_ram_cap} RAM | every {bot.cadence} turn(s)"
                )
                print(f"    payload: {payload}")

            print("\n[X] Return to subnet map")
            choice = input("Select bot to configure: ").strip().lower()
            if choice in {"x", ""}:
                return
            if not choice.isdigit() or not (1 <= int(choice) <= len(self.player.support_bots)):
                print("[sys] Invalid bot selection.")
                time.sleep(0.8)
                continue
            self.configure_single_support_bot(self.player.support_bots[int(choice) - 1])

    def run_precombat_recon(self, node, enemy, combat):
        history = list(getattr(node, "recon_log", []))
        self.apply_objective_card(prebreach_recon_card())
        combat.turn_phase = "recon"
        soft_engaged = False

        while True:
            self.clear_screen()
            print(f"[sys] Passive tap locked on {node.ip_address}.")
            print("Passive collection is live. Every successful scrape adds exposure.\n")
            enemy.print_status()
            print(f"[LINK EXPOSURE] {enemy.recon_exposure} | {enemy.get_recon_alert_text()}")

            if history:
                print("\n[RECON LOG]")
                for line in history[-4:]:
                    print(line)

            choice = input("recon@link:~$ ").strip()
            if not choice:
                continue

            lowered = choice.lower()
            if lowered == "engage":
                node.recon_log = history[-8:]
                return "engage"

            if lowered in {"soft", "soft engage", "soft-engage"}:
                if soft_engaged:
                    print("\n[sys] Soft engage already burned on this link. Keep scouting or commit the breach.")
                    input("[Press Enter to continue recon...]")
                    continue
                survived, intel_lines = combat.run_soft_engage(enemy)
                soft_engaged = True
                history.append("[soft] opening response recorded")
                for line in intel_lines:
                    history.append(f"[soft] {line}")
                node.recon_log = history[-8:]
                if not survived or self.state.game_over:
                    return "downed"
                continue

            if lowered in {"abort", "back", "disconnect", "exit"}:
                self.clear_objective()
                node.recon_log = history[-8:]
                return "abort"

            success, message, alert_stage = combat.execute_recon_action(choice, enemy)
            print(f"\n{message}")
            if success:
                history.append(strip_ansi(message))
                node.recon_log = history[-8:]

            if alert_stage == 1:
                print("[!] COUNTER-SCAN: the host has a rough map of your node now.")
                history.append("[!] COUNTER-SCAN: host mapped your topology.")
                node.recon_log = history[-8:]
            elif alert_stage == 2:
                print("[!] COUNTER-SCAN: your signature leaked. This breach is now hot.")
                history.append("[!] COUNTER-SCAN: signature leaked.")
                node.recon_log = history[-8:]

            input("[Press Enter to continue recon...]")

    def run_cleanup_phase(self, node, enemy, result, events_data):
        scrubbed = False
        forensic_ready = node.compromise_state == "bricked" and not getattr(node, "forensic_complete", False)
        self.apply_objective_card(cleanup_card(node.root_access, forensic_ready))

        while True:
            forensic_ready = node.compromise_state == "bricked" and not getattr(node, "forensic_complete", False)
            self.apply_objective_card(cleanup_card(node.root_access, forensic_ready))
            self.clear_screen()
            print("=== PHASE 3 // CLEANUP ===\n")
            print(f"Node: {node.ip_address}")
            print(f"State: {node.compromise_state.upper()}   Trace: {self.state.trace_level}   Crypto: {self.state.player_crypto}")
            if node.root_access:
                print("Route flags held. The shell image stayed stable and one module slot is reserved here.")
            else:
                print("Crash image is cold. Loot channels are gone, but residue can still be worked for forensics.")
            print("")
            print("[status]   Review the link state again.")
            if not scrubbed and self.state.trace_level > 0:
                print("[scrub]    Burn residual telemetry and shave trace.")
            if forensic_ready:
                print("[forensics] Work the crash image before leaving.")
            print("[done]     Return to the route mesh.")

            choice = input("cleanup@node:~$ ").strip().lower()
            if not choice:
                continue

            if choice == "status":
                self.clear_screen()
                print("=== CLEANUP STATUS ===\n")
                print(f"Node: {node.ip_address}")
                print(f"Resolution: {result.reason.upper() if result.reason else node.compromise_state.upper()}")
                print(f"Trace: {self.state.trace_level}")
                if enemy:
                    print(f"Host alert memory: {enemy.get_recon_alert_text()}")
                    adaptation = enemy.get_adaptation_summary()
                    print(f"Host patches: {adaptation if adaptation else 'none observed'}")
                print(f"Forensic image: {'open' if forensic_ready else 'cold'}")
                input("\n[Press Enter to return to cleanup...]")
                continue

            if choice == "scrub":
                if scrubbed:
                    print("\n[sys] Cleanup scrub already spent on this node.")
                    input("[Press Enter to continue cleanup...]")
                    continue
                if self.state.trace_level <= 0:
                    print("\n[sys] Trace is already at zero.")
                    input("[Press Enter to continue cleanup...]")
                    continue
                scrub_amount = min(self.state.trace_level, 2 + max(1, node.difficulty) + (1 if node.root_access else 0))
                self.state.trace_level = max(0, self.state.trace_level - scrub_amount)
                scrubbed = True
                print(f"\n[SCRUB] Residual route noise burned off. Trace reduced by {scrub_amount}.")
                input("[Press Enter to continue cleanup...]")
                continue

            if choice == "forensics" and forensic_ready:
                self.investigate_forensic_node(node, events_data)
                continue

            if choice in {"done", "exit", "leave"}:
                self.clear_objective()
                return

            print("\n[sys] Cleanup command not recognized on this node.")
            input("[Press Enter to continue cleanup...]")

    def resolve_world_node(
        self,
        node,
        combat,
        enemies_data,
        modifiers,
        ability_library,
        events_data,
        day_summary=None,
        cleared_count_before=0,
        skip_recon=False,
    ):
        self.clear_screen()
        print(f"[sys] Routing to {node.ip_address}...")
        time.sleep(0.6)

        if node.node_type == "shop":
            self.visit_shop(events_data)
            return True, False

        enemy = self.current_enemy if skip_recon and self.current_enemy else self.build_enemy_for_node(node, enemies_data, modifiers, ability_library)
        self.current_enemy = enemy
        if not skip_recon:
            recon_result = self.run_precombat_recon(node, enemy, combat)
            if recon_result == "downed":
                self.current_enemy = None
                return False, False
            if recon_result != "engage":
                self.current_enemy = None
                print("\n[sys] Link cut before breach. Node remains unresolved.")
                input("[Press Enter to return to the subnet map...]")
                return False, False

        breach_alert_stage = enemy.get_recon_alert_stage()
        self.apply_objective_card(live_combat_card())
        result = combat.start_encounter(enemy)
        self.current_enemy = None

        if self.state.game_over:
            return False, False

        if result.outcome == "fled":
            print("\n[sys] You escaped the node, but the route is still active.")
            input("[Press Enter to return to the subnet map...]")
            return False, False

        if enemy.subsystems["OS"].current_hp > 0:
            print("\n[sys] Connection severed before the target was neutralized. Node remains active.")
            input("[Press Enter to return to the subnet map...]")
            return False, False

        node.compromise_state = "rooted" if result.reason == "rooted" else "bricked"
        node.root_access = node.compromise_state == "rooted"
        node.locked_data = node.compromise_state == "bricked"
        node.module_slots = 1 if node.root_access else 0
        node.forensic_complete = False if node.compromise_state == "bricked" else getattr(node, "forensic_complete", False)
        node.revolt_state = None if node.root_access else getattr(node, "revolt_state", None)
        node.map_flags = ["route-anchor", "root-shell"] if node.root_access else []
        if node.root_access:
            self.state.claim_rooted_node(node)

        worm_seed = int((result.metadata or {}).get("worm_seed", 0))
        if worm_seed > 0:
            seed_worm(node, worm_seed, source=(result.metadata or {}).get("worm_source"))
            print(f"[WORM] Residual traffic escaped the kill chain and seeded {node.ip_address}.")

        encounter_report = {
            "entry_alert_stage": breach_alert_stage,
            "signature_revealed": enemy.player_signature_revealed,
            "topology_revealed": enemy.topology_revealed,
            "telemetry_count": len(enemy.telemetry_targets),
            "sto_destroyed": enemy.subsystems["STO"].is_destroyed,
            "sec_destroyed": enemy.subsystems["SEC"].is_destroyed,
            "resolution": node.compromise_state,
            "worm_seed": worm_seed,
        }
        self.reward_node_clear(node, events_data, rooted=node.root_access)
        if node.root_access:
            print("[+] Root access retained. Route flags and one module slot reserved on the node shell.")
        else:
            print("[!] Bricked node logged. Route unlock remains, and the hardware corpse can be revisited for forensics.")
        contract_messages = self.state.resolve_contracts_for_node(node, enemy, encounter_report)
        for message in contract_messages:
            print(message)
        self.run_cleanup_phase(node, enemy, result, events_data)
        self.active_tap_node_index = None

        if node.node_type == "gatekeeper":
            print("\n[sys] Gatekeeper neutralized. Border controls for this subnet are open once the rest of the mesh is under control.")
            input("[Press Enter to return to the subnet map...]")
            return True, False

        input("[Press Enter to return to the subnet map...]")
        return True, False

    def run_world_cycle(self, combat, game_data):
        from world_gen import WorldGenerator

        enemies_data = game_data.get("enemies", {}).get("enemies", {})
        modifiers = game_data.get("enemies", {}).get("modifiers", {})
        ability_library = game_data.get("enemies", {}).get("abilities", {})
        events_data = game_data.get("events", {})

        while not self.state.game_over and self.running and not self.return_to_menu_requested:
            network = self.state.active_network
            if not network or getattr(network, "day", None) != self.state.day:
                network = WorldGenerator.create_network(self.state)
                if hasattr(network, "ensure_runtime_defaults"):
                    network.ensure_runtime_defaults()
                self.state.active_network = network
                self.state.current_subnet_id = network.entry_subnet_id
                self.active_tap_node_index = None
                self.current_enemy = None
                entry_subnet = network.get_subnet(network.entry_subnet_id)
                self.state.current_domain_id = entry_subnet.domain_id if entry_subnet else None
                world_tick_messages = self.state.issue_world_contracts(
                    entry_subnet.world_map if entry_subnet else None,
                    subnet_key=network.entry_subnet_id,
                )
                self.checkpoint_progress()
            else:
                if hasattr(network, "ensure_runtime_defaults"):
                    network.ensure_runtime_defaults()
                current_subnet = network.get_subnet(self.state.current_subnet_id or network.entry_subnet_id)
                if current_subnet:
                    self.state.bind_contract_inbox(current_subnet.subnet_id, current_subnet.world_map)
                world_tick_messages = []

            day_summary = {
                "world": network.get_subnet(self.state.current_subnet_id or network.entry_subnet_id).world_map,
                "crypto": self.state.player_crypto,
                "trace": self.state.trace_level,
                "brute": self.state.threat_ledger.brute_force_noise,
                "exploit": self.state.threat_ledger.exploit_noise,
            }
            self.clear_objective()

            while not self.state.game_over and self.running and not self.return_to_menu_requested:
                current_subnet = network.get_subnet(self.state.current_subnet_id or network.entry_subnet_id)
                if not current_subnet:
                    self.state.active_network = None
                    break
                world = current_subnet.world_map
                cleared_nodes = current_subnet.cleared_nodes
                current_anchor = current_subnet.current_anchor
                domain = network.get_domain(current_subnet.domain_id)
                self.sync_active_subnet_view(network, current_subnet)
                self.clear_objective()
                self.sync_active_subnet_view(network, current_subnet)
                tap_index, tap_node, tap_enemy = self.get_active_tap_context(
                    current_subnet,
                    enemies_data=enemies_data,
                    modifiers=modifiers,
                    ability_library=ability_library,
                )
                if tap_node and tap_enemy:
                    self.apply_objective_card(node_tap_card(tap_node.ip_address, tap_enemy.get_recon_alert_text()))
                else:
                    self.current_enemy = None

                self.clear_screen()
                print(
                    f"\n=== CONNECTED TO: {world.subnet_name} | {current_subnet.subnet_id} | "
                    f"{domain.name if domain else current_subnet.domain_id} | DAY {self.state.day} ===\n"
                )
                print(
                    f"Wallet: {self.state.player_crypto} Crypto   "
                    f"Trace: {self.state.trace_level}   "
                    f"Noise: BF {self.state.threat_ledger.brute_force_noise} / EX {self.state.threat_ledger.exploit_noise}   "
                    f"Sweep: {current_subnet.sweep_level}/{current_subnet.sweep_max}"
                )
                print(f"Foothold: {world.nodes[current_anchor].ip_address}")
                if tap_node and tap_enemy:
                    print(
                        f"Tap: {tap_node.ip_address}   "
                        f"Link: {tap_enemy.get_recon_alert_text()}   "
                        f"Exposure: {tap_enemy.recon_exposure}"
                    )
                print("")
                if self.has_standard_travel_unlock():
                    neighbors = sorted(network.neighboring_subnet_ids(current_subnet.subnet_id))
                    if neighbors:
                        print("[ADJACENT SUBNETS]")
                        print(f"{'ID':<6}{'SUBNET':<22}{'DOMAIN':<20}{'STATE':<12}")
                        for subnet_id in neighbors:
                            subnet = network.get_subnet(subnet_id)
                            domain_label = network.get_domain(subnet.domain_id).name if network.get_domain(subnet.domain_id) else subnet.domain_id
                            status = "SEALED"
                            if current_subnet.is_conquered():
                                status = "OPEN"
                            if subnet.is_conquered():
                                status = "CONQUERED"
                            print(f"{subnet.subnet_id:<6}{subnet.subnet_name:<22}{domain_label:<20}{status:<12}")
                        print("")
                if world_tick_messages:
                    for message in world_tick_messages:
                        print(message)
                    print("")
                    world_tick_messages = []

                type_labels = {
                    "personal": "PERSONAL",
                    "minecraft": "MINECRAFT",
                    "iot": "IPCAM",
                    "server": "SERVER",
                    "corporate": "CORP",
                    "lab": "LAB",
                    "relay": "RELAY",
                    "media": "MEDIA",
                    "honeypot": "HONEYPOT",
                    "shop": "MARKET",
                    "gatekeeper": "BORDER",
                    "civilian": "CIVILIAN",
                }

                for idx, node in enumerate(world.nodes, start=1):
                    node_index = idx - 1
                    if node_index in cleared_nodes:
                        status = self.get_node_status_text(node_index, node, cleared_nodes)
                        label = type_labels.get(node.node_type, node.node_type.upper())
                        if getattr(node, "compromise_state", "") == "rooted":
                            label = "ROOT"
                        elif getattr(node, "compromise_state", "") == "bricked":
                            label = "FORENSIC" if not getattr(node, "forensic_complete", False) else "BRICK"
                        intel_line = self.build_node_intel_summary(node)
                    elif node.node_type == "shop":
                        status = "MARKET"
                        label = type_labels.get(node.node_type, node.node_type.upper())
                        intel_line = "intel: neutral relay | black market access"
                    elif node.node_type == "gatekeeper":
                        status = self.get_node_status_text(node_index, node, cleared_nodes)
                        label = self.get_node_scan_label(getattr(node, "cached_enemy", None))
                        if label.strip() == "HOSTILE":
                            label = type_labels.get(node.node_type, node.node_type.upper())
                        intel_line = self.build_node_intel_summary(node)
                    else:
                        status = self.get_node_status_text(node_index, node, cleared_nodes)
                        label = self.get_node_scan_label(getattr(node, "cached_enemy", None))
                        intel_line = self.build_node_intel_summary(node)

                    print(f"{node.ip_address:<15} | {label:<10} | DIFF {node.difficulty:<2} | {status}")
                    if intel_line:
                        print(f"    {intel_line}")

                print("\n[BOT] Configure support bots")
                print("[MAIL] Review dead-drop inbox")
                if self.has_standard_travel_unlock():
                    print("[SUBNETS] Open route registry")
                print("[S] Save and disconnect")
                prompt = f"hop@{tap_node.ip_address}:~$ " if tap_node else "Select node IP or route command: "
                choice = input(prompt).strip().lower()

                if choice == "bot":
                    self.configure_support_bots()
                    continue

                if choice == "mail":
                    self.view_contract_inbox(world)
                    continue

                if choice == "subnets":
                    if not self.has_standard_travel_unlock():
                        print("[sys] Unknown command.")
                        time.sleep(0.8)
                        continue
                    self.clear_screen()
                    for line in self.build_subnet_registry_lines(network, current_subnet.subnet_id):
                        print(line)
                    input("\n[Press Enter to return to the route mesh...]")
                    continue

                if choice.startswith("travel "):
                    if not self.has_standard_travel_unlock():
                        print("[sys] Unknown command.")
                        time.sleep(0.8)
                        continue
                    target_token = choice.split(None, 1)[1].strip()
                    target_subnet_id = network.resolve_subnet_target(target_token, current_subnet.subnet_id)
                    if not target_subnet_id or target_subnet_id == current_subnet.subnet_id:
                        print("[sys] Travel target invalid.")
                        time.sleep(0.8)
                        continue
                    if target_subnet_id not in current_subnet.neighbors:
                        print("[sys] Travel target invalid.")
                        time.sleep(1.0)
                        continue
                    if self.subnet_is_locked_for_standard_travel(current_subnet):
                        print("[sys] Border lock active.")
                        time.sleep(1.0)
                        continue
                    self.state.current_subnet_id = target_subnet_id
                    self.active_tap_node_index = None
                    self.current_enemy = None
                    target_subnet = network.get_subnet(target_subnet_id)
                    self.state.current_domain_id = target_subnet.domain_id
                    self.state.bind_contract_inbox(target_subnet.subnet_id, target_subnet.world_map)
                    world_tick_messages = [f"[TRANSIT] Routed into {target_subnet.subnet_name} via standard border hop."]
                    world_tick_messages.extend(self.advance_world_dynamics(network, events_data))
                    self.checkpoint_progress()
                    continue

                if choice.startswith("supercruise "):
                    if not self.has_supercruise_unlock():
                        print("[sys] Unknown command.")
                        time.sleep(0.8)
                        continue
                    target_token = choice.split(None, 1)[1].strip()
                    target_subnet_id = network.resolve_subnet_target(target_token, current_subnet.subnet_id)
                    if not target_subnet_id or target_subnet_id == current_subnet.subnet_id:
                        print("[sys] Supercruise target invalid.")
                        time.sleep(0.8)
                        continue
                    jump_success, jump_messages = self.apply_supercruise_penalty(
                        network,
                        current_subnet.subnet_id,
                        target_subnet_id,
                    )
                    world_tick_messages = jump_messages
                    if jump_success:
                        self.state.current_subnet_id = target_subnet_id
                        self.active_tap_node_index = None
                        self.current_enemy = None
                        target_subnet = network.get_subnet(target_subnet_id)
                        self.state.current_domain_id = target_subnet.domain_id
                        self.state.bind_contract_inbox(target_subnet.subnet_id, target_subnet.world_map)
                    world_tick_messages.extend(self.advance_world_dynamics(network, events_data))
                    self.checkpoint_progress()
                    continue

                if choice == "s":
                    self.save_progress()
                    self.shutdown_game()
                    return

                if tap_node and tap_enemy:
                    if choice in {"leave", "back", "disconnect", "exit"}:
                        self.active_tap_node_index = None
                        self.current_enemy = None
                        continue

                    if choice == "recon":
                        self.clear_screen()
                        print(f"[sys] Passive tap active on {tap_node.ip_address}.\n")
                        tap_enemy.print_status()
                        print(f"\n[LINK STATE] {tap_enemy.get_recon_alert_text()} | exposure {tap_enemy.recon_exposure}")
                        tap_history = list(getattr(tap_node, "recon_log", []))
                        if tap_history:
                            print("\n[READBACK]")
                            for line in tap_history[-6:]:
                                print(line)
                        input("\n[Press Enter to return to the live hop...]")
                        continue

                    if choice == "engage":
                        node_cleared, _advanced_day = self.resolve_world_node(
                            tap_node,
                            combat,
                            enemies_data,
                            modifiers,
                            ability_library,
                            events_data,
                            day_summary=day_summary,
                            cleared_count_before=len(cleared_nodes),
                            skip_recon=True,
                        )

                        if self.state.game_over or not self.running or self.return_to_menu_requested:
                            return

                        if node_cleared:
                            cleared_nodes.add(tap_index)
                            current_subnet.current_anchor = tap_index
                            if current_subnet.is_conquered():
                                self.state.mark_subnet_conquered(current_subnet.subnet_id)
                            world_tick_messages.extend(self.advance_world_dynamics(network, events_data))
                            self.checkpoint_progress()

                            if current_subnet.is_conquered():
                                print(f"\n[sys] Subnet {current_subnet.subnet_id} is fully conquered. Border travel is now open.")
                                if network.all_subnets_conquered():
                                    completed_day = self.state.day
                                    self.state.day += 1
                                    self.state.trace_level = max(0, self.state.trace_level - 10)
                                    self.play_day_transition(
                                        completed_day,
                                        self.state.day,
                                        world,
                                        sum(len(subnet.cleared_nodes) for subnet in network.subnets.values()),
                                        day_summary["crypto"],
                                        day_summary["trace"],
                                        day_summary["brute"],
                                        day_summary["exploit"],
                                    )
                                    self.state.active_network = None
                                    self.state.current_subnet_id = None
                                    self.state.current_domain_id = None
                                    self.active_tap_node_index = None
                                    self.current_enemy = None
                                    self.state.subnet_contract_inboxes = {}
                                    self.state.current_contracts = []
                                    self.state.bound_contract_subnet_id = None
                                    self.checkpoint_progress()
                                    break
                                input("[Press Enter to stabilize the conquered border...]")
                            else:
                                self.advance_counter_sweep()
                                current_subnet.sweep_level = self.route_sweep_level
                                current_subnet.sweep_max = self.route_sweep_max
                                self.sync_active_subnet_view(network, current_subnet)
                                input("[Press Enter to stabilize the route mesh...]")
                        continue

                    if choice in {"soft", "soft engage", "soft-engage"}:
                        survived, intel_lines = combat.run_soft_engage(tap_enemy)
                        tap_history = list(getattr(tap_node, "recon_log", []))
                        tap_history.append("[soft] opening response recorded")
                        for line in intel_lines:
                            tap_history.append(f"[soft] {line}")
                        tap_node.recon_log = tap_history[-8:]
                        self.checkpoint_progress()
                        if not survived or self.state.game_over:
                            return
                        continue

                    try:
                        parsed_tap = self.arsenal.parse_command(choice, owner=self.player) if self.arsenal else None
                    except ValueError:
                        parsed_tap = None
                    if parsed_tap and self.arsenal.scripts.get(parsed_tap.base_cmd, {}).get("type") == "scan":
                        success, message, alert_stage = combat.execute_recon_action(choice, tap_enemy)
                        print(f"\n{message}")
                        if success:
                            tap_history = list(getattr(tap_node, "recon_log", []))
                            tap_history.append(strip_ansi(message))
                            tap_node.recon_log = tap_history[-8:]
                        if alert_stage == 1:
                            print("[!] COUNTER-SCAN: the host has a rough map of your node now.")
                        elif alert_stage == 2:
                            print("[!] COUNTER-SCAN: your signature leaked. This breach is now hot.")
                        self.checkpoint_progress()
                        input("[Press Enter to return to the passive tap...]")
                        continue
                    if parsed_tap:
                        print("[sys] That payload needs a live breach. Use engage first.")
                        time.sleep(0.9)
                        continue

                node_index = next((idx for idx, node in enumerate(world.nodes) if node.ip_address.lower() == choice), -1)
                if not (0 <= node_index < len(world.nodes)):
                    print("[sys] Route not found. No live node matches that address in the current mesh.")
                    time.sleep(0.8)
                    continue

                node = world.nodes[node_index]
                if getattr(node, "compromise_state", "") == "bricked" and node_index not in cleared_nodes:
                    cleared_nodes.add(node_index)

                if node_index in cleared_nodes:
                    self.active_tap_node_index = None
                    self.current_enemy = None
                    can_revisit = world.can_traverse_from(current_anchor, node_index, cleared_nodes)
                    can_fast_travel = self.state.can_fast_travel_to(node)
                    if not can_revisit and not can_fast_travel:
                        print("[sys] That node is outside your live local route mesh.")
                        time.sleep(0.9)
                        continue

                    current_subnet.current_anchor = node_index
                    self.sync_active_subnet_view(network, current_subnet)

                    if node.root_access and getattr(node, "revolt_state", None):
                        self.defend_rooted_node(
                            node,
                            node_index,
                            current_subnet,
                            world,
                            combat,
                            enemies_data,
                            ability_library,
                            events_data,
                        )
                    elif getattr(node, "compromise_state", "") == "bricked":
                        self.investigate_forensic_node(
                            node,
                            node_index,
                            current_subnet,
                            enemies_data,
                            modifiers,
                            ability_library,
                            events_data,
                        )
                    elif node.root_access:
                        self.manage_rooted_node(node, world, events_data)
                    else:
                        print("[sys] That node has already been resolved.")
                        time.sleep(0.8)
                    continue

                if not world.can_traverse_from(current_anchor, node_index, cleared_nodes):
                    print("[sys] Route locked.")
                    time.sleep(1.0)
                    continue

                current_subnet.current_anchor = node_index
                self.sync_active_subnet_view(network, current_subnet)
                self.active_tap_node_index = node_index
                self.current_enemy = self.build_enemy_for_node(node, enemies_data, modifiers, ability_library)
                self.apply_objective_card(node_tap_card(node.ip_address, self.current_enemy.get_recon_alert_text()))
                self.checkpoint_progress()

    def run_game(self):
        original_input = builtins.input
        original_system = os.system
        builtins.input = self.custom_input

        def custom_system(command):
            if command in {"cls", "clear"}:
                self.clear_screen()
            else:
                return original_system(command)

        os.system = custom_system
        try:
            self.clear_screen()
            print("[sys] BIOS check initialized...")
            time.sleep(0.4)
            print("[sys] Memory sector OK. Core modules verified.")
            time.sleep(0.4)
            print("\n> ssh root@terminal-rogue.net")
            time.sleep(0.8)
            print("root@terminal-rogue.net's password: ********")
            time.sleep(0.6)
            print("[sys] Authenticating...")
            time.sleep(0.4)
            print("[sys] Access Granted.\n")
            time.sleep(0.5)

            while self.running:
                session_loaded = False
                while self.running and not session_loaded:
                    self.clear_screen()
                    print(self.get_ascii_art("terminal_rogue"))
                    print("[ bootloader ] rogue shell initialized\n")
                    print("[1] START NEW SESSION (TUTORIAL)")
                    print("[2] START NEW SESSION (SKIP TUTORIAL)")
                    print("[3] CONTINUE SESSION (LOAD SAVE)")
                    choice = input("Select an option: ").strip()

                    if choice == "1":
                        print("\n[sys] Initiating fresh run sequence...")
                        time.sleep(0.8)
                        state = GameState()
                        player = Player(profile="student")
                        session_loaded = True
                        continue

                    if choice == "2":
                        print("\n[sys] Tutorial bypass accepted. Live grid access loading...")
                        time.sleep(0.8)
                        state = GameState()
                        state.prologue_complete = True
                        state.origin_story = "skip"
                        player = Player(profile="rookie")
                        session_loaded = True
                        continue

                    if choice == "3":
                        print("\n[sys] Locating save state...")
                        time.sleep(0.4)
                        save_reference = self.selected_save_reference or GameState.AUTOSAVE_SLOT_KEY
                        save_data = GameState.load_session(slot_key=save_reference)
                        if save_data:
                            state = save_data["state"]
                            player = save_data["player"]
                            state.ensure_runtime_defaults()
                            player.ensure_runtime_defaults()
                            if state.game_over:
                                GameState.delete_session(slot_key=save_reference)
                                print("[sys] Save archive was flagged dead. Wiped.")
                                time.sleep(0.8)
                                continue
                            print("[sys] Save state restored successfully.")
                            time.sleep(0.8)
                            self.active_save_reference = save_reference
                            self.selected_save_reference = None
                            session_loaded = True
                            continue
                        print("\n[sys] ERROR: No local save state detected. Save/Load module offline.\n")
                        time.sleep(1.0)
                        self.selected_save_reference = None
                        continue

                    print("\n[sys] Invalid selection. Core command not recognized.\n")
                    time.sleep(0.8)

                if not self.running:
                    return

                self.clear_screen()
                for value in range(10, 101, 30):
                    print(f"[sys] Mounting virtual drives... {value}%")
                    time.sleep(0.2)
                print("[sys] Bypassing ISP firewalls...")
                time.sleep(0.3)
                print("[sys] Establishing encrypted tunnel...")
                time.sleep(0.5)
                print("[sys] Connection Secure.\n")
                time.sleep(0.4)

                game_data = DataLoader.load_all()
                arsenal = Arsenal(game_data.get("arsenal", {}))
                self.item_library = game_data.get("events", {}).get("consumables", {})
                combat = CombatEngine(player, arsenal, state, item_library=self.item_library, ui_session=self)
                self.combat_engine = combat

                self.state = state
                self.player = player
                self.arsenal = arsenal
                self.apply_day_unlocks()
                self.update_arsenal_display(arsenal)

                enemies_data = game_data.get("enemies", {}).get("enemies", {})
                ability_library = game_data.get("enemies", {}).get("abilities", {})

                if not state.prologue_complete:
                    if not self.run_tutorial_sequence(combat, enemies_data, ability_library):
                        self.shutdown_game()
                        return
                else:
                    print(f"\n[sys] Resuming session... (Day {state.day})")
                    time.sleep(0.8)

                if self.return_to_menu_requested:
                    self.reset_frontend_state()
                    continue

                self.run_world_cycle(combat, game_data)

                if not self.running:
                    return

                if self.return_to_menu_requested:
                    self.reset_frontend_state()
                    continue

                if self.state and self.state.game_over:
                    self.handle_permadeath()
                    continue

                return
        finally:
            builtins.input = original_input
            os.system = original_system

    def color_for(self, tone: str):
        return self.COLORS.get(tone, self.COLORS["text"])

    def render_backplane(self, console):
        console.clear(fg=self.COLORS["text"], bg=self.COLORS["bg"])

    def get_terminal_identity(self):
        if self.player:
            return f"root@{self.player.handle}"
        return "root@terminal-rogue"

    def format_pane_title(self, path: str):
        return f"{self.get_terminal_identity()}:{path}"

    def draw_box(self, console, x, y, w, h, color):
        if w < 2 or h < 2:
            return
        console.print(x, y, "+" + "-" * (w - 2) + "+", fg=color)
        for row in range(y + 1, y + h - 1):
            console.print(x, row, "|", fg=color)
            console.print(x + w - 1, row, "|", fg=color)
        console.print(x, y + h - 1, "+" + "-" * (w - 2) + "+", fg=color)

    def render(self):
        console = self.console
        self.render_backplane(console)

        self.draw_panel(
            console,
            0,
            0,
            self.FEED_WIDTH,
            self.CONTENT_HEIGHT,
            self.format_pane_title("~/var/log/live_feed"),
            self.COLORS["green"],
        )
        self.draw_panel(
            console,
            0,
            self.CONTENT_HEIGHT,
            self.WIDTH,
            self.INPUT_HEIGHT,
            self.format_pane_title("~"),
            self.COLORS["green"],
        )

        self.render_log(console, 1, 1, self.FEED_WIDTH - 2, self.CONTENT_HEIGHT - 2)
        self.render_sidebar(console, self.FEED_WIDTH + 1, 0, self.SIDEBAR_WIDTH - 1, self.CONTENT_HEIGHT)
        self.render_input(console, 1, self.CONTENT_HEIGHT + 1, self.WIDTH - 2, self.INPUT_HEIGHT - 2)

    def draw_panel(self, console, x, y, w, h, title, color):
        if w < 4 or h < 4:
            return

        console.draw_rect(x, y, w, h, ch=ord(" "), bg=self.COLORS["panel"])
        self.draw_box(console, x, y, w, h, self.COLORS["line"])
        clipped = title[: max(0, w - 4)]
        tag_x = clamp(x + 2, x + 1, max(x + 1, x + w - len(clipped) - 1))
        console.print(tag_x, y, clipped, fg=color, bg=self.COLORS["panel"])

    def render_log(self, console, x, y, w, h):
        wrapped = []
        with self.io_lock:
            source_lines = list(self.log_lines)
            if self.stdout_buffer:
                source_lines.append((strip_ansi(self.stdout_buffer), self.pick_line_color(self.stdout_buffer)))

        feed_label = self.format_pane_title("~/var/log/session.log") + "$ tail -f live_feed"
        console.print(x, y, feed_label[:w], fg=self.COLORS["muted"])
        y += 1
        h -= 1
        if h <= 0:
            return

        for text, tone in source_lines[-260:]:
            if not text:
                wrapped.append(("", tone))
                continue
            chunks = textwrap.wrap(text, width=max(8, w - 1), replace_whitespace=False, drop_whitespace=False)
            if not chunks:
                wrapped.append(("", tone))
            else:
                for chunk in chunks:
                    wrapped.append((chunk, tone))

        visible = wrapped[-h:]
        start_y = y + max(0, h - len(visible))
        for offset, (line, tone) in enumerate(visible):
            console.print(x, start_y + offset, line[:w], fg=self.color_for(tone))

    def render_sidebar(self, console, x, y, w, h):
        status_h = 12
        objective_h = 10
        target_h = 8
        map_h = 10
        databank_h = h - status_h - objective_h - target_h - map_h

        self.draw_panel(console, x, y, w, status_h, self.format_pane_title("~/proc/player"), self.COLORS["green"])
        self.render_player_panel(console, x + 1, y + 1, w - 2, status_h - 2)

        y += status_h
        self.draw_panel(
            console,
            x,
            y,
            w,
            objective_h,
            self.format_pane_title("~/proc/objective"),
            self.color_for(self.objective_tone),
        )
        self.render_objective_panel(console, x + 1, y + 1, w - 2, objective_h - 2)

        y += objective_h
        self.draw_panel(console, x, y, w, target_h, self.format_pane_title("~/proc/target"), self.COLORS["yellow"])
        self.render_target_panel(console, x + 1, y + 1, w - 2, target_h - 2)

        y += target_h
        map_title = self.format_pane_title("~/proc/architecture") if self.current_enemy else self.format_pane_title("~/net/route_web")
        self.draw_panel(console, x, y, w, map_h, map_title, self.COLORS["cyan"])
        self.render_network_map(console, x + 1, y + 1, w - 2, map_h - 2)

        y += map_h
        self.draw_panel(console, x, y, w, databank_h, self.format_pane_title("~/usr/share/databank"), self.COLORS["magenta"])
        self.render_databank(console, x + 1, y + 1, w - 2, databank_h - 2)

    def render_objective_panel(self, console, x, y, w, h):
        lines = []
        if self.objective_is_tutorial:
            lines.append(("[ TUTORIAL ACTIVE ]", "magenta"))
            lines.append((self.objective_title, self.objective_tone))
            if self.objective_command:
                lines.append((f"TRY : {self.objective_command}", "green"))
            if self.objective_detail:
                lines.append((f"WHY : {self.objective_detail}", "yellow"))
            lines.append(("", "text"))
            lines.append((self.objective_body, "text"))
        else:
            lines.append((self.objective_title, self.objective_tone))
            if self.objective_command:
                lines.append((f"NEXT: {self.objective_command}", "green"))
            if self.objective_detail:
                lines.append((self.objective_detail, "yellow"))
            if self.objective_body:
                if self.objective_command or self.objective_detail:
                    lines.append(("", "text"))
                lines.append((self.objective_body, "text"))

        rendered = []
        for line, tone in lines:
            if line == "":
                rendered.append(("", tone))
                continue
            wrapped = textwrap.wrap(line, width=max(6, w), replace_whitespace=False, drop_whitespace=False)
            if not wrapped:
                rendered.append(("", tone))
            else:
                for chunk in wrapped:
                    rendered.append((chunk, tone))

        visible = rendered[:h]
        for offset, (line, tone) in enumerate(visible):
            console.print(x, y + offset, line[:w], fg=self.color_for(tone))

    def get_integrity_tone(self, current_hp: int, max_hp: int):
        if current_hp <= 0:
            return "red"
        ratio = current_hp / max(1, max_hp)
        if ratio <= 0.35:
            return "red"
        if ratio <= 0.7:
            return "yellow"
        return "green"

    def render_player_panel(self, console, x, y, w, h):
        if not self.player:
            self.render_wrapped_block(console, x, y, w, h, ["Awaiting session bootstrap."], "text")
            return

        row = y
        effective_ram = self.player.get_effective_max_ram()
        console.print(x, row, f"{self.player.handle}@{self.player.local_ip}"[:w], fg=self.COLORS["white"])
        row += 1
        console.print(x, row, self.player.title[:w], fg=self.COLORS["muted"])
        row += 1
        console.print(x, row, f"day:{self.state.day if self.state else 1}  crypto:{self.state.player_crypto if self.state else 0}"[:w], fg=self.COLORS["cyan"])
        row += 1
        trace_tone = "green" if (self.state.trace_level if self.state else 0) < 35 else "yellow" if (self.state.trace_level if self.state else 0) < 70 else "red"
        console.print(x, row, f"trace:{self.state.trace_level if self.state else 0}  ram:{self.player.current_ram}/{effective_ram}"[:w], fg=self.color_for(trace_tone))
        row += 1
        if self.route_sweep_max > 0:
            sweep_tone = "green" if self.route_sweep_level < self.route_sweep_max * 0.4 else "yellow" if self.route_sweep_level < self.route_sweep_max * 0.75 else "red"
            console.print(x, row, f"sweep:{self.route_sweep_level}/{self.route_sweep_max}"[:w], fg=self.color_for(sweep_tone))
            row += 1
        if self.state:
            console.print(
                x,
                row,
                f"mail:{len(self.state.get_accepted_contracts())}/{len(self.state.current_contracts)} active"[:w],
                fg=self.COLORS["magenta"],
            )
            row += 1

        for key in ["OS", "SEC", "NET", "MEM", "STO"]:
            if row >= y + h - 2:
                break
            subsystem = self.player.subsystems[key]
            tone = self.get_integrity_tone(subsystem.current_hp, subsystem.max_hp)
            console.print(x, row, f"{key:<3} {subsystem.current_hp:>2}/{subsystem.max_hp:<2}"[:w], fg=self.color_for(tone))
            row += 1

        extras = [self.player.get_support_bot_summary(), self.player.get_consumable_summary()]
        for extra in extras:
            if row >= y + h:
                break
            console.print(x, row, extra[:w], fg=self.COLORS["muted"])
            row += 1

    def render_target_panel(self, console, x, y, w, h):
        enemy = self.current_enemy
        if not enemy:
            self.render_wrapped_block(
                console,
                x,
                y,
                w,
                h,
                ["No live hostile link.", "", "Recon shell and combat", "details will appear here."],
                "text",
            )
            return

        row = y
        console.print(x, row, enemy.get_visible_name()[:w], fg=self.COLORS["white"])
        row += 1
        console.print(x, row, enemy.get_visible_weapon()[:w], fg=self.COLORS["muted"])
        row += 1

        alert_stage = enemy.get_recon_alert_stage()
        alert_tone = "green" if alert_stage == 0 else "yellow" if alert_stage == 1 else "red"
        console.print(x, row, f"entry: {enemy.get_recon_alert_text()}"[:w], fg=self.color_for(alert_tone))
        row += 1

        adaptation = enemy.get_adaptation_summary()
        if adaptation and row < y + h:
            console.print(x, row, f"adapt: {adaptation}"[:w], fg=self.COLORS["yellow"])
            row += 1

        if not enemy.topology_revealed:
            if row < y + h:
                console.print(x, row, "No structure read."[:w], fg=self.COLORS["muted"])
                row += 1
            if row < y + h:
                console.print(x, row, "Run nmap or stay blind."[:w], fg=self.COLORS["cyan"])
            return

        for key in ["OS", "SEC", "NET", "MEM", "STO"]:
            if row >= y + h:
                break
            subsystem = enemy.subsystems[key]
            if enemy.has_telemetry_for(key):
                tone = self.get_integrity_tone(subsystem.current_hp, subsystem.max_hp)
                text = f"{key:<3} {subsystem.current_hp:>2}/{subsystem.max_hp:<2}"
            else:
                tone = "red" if subsystem.is_destroyed else "muted"
                text = f"{key:<3} {'OFF' if subsystem.is_destroyed else '??'}"
            console.print(x, row, text[:w], fg=self.color_for(tone))
            row += 1

    def render_network_map(self, console, x, y, w, h):
        if self.current_enemy:
            self.render_architecture_map(console, x, y, w, h)
            return

        status_lines = textwrap.wrap(self.map_status, width=max(10, w))
        for idx, line in enumerate(status_lines[:2]):
            console.print(x, y + idx, line[:w], fg=self.COLORS["muted"])

        map_top = y + 2
        map_height = h - 2
        if map_height <= 2 or not self.map_world or not getattr(self.map_world, "nodes", None):
            console.print(x, map_top, "No active route mesh.", fg=self.COLORS["muted"])
            return

        root_x = x + 1
        root_y = map_top + (map_height // 2)
        console.print(root_x, root_y, "@", fg=self.COLORS["cyan"])
        console.print(root_x + 1, root_y, "YOU", fg=self.COLORS["cyan"])

        depths = getattr(self.map_world, "node_depths", {}) or {index: 1 for index in range(len(self.map_world.nodes))}
        groups = {}
        for index, node in enumerate(self.map_world.nodes):
            depth = depths.get(index, 1)
            groups.setdefault(depth, []).append(index)

        min_depth = min(groups) if groups else 1
        max_depth = max(groups) if groups else 1
        positions = {}
        left = x + 6
        right = x + w - 2
        usable_width = max(4, right - left)
        usable_height = max(3, map_height - 1)

        for depth, indices in sorted(groups.items()):
            if max_depth == min_depth:
                column_x = left + usable_width // 2
            else:
                column_x = left + int(((depth - min_depth) / max(1, max_depth - min_depth)) * usable_width)
            total = len(indices)
            for order, index in enumerate(sorted(indices)):
                if total == 1:
                    row_y = map_top + usable_height // 2
                else:
                    row_y = map_top + int((order + 1) * usable_height / (total + 1))
                positions[index] = (column_x, row_y)

        for entry_index in getattr(self.map_world, "entry_links", set()):
            if entry_index in positions:
                entry_x, entry_y = positions[entry_index]
                self.draw_line(console, root_x + 3, root_y, entry_x, entry_y, ".", self.COLORS["line"])

        for left_index, linked in getattr(self.map_world, "forward_links", {}).items():
            for right_index in linked:
                if left_index not in positions or right_index not in positions:
                    continue
                left_pos = positions[left_index]
                right_pos = positions[right_index]
                line_color = self.COLORS["line"]
                if left_index in self.map_cleared or right_index in self.map_cleared:
                    line_color = self.COLORS["green"]
                self.draw_line(console, left_pos[0], left_pos[1], right_pos[0], right_pos[1], ".", line_color)
                arrow = ">" if right_pos[0] >= left_pos[0] else "<"
                arrow_x = right_pos[0] - 1 if right_pos[0] > left_pos[0] else right_pos[0] + 1
                if x <= arrow_x < x + w and map_top <= right_pos[1] < map_top + map_height:
                    console.print(arrow_x, right_pos[1], arrow, fg=line_color)

        sweep_ratio = 0 if self.route_sweep_max <= 0 else self.route_sweep_level / max(1, self.route_sweep_max)
        sweep_color = self.COLORS["green"] if sweep_ratio < 0.4 else self.COLORS["yellow"] if sweep_ratio < 0.75 else self.COLORS["red"]
        console.print(x, map_top, f"SWEEP {self.route_sweep_level}/{self.route_sweep_max}", fg=sweep_color)

        for index, node in enumerate(self.map_world.nodes):
            if index not in positions:
                continue
            node_x, node_y = positions[index]
            is_cleared = index in self.map_cleared
            is_active = index == self.map_active
            anchor_index = self.map_active
            if anchor_index is None and self.map_world.entry_links:
                anchor_index = min(self.map_world.entry_links)
            is_locked = (
                self.map_world
                and not self.map_world.can_traverse_from(anchor_index, index, self.map_cleared)
                and not is_cleared
            )

            if node.node_type == "shop":
                glyph = "$"
                color = self.COLORS["yellow"]
            elif node.node_type == "gatekeeper":
                glyph = "G"
                color = self.COLORS["red"]
            elif node.node_type == "iot":
                glyph = "o"
                color = self.COLORS["cyan"]
            elif node.node_type == "minecraft":
                glyph = "m"
                color = self.COLORS["green"]
            elif node.node_type == "server":
                glyph = "s"
                color = self.COLORS["magenta"]
            elif node.node_type == "corporate":
                glyph = "c"
                color = self.COLORS["red"]
            else:
                glyph = "n"
                color = self.COLORS["white"]

            if is_locked:
                glyph = "#"
                color = self.COLORS["muted"]
            if is_cleared:
                glyph = "x"
                color = self.COLORS["green"]
            elif is_active:
                glyph = "@"
                color = self.COLORS["white"]

            console.print(node_x, node_y, glyph, fg=color)
            contract_hit = bool(self.state and self.state.get_contracts_for_node(node.ip_address, accepted_only=True))
            if contract_hit and not is_cleared:
                marker_x = clamp(node_x + 1, x, x + w - 1)
                console.print(marker_x, node_y, "!", fg=self.COLORS["yellow"])
            if node.node_type == "gatekeeper":
                label = "BDR"
            elif node.node_type == "shop":
                label = "MKT"
            elif is_cleared:
                label = "CLR"
            elif is_locked:
                label = "LCK"
            elif getattr(node, "lockdown_turns", 0) > 0:
                label = "ALR"
            else:
                label = node.ip_address.split(".")[-1]
            label_x = clamp(node_x - (len(label) // 2), x, x + max(0, w - len(label)))
            label_y = clamp(node_y + 1, map_top, map_top + map_height - 1)
            label_color = self.COLORS["yellow"] if contract_hit and not is_cleared else self.COLORS["muted"]
            console.print(label_x, label_y, label, fg=label_color)

    def render_architecture_map(self, console, x, y, w, h):
        enemy = self.current_enemy
        if not enemy:
            console.print(x, y, "No live hostile link.", fg=self.COLORS["muted"])
            return

        console.print(x, y, "target module lattice", fg=self.COLORS["muted"])
        layout_top = y + 1
        center_x = x + (w // 2)
        center_y = layout_top + max(2, (h - 2) // 2)
        positions = {
            "SEC": (center_x, layout_top),
            "MEM": (x + 2, center_y),
            "OS": (center_x, center_y),
            "NET": (x + max(2, w - 8), center_y),
            "STO": (center_x, y + max(2, h - 1)),
        }

        for key in ["SEC", "MEM", "NET", "STO"]:
            self.draw_line(
                console,
                positions["OS"][0],
                positions["OS"][1],
                positions[key][0],
                positions[key][1],
                ".",
                self.COLORS["line"],
            )

        for key in ["SEC", "MEM", "OS", "NET", "STO"]:
            subsystem = enemy.subsystems[key]
            if not enemy.topology_revealed:
                label = "???"
                color = self.COLORS["muted"]
            elif enemy.has_telemetry_for(key):
                label = f"{key}{subsystem.current_hp:02d}"
                ratio = subsystem.current_hp / max(1, subsystem.max_hp)
                if subsystem.is_destroyed:
                    color = self.COLORS["red"]
                elif ratio < 0.35:
                    color = self.COLORS["yellow"]
                else:
                    color = self.COLORS["green"]
            else:
                label = f"{key}??"
                color = self.COLORS["cyan"] if not subsystem.is_destroyed else self.COLORS["red"]

            label_x = clamp(positions[key][0] - (len(label) // 2), x, x + max(0, w - len(label)))
            label_y = clamp(positions[key][1], y, y + h - 1)
            console.print(label_x, label_y, label, fg=color)

    def render_databank(self, console, x, y, w, h):
        row = y
        section_tones = {
            "TOOLS": "green",
            "FLAGS": "yellow",
            "ITEMS": "magenta",
            "TARGETS": "cyan",
        }
        for line in self.databank_lines:
            if row >= y + h:
                break
            tone = section_tones.get(line.strip(), "muted")
            console.print(x, row, line[:w], fg=self.color_for(tone))
            row += 1

    def render_input(self, console, x, y, w, h):
        if not self.active_prompt:
            prompt = self.get_terminal_identity() + ":~$ "
            console.print(x, y, prompt[:w], fg=self.COLORS["muted"])
            status = "# process running"
            offset = min(len(prompt), max(0, w - 1))
            console.print(x + offset, y, status[: max(0, w - offset)], fg=self.COLORS["muted"])
            console.print(
                x,
                y + 1,
                "keyboard opens when the next prompt is active",
                fg=self.COLORS["muted"],
            )
            return

        prompt = self.active_prompt
        prompt_color = self.COLORS["green"]
        console.print(x, y, prompt[:w], fg=prompt_color)

        input_x = x + min(len(prompt), max(0, w - 2))
        available = max(1, w - (input_x - x) - 2)
        visible_input = self.current_input[-available:]
        console.print(input_x, y, visible_input, fg=self.COLORS["white"])
        cursor_x = clamp(input_x + len(visible_input), x, x + w - 1)
        console.print(cursor_x, y, "_", fg=self.COLORS["cyan"])
        console.print(
            x,
            y + 1,
            "enter submit | backspace edit | esc clear | help | man <topic> | man exploit",
            fg=self.COLORS["muted"],
        )

    def render_wrapped_block(self, console, x, y, w, h, lines, tone="text", title_tone=None):
        rendered = []
        if not lines:
            return

        for index, line in enumerate(lines):
            current_tone = title_tone if title_tone and index == 0 else tone
            if line == "":
                rendered.append(("", current_tone))
                continue
            wrapped = textwrap.wrap(line, width=max(6, w), replace_whitespace=False, drop_whitespace=False)
            if not wrapped:
                rendered.append(("", current_tone))
            else:
                for chunk in wrapped:
                    rendered.append((chunk, current_tone))

        for row, (chunk, current_tone) in enumerate(rendered[:h]):
            console.print(x, y + row, chunk[:w], fg=self.color_for(current_tone))

    def draw_line(self, console, x1, y1, x2, y2, char, color):
        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx + dy
        x, y = x1, y1
        while True:
            if (x, y) not in {(x1, y1), (x2, y2)}:
                console.print(x, y, char, fg=color)
            if x == x2 and y == y2:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy
