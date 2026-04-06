import os
import time
from contextlib import contextmanager
from dataclasses import dataclass

from arsenal import Arsenal
from combat_flavor import CombatFrame, build_enemy_action_frames, build_player_action_frames
from combat_feedback import build_action_feedback, capture_enemy_feedback_state
from entities import Player, Enemy
from game_state import GameState


@dataclass
class EncounterResult:
    outcome: str
    reason: str = ""


class CombatEngine:
    def __init__(self, player: Player, arsenal: Arsenal, state: GameState, item_library=None, ui_session=None):
        self.player = player
        self.arsenal = arsenal
        self.state = state
        self.item_library = item_library or {}
        self.ui_session = ui_session
        self.planning_snapshot = None

    def get_resolved_target(self, parsed_command, script_data: dict):
        if parsed_command.target_subsystem:
            return parsed_command.target_subsystem
        default_target = script_data.get("default_target")
        if default_target:
            return str(default_target).upper()
        if script_data.get("type") in {"brute_force", "exploit"}:
            return "OS"
        return None

    def process_exploit_chain(self, command_str: str, enemy: Enemy, source="player"):
        try:
            parsed = self.arsenal.parse_command(command_str, owner=self.player)
        except ValueError:
            return

        script_data = self.arsenal.scripts.get(parsed.base_cmd, {})
        resolved_target = self.get_resolved_target(parsed, script_data)
        activation = self.state.register_exploit_event(
            parsed,
            script_data,
            resolved_target,
            enemy,
            self.player,
            source=source,
        )
        if not activation:
            return

        for line in activation["lines"]:
            print(line)
            time.sleep(1.0)

    def clear_screen(self):
        if self.ui_session and hasattr(self.ui_session, "clear_screen"):
            self.ui_session.clear_screen()
            return
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def pause_to_read(prompt: str = "[Press Enter to continue...]"):
        input(f"\033[90m{prompt}\033[0m")

    @contextmanager
    def transient_animation(self):
        if self.ui_session and hasattr(self.ui_session, "suspend_session_archive"):
            self.ui_session.suspend_session_archive += 1
            try:
                yield
            finally:
                self.ui_session.suspend_session_archive = max(0, self.ui_session.suspend_session_archive - 1)
            return
        yield

    @staticmethod
    def tone_ansi(tone: str) -> str:
        return {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
        }.get(tone, "\033[97m")

    def show_frame(self, frame: CombatFrame):
        self.clear_screen()
        tone = self.tone_ansi(frame.tone)
        print(f"\n{tone}[{frame.title}]\033[0m")
        print("\033[90m" + "=" * 54 + "\033[0m")
        for line in frame.lines:
            print(f"{tone}{line}\033[0m")
        time.sleep(frame.delay)

    def play_transient_frames(self, frames: list[CombatFrame]):
        with self.transient_animation():
            for frame in frames:
                self.show_frame(frame)

    def print_action_output_log(
        self,
        index: int,
        total: int,
        command_str: str,
        result,
        flag_notes: list[str],
        feedback_lines: list[str] | None = None,
    ):
        self.clear_screen()
        print(f"\n\033[95m[OUTPUT LOG {index}/{total}]\033[0m")
        print("\033[90m" + "=" * 54 + "\033[0m")
        print(f"\033[90mPAYLOAD :: {command_str}\033[0m")
        if flag_notes:
            print("\033[95m[WRAPPER EFFECTS]\033[0m")
            for note in flag_notes:
                print(f"\033[95m- {note}\033[0m")
            print("\033[90m" + "-" * 54 + "\033[0m")
        if feedback_lines:
            print("\033[96m[FEEDBACK CHANNEL]\033[0m")
            for line in feedback_lines:
                print(f"\033[96m- {line}\033[0m")
            print("\033[90m" + "-" * 54 + "\033[0m")
        self.print_action_report(result)
        time.sleep(1.0)

    def print_enemy_output_log(self, enemy: Enemy, lines: list[str]):
        self.clear_screen()
        print("\n\033[91m[HOST RESPONSE LOG]\033[0m")
        print("\033[90m" + "=" * 54 + "\033[0m")
        print(f"\033[90mHOST :: {enemy.get_visible_name()}    ROUTINE :: {enemy.current_intent['name']}\033[0m")
        print("\033[90m" + "-" * 54 + "\033[0m")
        for line in lines:
            print(f"\033[91m[-] {line}\033[0m")
        time.sleep(1.15)

    def print_turn_summary(self, turn_number: int, enemy: Enemy):
        self.clear_screen()
        print(f"\n\033[96m[TURN {turn_number:02d} SUMMARY]\033[0m")
        print("\033[90m" + "=" * 54 + "\033[0m")
        print(
            f"\033[96mRIG\033[0m :: OS {self.player.subsystems['OS'].current_hp}/{self.player.subsystems['OS'].max_hp}   "
            f"RAM {self.player.current_ram}/{self.player.get_effective_max_ram()}   TRACE {self.state.trace_level}"
        )
        print(f"\033[96mDEF\033[0m :: {self.player.get_defense_summary()}")
        print(f"\033[96mBOT\033[0m :: {self.player.get_support_bot_summary()}")
        if enemy.subsystems["OS"].current_hp > 0:
            if enemy.has_telemetry_for("OS"):
                host_line = (
                    f"{enemy.get_visible_name()} core {enemy.subsystems['OS'].current_hp}/"
                    f"{enemy.subsystems['OS'].max_hp}"
                )
            else:
                host_line = f"{enemy.get_visible_name()} core still live // exact integrity masked"
        else:
            host_line = f"{enemy.get_visible_name()} core offline"
        print(f"\033[91mHOST\033[0m :: {host_line}")
        print(f"\033[91mLINK\033[0m :: {enemy.get_recon_alert_text()}")
        if enemy.intent_revealed:
            print(f"\033[91mNEXT READ\033[0m :: hostile routine cache last seen as {enemy.current_intent['name']}")
        print("\033[90m" + "-" * 54 + "\033[0m")

    def apply_disconnect_penalty(self, enemy: Enemy):
        trace_gain = 18
        backlash = 6
        self.state.trace_level += trace_gain
        self.player.subsystems["OS"].take_damage(backlash)
        print("\n\033[91m[!] DISCONNECT FORCED UNDER FIRE.\033[0m")
        print(f"\033[91m[-] Trace Level increased by {trace_gain}.\033[0m")
        print(f"\033[91m[-] Connection backlash dealt {backlash} damage to your Core OS.\033[0m")
        time.sleep(2.4)
        if self.player.subsystems["OS"].current_hp <= 0:
            self.state.game_over = True
            return EncounterResult("defeat", "disconnect_backlash")
        return EncounterResult("fled", enemy.id)

    def execute_recon_action(self, command_str: str, enemy: Enemy):
        try:
            parsed = self.arsenal.parse_command(command_str, owner=self.player)
        except ValueError as exc:
            return False, str(exc), 0

        script_data = self.arsenal.scripts.get(parsed.base_cmd, {})
        if script_data.get("type") != "scan":
            return False, "Error: Aggressive payloads are blocked during passive tap.", 0

        result = self.arsenal.execute(command_str, self.player, enemy, self.state)
        if not result.success:
            return False, result.message, 0

        exposure_map = {
            "whois": 10,
            "nmap": 25 if not parsed.has_target else 35,
            "enum": 20,
            "dirb": 14,
        }
        exposure = exposure_map.get(parsed.base_cmd, 0)
        exposure += sum(self.arsenal.flags.get(flag, {}).get("exposure_delta", 0) for flag in parsed.flags)
        if enemy.recon_discount > 0:
            exposure = max(0, exposure - enemy.recon_discount)
            enemy.recon_discount = 0

        alert_stage = enemy.apply_recon_exposure(max(0, exposure))
        return True, result.message, alert_stage

    def parse_item_command(self, command_str: str):
        tokens = command_str.strip().split()
        if len(tokens) < 2 or tokens[0].lower() != "use":
            raise ValueError("Error: Item syntax is 'use <item>' or 'use <item> -target <SUB>'.")

        item_id = tokens[1].lower()
        item_data = self.item_library.get(item_id)
        if not item_data:
            raise ValueError(f"Error: Consumable '{item_id}' not recognized.")
        if self.player.get_consumable_count(item_id) <= 0:
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
        if target_subsystem and target_subsystem not in self.player.subsystems:
            raise ValueError(f"Error: Defensive target [{target_subsystem}] does not exist.")
        return item_id, item_data, target_subsystem

    def get_action_cost(self, command_str: str):
        if command_str.strip().lower().startswith("use "):
            self.parse_item_command(command_str)
            return 0
        return self.arsenal.get_command_cost(command_str, owner=self.player)

    def execute_item_command(self, command_str: str, enemy: Enemy):
        try:
            item_id, item_data, target_subsystem = self.parse_item_command(command_str)
        except ValueError as exc:
            return False, str(exc)

        effect = item_data.get("effect")
        amount = item_data.get("amount", 0)
        turns = item_data.get("turns", 1)

        if effect == "ram":
            restored = min(max(0, self.player.get_effective_max_ram() - self.player.current_ram), amount)
            if restored <= 0:
                return False, "Error: RAM is already at capacity."
            self.player.consume_consumable(item_id)
            self.player.current_ram += restored
            return True, f"SUCCESS: {item_data.get('name', item_id)} injected. Restored {restored} RAM."

        if effect == "guard":
            self.player.consume_consumable(item_id)
            self.player.grant_guard(target_subsystem, amount, turns)
            return (
                True,
                f"SUCCESS: {item_data.get('name', item_id)} reinforced [{target_subsystem}] "
                f"with an ACL shell worth {amount} integrity over {turns} turn(s).",
            )

        if effect == "patch":
            os_core = self.player.subsystems["OS"]
            restored = min(os_core.max_hp - os_core.current_hp, amount)
            had_lock = self.player.clear_ram_lock()
            if restored <= 0 and not had_lock:
                return False, "Error: Core OS is already stable. Save that item for later."
            self.player.consume_consumable(item_id)
            if restored > 0:
                os_core.current_hp += restored
            return (
                True,
                f"SUCCESS: {item_data.get('name', item_id)} restored {restored} Core OS integrity"
                + (" and flushed RAM lock residue." if had_lock else "."),
            )

        if effect == "decoy":
            scrubbed = enemy.scrub_player_recon_stage(item_data.get("scrub_stages", 1))
            self.player.signature_revealed = enemy.player_signature_revealed
            self.player.topology_exposed = enemy.player_topology_revealed
            self.player.consume_consumable(item_id)
            self.player.arm_scan_jammer(item_data.get("jammer_turns", 1))
            message = [
                f"SUCCESS: {item_data.get('name', item_id)} deployed.",
                "         Honeypot decoys are live.",
            ]
            if scrubbed > 0:
                message.append(f"         Hostile recon dropped by {scrubbed} stage(s).")
            return True, "\n".join(message)

        if effect == "tripwire":
            self.player.consume_consumable(item_id)
            self.player.arm_tripwire(target_subsystem, item_data.get("trap_damage", 5), turns)
            return (
                True,
                f"SUCCESS: {item_data.get('name', item_id)} armed on [{target_subsystem}]. "
                "The next hostile commit there will trip the canary.",
            )

        return False, f"Error: Consumable '{item_id}' has an unknown effect."

    def execute_action(self, command_str: str, enemy: Enemy):
        if command_str.strip().lower().startswith("use "):
            success, message = self.execute_item_command(command_str, enemy)
            return type("ActionResult", (), {"success": success, "message": message})()
        return self.arsenal.execute(command_str, self.player, enemy, self.state)

    def print_enemy_action_banner(self, enemy: Enemy):
        print("\n\033[91m[COUNTER-ATTACK]\033[0m")
        print(f"\033[91m{enemy.get_visible_name()} -> {enemy.current_intent['name']}\033[0m")
        print("\033[90m" + "-" * 44 + "\033[0m")
        time.sleep(1.2)

    def build_queue_action_metadata(self, command_str: str):
        lowered = command_str.strip().lower()
        if lowered.startswith("use "):
            try:
                item_id, item_data, target_subsystem = self.parse_item_command(command_str)
            except ValueError:
                return {
                    "label": "FIELD KIT",
                    "kind": "item",
                    "target": "---",
                    "cost": 0,
                    "flags": [],
                }
            return {
                "label": "FIELD KIT",
                "kind": "item",
                "target": target_subsystem or item_data.get("default_target", "---"),
                "cost": 0,
                "flags": [],
                "name": item_data.get("name", item_id),
            }

        try:
            parsed = self.arsenal.parse_command(command_str, owner=self.player)
        except ValueError:
            return {
                "label": "PAYLOAD",
                "kind": "unknown",
                "target": "---",
                "cost": 0,
                "flags": [],
                "name": command_str,
            }

        script_data = self.arsenal.scripts.get(parsed.base_cmd, {})
        script_type = script_data.get("type", "unknown")
        label_map = {
            "scan": "RECON PASS",
            "brute_force": "PRESSURE COMMIT",
            "exploit": "ACCESS COMMIT",
            "utility": "CONTROL COMMIT",
        }
        return {
            "label": label_map.get(script_type, "PAYLOAD"),
            "kind": script_type,
            "target": self.get_resolved_target(parsed, script_data) or "---",
            "cost": self.arsenal.get_command_cost(parsed),
            "flags": list(parsed.flags),
            "name": parsed.base_cmd,
        }

    def print_queue_execution_banner(self, turn_number: int, script_queue: list[str], enemy: Enemy):
        print("\n\033[93m[QUEUE COMMIT]\033[0m")
        print("\033[90m" + "=" * 50 + "\033[0m")
        print(
            f"\033[90mTURN {turn_number:02d} :: {len(script_queue)} payload(s) armed :: "
            f"{self.describe_enemy_posture(enemy)}\033[0m"
        )
        print(
            f"\033[90mRAM WINDOW :: {self.player.current_ram}/{self.player.get_effective_max_ram()} GB "
            "before commit\033[0m"
        )
        print("\033[90m" + "=" * 50 + "\033[0m")
        time.sleep(0.75)

    @staticmethod
    def print_action_report(result):
        if result.success:
            print("\033[95m[IMPACT REPORT]\033[0m")
            print(f"\033[92m{result.message}\033[0m")
        else:
            print("\033[91m[PAYLOAD FAULT]\033[0m")
            print(f"\033[91m{result.message}\033[0m")

    def print_queue_resolution(self, enemy: Enemy):
        print("\n\033[90m" + "-" * 50 + "\033[0m")
        if enemy.subsystems["OS"].current_hp > 0:
            if enemy.has_telemetry_for("OS"):
                print(
                    f"\033[96m[QUEUE RESOLVED]\033[0m Host core still live at "
                    f"{enemy.subsystems['OS'].current_hp}/{enemy.subsystems['OS'].max_hp}."
                )
            else:
                print("\033[96m[QUEUE RESOLVED]\033[0m Host core still live. Exact core integrity remains masked.")
        else:
            print("\033[92m[QUEUE RESOLVED]\033[0m Host core dropped out of the queue window.")
        time.sleep(0.7)

    def run_support_bots(self, turn_number: int, enemy: Enemy):
        ready_bots = [bot for bot in self.player.support_bots if bot.should_trigger(turn_number)]
        if not ready_bots or enemy.subsystems["OS"].current_hp <= 0:
            return False

        print("\n\033[95m[SUPPORT BOTS]\033[0m")
        print("\033[90m" + "-" * 44 + "\033[0m")
        time.sleep(0.6)

        for bot in ready_bots:
            print(f"\033[95m[{bot.name.upper()}]\033[0m {bot.payload}")
            result = self.arsenal.execute(bot.payload, self.player, enemy, self.state)
            if result.success:
                print(f"\033[92m{result.message}\033[0m")
                self.process_exploit_chain(bot.payload, enemy, source="bot")
            else:
                print(f"\033[91m{bot.name} stalled: {result.message}\033[0m")
            time.sleep(1.2)

            if enemy.subsystems["OS"].current_hp <= 0:
                break
        return True

    def describe_enemy_posture(self, enemy: Enemy):
        posture_map = {
            "scan_topology": "RECON ROUTINE (mapping your layout)",
            "scan_signature": "PINPOINT ROUTINE (hunting your weak angle)",
            "repair": "RECOVERY ROUTINE",
            "trace": "TRACE ROUTINE",
            "ram_lock": "CONTROL ROUTINE",
            "attack": "ATTACK ROUTINE",
            "drain": "DRAIN ROUTINE",
            "finisher": "KILL ROUTINE",
            "idle": "IDLE",
        }
        kind = enemy.current_intent.get("kind", "idle")
        return posture_map.get(kind, "UNCLASSIFIED ROUTINE")

    def describe_enemy_recon(self, enemy: Enemy):
        stage = enemy.get_recon_alert_stage()
        if stage == 0:
            return "\033[90m[BREACH STATE]\033[0m cold link :: hostile has not mapped your rig."
        if stage == 1:
            return "\033[93m[BREACH STATE]\033[0m warm link :: hostile has your topology, but not your signature."
        return "\033[91m[BREACH STATE]\033[0m hot link :: hostile fingerprinted your signature and can exploit it."

    def build_round_openers(self, turn_number: int, enemy: Enemy, regen_amount: int):
        notes: list[tuple[str, str]] = []

        if turn_number == 1:
            notes.append(("cyan", "socket live :: first turn on this hostile link"))
        elif regen_amount > 0:
            notes.append(("green", f"mem bus recovered +{regen_amount} RAM into the live pool"))

        if self.player.temp_ram_turns > 0 and self.player.temp_ram_penalty > 0:
            notes.append(
                (
                    "red",
                    f"ram lock persists :: -{self.player.temp_ram_penalty} max RAM for {self.player.temp_ram_turns} more turn(s)",
                )
            )

        active_acl = []
        for key in self.player.DEFENSIVE_TARGETS:
            amount = self.player.guard_banks.get(key, 0)
            turns = self.player.guard_turns.get(key, 0)
            if amount > 0 and turns > 0:
                active_acl.append(f"{key}+{amount}/{turns}t")
        if active_acl:
            notes.append(("cyan", "acl shell active :: " + ", ".join(active_acl[:3])))

        if self.player.scan_jammer_turns > 0:
            notes.append(("magenta", "honeypot live :: next hostile scan will hit planted telemetry"))
        if self.player.tripwire_turns > 0 and self.player.tripwire_target:
            notes.append(
                (
                    "magenta",
                    f"canary armed :: [{self.player.tripwire_target}] for {self.player.tripwire_turns} more turn(s)",
                )
            )
        if self.player.mirror_turns > 0 and self.player.mirror_target:
            notes.append(
                (
                    "magenta",
                    f"sinkhole armed :: [{self.player.mirror_target}] for {self.player.mirror_turns} more turn(s)",
                )
            )

        if enemy.security_breach_turns > 0:
            notes.append(
                (
                    "yellow",
                    f"host perimeter still peeled :: SEC disruption open for {enemy.security_breach_turns} turn(s)",
                )
            )

        if enemy.current_intent.get("name") == "Signal Jammed":
            notes.append(("yellow", "host control loop jammed :: this round's response routine is degraded"))

        adaptation_summary = enemy.get_adaptation_summary()
        if adaptation_summary:
            notes.append(("yellow", f"host adaptation cache :: {adaptation_summary}"))

        ready_bots = [bot.name for bot in self.player.support_bots if bot.should_trigger(turn_number)]
        if ready_bots:
            notes.append(("green", "support bot cadence live :: " + ", ".join(ready_bots[:3])))

        return notes

    def update_planning_snapshot(
        self,
        turn_number: int,
        enemy: Enemy,
        script_queue: list[str],
        regen_amount: int,
        round_openers=None,
    ):
        self.planning_snapshot = {
            "turn_number": turn_number,
            "enemy": enemy,
            "script_queue": list(script_queue),
            "regen_amount": regen_amount,
            "round_openers": list(round_openers or []),
        }

    def clear_planning_snapshot(self):
        self.planning_snapshot = None

    def render_planning_snapshot(self):
        snapshot = self.planning_snapshot
        if not snapshot:
            return

        enemy = snapshot["enemy"]
        script_queue = snapshot["script_queue"]
        regen_amount = snapshot["regen_amount"]
        round_openers = snapshot.get("round_openers", [])

        print("\033[96m[COMBAT LOOP]\033[0m")
        print("\033[90m" + "=" * 50 + "\033[0m")
        if round_openers:
            print("\033[95m[ROUND OPEN]\033[0m")
            tone_map = {
                "red": "\033[91m",
                "green": "\033[92m",
                "yellow": "\033[93m",
                "magenta": "\033[95m",
                "cyan": "\033[96m",
            }
            for tone, text in round_openers:
                print(f"{tone_map.get(tone, '\033[97m')}- {text}\033[0m")
            print("\033[90m" + "-" * 50 + "\033[0m")
        print(f"\033[96m[LIVE HOST]\033[0m {enemy.get_visible_name()}")
        print("\033[90m" + "-" * 50 + "\033[0m")

        if not enemy.intent_revealed:
            print(
                "\033[91m[HOSTILE ACTIVITY]\033[0m \033[90mUnreadable. Live process chatter not yet resolved.\033[0m"
            )
        elif not enemy.telemetry_revealed:
            print(
                f"\033[91m[ENEMY INTENT]\033[0m {enemy.current_intent['name']} "
                "\033[90m(projected damage still masked)\033[0m"
            )
        else:
            damage_preview = enemy.current_intent.get("damage", 0)
            detail = f" (Projected DMG: {damage_preview})" if damage_preview > 0 else ""
            print(f"\033[91m[ENEMY INTENT]\033[0m {enemy.current_intent['name']}{detail}")

        print("\033[90m" + "-" * 50 + "\033[0m")
        if regen_amount > 0:
            print(f"\033[96m[RAM REGEN]\033[0m +{regen_amount} GB recovered from memory buses.")
        print(self.describe_enemy_recon(enemy))

        print("\n\033[95m[SCRIPT BUILDER QUEUE]\033[0m")
        if not script_queue:
            print("  (Empty)")
        else:
            for idx, cmd in enumerate(script_queue, start=1):
                print(f"  {idx}. {cmd}")

    def start_encounter(self, enemy: Enemy, objective_callback=None):
        self.current_enemy = enemy
        self.player.begin_encounter()
        self.state.begin_encounter_tracking()
        self.clear_planning_snapshot()
        self.player.topology_exposed = enemy.player_topology_revealed
        self.player.signature_revealed = enemy.player_signature_revealed
        turn_number = 0

        def update_objective(phase: str):
            if objective_callback:
                objective_callback(phase, enemy, self.player, self.state)

        self.clear_screen()
        print("\n\033[91m[!] WARNING: INITIATING HOSTILE CONNECTION.\033[0m")
        time.sleep(1.4)
        update_objective("intro")

        if enemy.player_signature_revealed:
            print("\033[91m[!] HOT ENTRY: hostile signature lock already established before breach.\033[0m")
            time.sleep(1.3)
        elif enemy.player_topology_revealed:
            print("\033[93m[!] WARM ENTRY: the host already has a rough map of your node.\033[0m")
            time.sleep(1.3)
        else:
            print("\033[92m[+] COLD ENTRY: no hostile lock-on detected. You move first from the dark.\033[0m")
            time.sleep(1.2)

        if enemy.player_crypto_bonus > 0:
            self.state.player_crypto += enemy.player_crypto_bonus
            print(f"\033[92m[+] BACKDOOR EXPLOITED: Siphoned {enemy.player_crypto_bonus} Crypto on entry.\033[0m")
            time.sleep(1.3)

        if enemy.trace_penalty > 0:
            self.state.trace_level += enemy.trace_penalty
            print(f"\033[91m[!] MONITORED NODE: Trace Level increased by {enemy.trace_penalty}.\033[0m")
            time.sleep(1.3)

        if enemy.player_ram_modifier != 0:
            self.player.encounter_ram_modifier = enemy.player_ram_modifier
            if enemy.player_ram_modifier < 0:
                print(
                    f"\033[91m[-] INTERFERENCE: Max RAM restricted by "
                    f"{abs(enemy.player_ram_modifier)} GB for this encounter.\033[0m"
                )
            else:
                print(f"\033[92m[+] OVERCLOCK: Max RAM increased by {enemy.player_ram_modifier} GB.\033[0m")
            time.sleep(1.6)

        self.pause_to_read("[Press Enter to enter the planning loop...]")

        while enemy.subsystems["OS"].current_hp > 0 and self.player.subsystems["OS"].current_hp > 0:
            turn_number += 1
            regen_amount = 0
            if turn_number > 1:
                regen_amount = self.player.regen_ram()
            script_queue = []
            turn_ram = self.player.current_ram
            provisional_ram = turn_ram

            enemy.prep_turn(self.player)
            round_openers = self.build_round_openers(turn_number, enemy, regen_amount)
            update_objective("planning")

            while True:
                self.update_planning_snapshot(turn_number, enemy, script_queue, regen_amount, round_openers)
                self.clear_screen()
                self.render_planning_snapshot()

                cmd_input = input("\nroot@player:~$ ").strip()

                if cmd_input == "execute":
                    if not script_queue:
                        input("\033[93mQueue is empty! Press Enter to continue...\033[0m")
                        continue
                    break

                if cmd_input == "clear":
                    script_queue = []
                    provisional_ram = turn_ram
                    continue

                if cmd_input in {"disconnect", "exit"}:
                    if enemy.disconnect_lock:
                        input("\033[91mDisconnect failed: this node has pinned your socket. Press Enter...\033[0m")
                        continue
                    if not self.player.can_disconnect():
                        input("\033[91mDisconnect failed: your [NET] subsystem is offline. Press Enter...\033[0m")
                        continue
                    result = self.apply_disconnect_penalty(enemy)
                    self.player.end_encounter()
                    self.clear_planning_snapshot()
                    return result

                if not cmd_input:
                    continue

                try:
                    cost = self.get_action_cost(cmd_input)
                except ValueError as exc:
                    input(f"\033[91m{exc} Press Enter...\033[0m")
                    continue

                if provisional_ram < cost:
                    input(
                        f"\033[91mError: Not enough RAM. Needs {cost}, have {provisional_ram}. Press Enter...\033[0m"
                    )
                    continue

                script_queue.append(cmd_input)
                provisional_ram -= cost

            self.clear_screen()
            self.print_queue_execution_banner(turn_number, script_queue, enemy)

            for index, cmd in enumerate(script_queue, start=1):
                cost = self.get_action_cost(cmd)
                self.player.current_ram = max(0, self.player.current_ram - cost)

                meta = self.build_queue_action_metadata(cmd)
                flag_notes = []
                if not cmd.strip().lower().startswith("use "):
                    try:
                        parsed = self.arsenal.parse_command(cmd, owner=self.player)
                    except ValueError:
                        parsed = None
                    if parsed:
                        flag_notes = self.arsenal.describe_flag_stack(parsed, owner=self.player)
                self.play_transient_frames(build_player_action_frames(cmd, meta, enemy, flag_notes))

                enemy_feedback_before = capture_enemy_feedback_state(enemy)
                result = self.execute_action(cmd, enemy)
                feedback_lines = []
                if result.success:
                    feedback_lines = build_action_feedback(
                        meta.get("name", cmd),
                        meta,
                        enemy,
                        enemy_feedback_before,
                        capture_enemy_feedback_state(enemy),
                    )
                self.print_action_output_log(index, len(script_queue), cmd, result, flag_notes, feedback_lines)
                if result.success and not cmd.strip().lower().startswith("use "):
                    self.process_exploit_chain(cmd, enemy)
                self.pause_to_read("[Press Enter to continue execution...]")

                if enemy.subsystems["OS"].current_hp <= 0:
                    break

            bots_ran = self.run_support_bots(turn_number, enemy)
            if bots_ran and enemy.subsystems["OS"].current_hp > 0:
                self.pause_to_read("[Press Enter to close the support-bot pass...]")
            self.print_queue_resolution(enemy)

            if enemy.subsystems["OS"].current_hp <= 0:
                self.clear_screen()
                print("\n\033[91m" + "#" * 50)
                print("##  [!] TARGET CORE OS KERNEL PANIC [!]   ##")
                print("##  [!] CATASTROPHIC SYSTEM FAILURE [!]   ##")
                print("#" * 50 + "\033[0m")
                time.sleep(1.2)
                print(f"\n\033[92m[+] SUCCESS: {enemy.name} completely neutralized.\033[0m")
                print("\033[92m[+] Terminating connection...\033[0m")
                time.sleep(2)
                self.pause_to_read("[Press Enter to sever the link...]")
                update_objective("exit")
                self.player.end_encounter()
                self.clear_planning_snapshot()
                return EncounterResult("victory", enemy.id)

            input("\033[90m[Press Enter for hostile response...]\033[0m")
            self.play_transient_frames(build_enemy_action_frames(enemy))
            lines, reason = enemy.resolve_intent(self.player, self.state)
            self.print_enemy_output_log(enemy, lines)

            if reason == "burn_notice":
                self.player.subsystems["OS"].current_hp = 0
                self.player.subsystems["OS"].is_destroyed = True

            time.sleep(0.35)
            enemy.tick_end_of_turn()
            self.player.tick_end_of_turn()
            update_objective("enemy_turn")
            if enemy.subsystems["OS"].current_hp > 0 and self.player.subsystems["OS"].current_hp > 0:
                input("\033[90m[Press Enter for turn summary...]\033[0m")
                self.print_turn_summary(turn_number, enemy)
                input("\033[90m[Press Enter to plan the next turn...]\033[0m")

        self.player.end_encounter()
        self.clear_planning_snapshot()
        update_objective("exit")

        if self.player.subsystems["OS"].current_hp <= 0:
            print("\n\033[91m[!] FATAL ERROR: Player OS reached 0. SYSTEM CRASH.\033[0m")
            self.state.game_over = True
            self.pause_to_read("[Press Enter to acknowledge the crash...]")
            reason = "burn_notice" if enemy.current_intent.get("kind") == "finisher" else "combat_defeat"
            return EncounterResult("defeat", reason)

        return EncounterResult("unknown")
