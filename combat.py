import os
import time
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from copy import deepcopy

from arsenal import Arsenal
from combat_flavor import CombatFrame, build_enemy_action_frames, build_player_action_frames
from combat_feedback import build_action_feedback, capture_enemy_feedback_state
from entities import Player, Enemy
from game_state import GameState
from ui_runtime_flavor import build_enemy_turn_disturbances
from stack_engine import (
    StackProjection,
    apply_adjacency_window,
    apply_held_damage,
    bank_excess_damage,
    build_projection,
    classify_resolution,
    clear_adjacency_window,
    consume_stack_ram,
    command_target,
    is_item_command,
    next_adjacency_window,
    parse_item_command,
    prime_ram_capsule,
    split_stack,
    simulate_command_delta,
)


@dataclass
class EncounterResult:
    outcome: str
    reason: str = ""
    metadata: dict = field(default_factory=dict)


class CombatEngine:
    def __init__(self, player: Player, arsenal: Arsenal, state: GameState, item_library=None, ui_session=None):
        self.player = player
        self.arsenal = arsenal
        self.state = state
        self.item_library = item_library or {}
        self.ui_session = ui_session
        self.planning_snapshot = None
        self.encounter_resolution = None
        self.turn_phase = "recon"
        self.stack_overflow_ram = 0
        self.ui_window_disturbances = {}
        self.ui_status_override = ""

    def shared_io_lock(self):
        lock = getattr(self.ui_session, "io_lock", None)
        return lock if lock else nullcontext()

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

        result = self.arsenal.execute(command_str, self.player, enemy, self.state, phase="recon")
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
        item_id, item_data, target_subsystem = parse_item_command(command_str, self.item_library, self.player)
        if target_subsystem and target_subsystem not in self.player.subsystems:
            raise ValueError(f"Error: Defensive target [{target_subsystem}] does not exist.")
        return item_id, item_data, target_subsystem

    def get_action_cost(self, command_str: str):
        if command_str.strip().lower().startswith("use "):
            self.parse_item_command(command_str)
            return 0
        return self.arsenal.get_command_cost(command_str, owner=self.player)

    def build_queue_projection(self, script_queue: list[str], enemy: Enemy) -> StackProjection:
        return build_projection(
            script_queue,
            self.arsenal,
            self.player,
            enemy,
            self.state,
            self.item_library,
        )

    def render_dry_run_report(self, projection: StackProjection):
        self.clear_screen()
        print("\n\033[96m[DRY RUN // GHOST STATE]\033[0m")
        print("\033[90m" + "=" * 58 + "\033[0m")
        if not projection.legal and projection.error:
            print(f"\033[91m{projection.error}\033[0m")
        print(
            f"\033[90mSTACK ORDER\033[0m :: "
            f"{' -> '.join(projection.execution_commands) if projection.execution_commands else 'empty'}"
        )
        print("\033[90m" + "-" * 58 + "\033[0m")
        for index, step in enumerate(projection.steps, start=1):
            color = "\033[92m" if step.legal else "\033[91m"
            print(
                f"{color}{index:02d}. [{step.phase.upper():<9}] {step.command}"
                f"  RAM {step.ram_before}->{step.ram_after}\033[0m"
            )
            if step.notes:
                for note in step.notes:
                    print(f"\033[96m    - {note}\033[0m")
            for line in str(step.message).splitlines():
                print(f"\033[90m    {line}\033[0m")
        print("\033[90m" + "-" * 58 + "\033[0m")
        if projection.root_prediction:
            tone = "\033[92m" if projection.root_prediction == "rooted" else "\033[91m"
            print(f"{tone}PREDICTED NODE OUTCOME :: {projection.root_prediction.upper()}\033[0m")
            print(f"\033[90m{projection.root_reason}\033[0m")
        if projection.projected_enemy:
            projected_os = projection.projected_enemy.subsystems["OS"]
            print(
                f"\033[90mHOST CORE AFTER SIM :: {projected_os.current_hp}/{projected_os.max_hp}\033[0m"
            )
        if projection.projected_player:
            print(
                f"\033[90mPLAYER RAM AFTER SIM :: {projection.projected_player.current_ram}/"
                f"{projection.projected_player.get_effective_max_ram()}\033[0m"
            )

    def execute_preflight_item_live(self, command_str: str, enemy: Enemy):
        success, message = self.execute_item_command(command_str, enemy)
        return type("ActionResult", (), {"success": success, "message": message})()

    def execute_item_command(self, command_str: str, enemy: Enemy):
        try:
            item_id, item_data, target_subsystem = self.parse_item_command(command_str)
        except ValueError as exc:
            return False, str(exc)

        effect = item_data.get("effect")
        amount = item_data.get("amount", 0)
        turns = item_data.get("turns", 1)

        if effect == "ram":
            restored, gained_overflow = prime_ram_capsule(self.player, amount)
            if restored <= 0 and gained_overflow <= 0:
                return False, "Error: RAM capsule would have no effect."
            self.player.consume_consumable(item_id)
            self.stack_overflow_ram += gained_overflow
            parts = [f"SUCCESS: {item_data.get('name', item_id)} injected."]
            if restored > 0:
                parts.append(f"Added +{restored} live RAM.")
            if gained_overflow > 0:
                parts.append(f"Primed +{gained_overflow} overflow RAM for the next payload.")
            return True, " ".join(parts)

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
        return self.arsenal.execute(command_str, self.player, enemy, self.state, phase="combat")

    @staticmethod
    def resolve_player_subsystem_token(token: str | None):
        if not token:
            return "OS"
        key = token.strip().upper()
        aliases = {
            "CORE": "OS",
            "FIREWALL": "SEC",
            "PROXY": "NET",
            "MEMORY": "MEM",
            "STORAGE": "STO",
        }
        key = aliases.get(key, key)
        if key not in {"OS", "SEC", "NET", "MEM", "STO"}:
            raise ValueError("Subsystem must be one of OS, SEC, NET, MEM, or STO.")
        return key

    def execute_player_turn_action(self, command_str: str):
        parts = command_str.strip().split()
        action = parts[0].lower() if parts else ""
        target_token = parts[1] if len(parts) > 1 else None

        if action in {"wait", "pass"}:
            return {
                "success": True,
                "label": "HOLD",
                "message": (
                    "You keep the socket quiet, commit no exploit traffic, and let the hostile side move first.\n"
                    "No RAM is spent. Memory recovery will happen at the start of your next turn."
                ),
            }

        target_key = self.resolve_player_subsystem_token(target_token)
        subsystem = self.player.subsystems[target_key]

        if action == "defend":
            self.player.grant_guard(target_key, 4, turns=1)
            return {
                "success": True,
                "label": "DEFEND",
                "message": (
                    f"ACL shell braced around [{target_key}].\n"
                    "The next hostile commit into that lane has to punch through the shell first."
                ),
            }

        if action == "repair":
            progression_tier = self.state.get_progression_tier() if self.state and hasattr(self.state, "get_progression_tier") else 0
            repair_bonus = min(3, progression_tier)
            restore_amount = (3 if target_key == "OS" else 4) + repair_bonus
            restored = subsystem.repair(restore_amount)
            if restored <= 0:
                return {
                    "success": False,
                    "label": "REPAIR",
                    "message": f"[{target_key}] is already stable. No repair work was needed.",
                }
            return {
                "success": True,
                "label": "REPAIR",
                "message": (
                    f"Manual maintenance pushed {restored} integrity back into [{target_key}].\n"
                    "It is slow, but it keeps damaged lanes from staying dead forever."
                ),
            }

        raise ValueError("Unknown turn action.")

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
        print(
            "\033[90mSTACK RESOLVE :: queued payloads resolve in order // inline injectors hold position // immediate-neighbor syntheses only\033[0m"
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

        for notice in self.player.consume_hardening_notices():
            notes.append(("cyan", notice))
        hardening_summary = self.player.get_hardening_summary()
        if hardening_summary:
            notes.append(("cyan", f"pattern cache :: {hardening_summary}"))

        if enemy.security_breach_turns > 0:
            notes.append(
                (
                    "yellow",
                    f"host perimeter still peeled :: SEC disruption open for {enemy.security_breach_turns} turn(s)",
                )
            )

        if enemy.current_intent.get("name") == "Signal Jammed":
            notes.append(("yellow", "host control loop jammed :: this round's response routine is degraded"))

        for notice in enemy.consume_patch_notices():
            notes.append(("red", f"host patch applied :: {notice}"))

        adaptation_summary = enemy.get_adaptation_summary()
        if adaptation_summary:
            notes.append(("yellow", f"host adaptation cache :: {adaptation_summary}"))

        ready_bots = [bot.name for bot in self.player.support_bots if bot.should_trigger(turn_number)]
        if ready_bots:
            notes.append(("green", "support bot cadence live :: " + ", ".join(ready_bots[:3])))

        held_summary = enemy.get_hold_buffer_summary()
        if held_summary != "none":
            notes.append(("magenta", f"staged charge live :: {held_summary}"))

        return notes

    def build_soft_engage_readback(self, enemy: Enemy):
        lines = []
        intent = enemy.current_intent or {}
        intent_name = intent.get("name", "Unknown Routine")
        target = intent.get("target")
        lane = f"[{target}]" if target else "route-wide"
        lines.append(f"opening response :: {intent_name} against {lane}")
        lines.append(f"link state :: {enemy.get_recon_alert_text()}")

        patch_summary = enemy.get_adaptation_summary()
        if patch_summary:
            lines.append(f"active patches :: {patch_summary}")
        else:
            lines.append("active patches :: none observed on this host yet")

        attack_lanes = []
        family_map = {
            "attack": "direct pressure",
            "drain": "data siphon",
            "trace": "forensics",
            "ram_lock": "control lock",
            "strip_defense": "defense breaker",
            "finisher": "kill chain",
            "scan_topology": "topology scan",
            "scan_signature": "signature scan",
        }
        families = []
        for ability in enemy.abilities:
            target_key = ability.get("target")
            if target_key and target_key not in attack_lanes:
                attack_lanes.append(target_key)
            family = family_map.get(ability.get("kind"))
            if family and family not in families:
                families.append(family)

        if attack_lanes:
            lines.append("observed lanes :: " + ", ".join(f"[{lane_key}]" for lane_key in attack_lanes[:5]))
        if families:
            lines.append("host toolkit :: " + ", ".join(families[:5]))
        return lines

    def update_planning_snapshot(
        self,
        turn_number: int,
        enemy: Enemy,
        script_queue: list[str],
        regen_amount: int,
        round_openers=None,
    ):
        projection = self.build_queue_projection(script_queue, enemy)
        with self.shared_io_lock():
            self.planning_snapshot = {
                "turn_number": turn_number,
                "enemy": enemy,
                "script_queue": list(script_queue),
                "regen_amount": regen_amount,
                "round_openers": list(round_openers or []),
                "projection": projection,
            }

    def clear_planning_snapshot(self):
        with self.shared_io_lock():
            self.planning_snapshot = None

    def clear_ui_disturbances(self):
        with self.shared_io_lock():
            self.ui_window_disturbances = {}
            self.ui_status_override = ""

    def set_enemy_turn_ui_disturbances(self, enemy: Enemy):
        disturbances, status_override = build_enemy_turn_disturbances(enemy)
        with self.shared_io_lock():
            self.ui_window_disturbances = disturbances
            self.ui_status_override = status_override

    def render_planning_snapshot(self):
        with self.shared_io_lock():
            snapshot = deepcopy(self.planning_snapshot)
        if not snapshot:
            return

        enemy = snapshot["enemy"]
        script_queue = snapshot["script_queue"]
        regen_amount = snapshot["regen_amount"]
        round_openers = snapshot.get("round_openers", [])

        print("\033[96m[COMBAT LOOP]\033[0m")
        print("\033[90m" + "=" * 50 + "\033[0m")
        print("\033[90mPHASE :: ENGAGE STACK\033[0m")
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

        print("\n\033[95m[EXPLOIT STACK]\033[0m")
        if not script_queue:
            print("  (Empty)")
        else:
            for idx, cmd in enumerate(script_queue):
                print(f"   {idx}. {cmd}")

    def run_enemy_response(self, enemy: Enemy):
        self.set_enemy_turn_ui_disturbances(enemy)
        self.play_transient_frames(build_enemy_action_frames(enemy))
        lines, reason = enemy.resolve_intent(self.player, self.state)
        self.print_enemy_output_log(enemy, lines)

        if reason == "burn_notice":
            self.player.subsystems["OS"].current_hp = 0
            self.player.subsystems["OS"].is_destroyed = True

        time.sleep(0.35)
        enemy.tick_end_of_turn()
        self.player.tick_end_of_turn()
        self.clear_ui_disturbances()
        return lines, reason

    def run_soft_engage(self, enemy: Enemy):
        self.turn_phase = "recon"
        self.clear_planning_snapshot()
        self.clear_ui_disturbances()
        enemy.prep_turn(self.player)
        enemy.intent_revealed = True
        enemy.identity_revealed = True
        enemy.weapon_revealed = True

        self.clear_screen()
        print("\n\033[93m[SOFT ENGAGE]\033[0m")
        print("\033[90m" + "=" * 54 + "\033[0m")
        print("\033[90mYou feather the socket, let the host answer first, and read the response before committing your own stack.\033[0m")
        print(f"\033[91mHOST\033[0m :: {enemy.get_visible_name()}    \033[91mROUTINE\033[0m :: {enemy.current_intent.get('name', 'Idle')}")
        print("\033[90m" + "-" * 54 + "\033[0m")
        self.pause_to_read("[Press Enter to take the opening volley...]")

        self.run_enemy_response(enemy)
        if self.player.subsystems["OS"].current_hp <= 0:
            self.state.game_over = True
            self.pause_to_read("[Press Enter to acknowledge the crash...]")
            return False, []

        intel_lines = self.build_soft_engage_readback(enemy)
        self.pause_to_read("[Press Enter for the soft-engage readback...]")
        self.clear_screen()
        print("\n\033[96m[SOFT-ENGAGE READBACK]\033[0m")
        print("\033[90m" + "=" * 54 + "\033[0m")
        for line in intel_lines:
            print(f"\033[96m- {line}\033[0m")
        self.pause_to_read("[Press Enter to return to the passive tap...]")
        return True, intel_lines

    def start_encounter(self, enemy: Enemy, objective_callback=None):
        self.current_enemy = enemy
        self.player.begin_encounter()
        self.player.enable_adaptive_hardening(bool(self.state and self.state.has_meta("pattern_cache")))
        self.state.begin_encounter_tracking()
        self.clear_planning_snapshot()
        self.player.topology_exposed = enemy.player_topology_revealed
        self.player.signature_revealed = enemy.player_signature_revealed
        self.encounter_resolution = None
        turn_number = 0
        self.clear_ui_disturbances()
        encounter_metadata = {
            "worm_seed": 0,
            "worm_source": None,
            "bus_splash_events": 0,
            "bus_splash_damage": 0,
        }

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
            self.clear_ui_disturbances()
            regen_amount = 0
            if turn_number > 1:
                regen_amount = self.player.regen_ram()
            script_queue = []
            self.stack_overflow_ram = 0
            turn_action = None

            enemy.prep_turn(self.player)
            round_openers = self.build_round_openers(turn_number, enemy, regen_amount)
            update_objective("planning")
            self.turn_phase = "engage"

            while True:
                self.update_planning_snapshot(turn_number, enemy, script_queue, regen_amount, round_openers)
                self.clear_screen()
                self.render_planning_snapshot()

                cmd_input = input("\nroot@player:~$ ").strip()

                if cmd_input == "execute":
                    if not script_queue:
                        input("\033[93mQueue is empty! Press Enter to continue...\033[0m")
                        continue
                    projection = self.build_queue_projection(script_queue, enemy)
                    if not projection.legal:
                        input(f"\033[91m{projection.error} Press Enter...\033[0m")
                        continue
                    break

                if cmd_input == "dry_run":
                    if not self.state.has_meta("dry_run"):
                        input("\033[93mSandbox access not unlocked on this rig. Press Enter...\033[0m")
                        continue
                    if not script_queue:
                        input("\033[93mQueue is empty! Press Enter to continue...\033[0m")
                        continue
                    projection = self.build_queue_projection(script_queue, enemy)
                    self.render_dry_run_report(projection)
                    self.pause_to_read("[Press Enter to return to the live stack...]")
                    continue

                if cmd_input == "clear":
                    script_queue = []
                    continue

                if cmd_input in {"wait", "pass"}:
                    if script_queue:
                        input("\033[93mQuiet turn actions can only be used with an empty stack. Press Enter...\033[0m")
                        continue
                    turn_action = cmd_input
                    break

                if cmd_input.startswith("defend") or cmd_input.startswith("repair"):
                    if script_queue:
                        input("\033[93mManual turn actions can only be used with an empty stack. Press Enter...\033[0m")
                        continue
                    try:
                        parts = cmd_input.split()
                        if parts[0] == "defend":
                            self.resolve_player_subsystem_token(parts[1] if len(parts) > 1 else None)
                        elif parts[0] == "repair":
                            self.resolve_player_subsystem_token(parts[1] if len(parts) > 1 else None)
                    except ValueError as exc:
                        input(f"\033[91m{exc} Press Enter...\033[0m")
                        continue
                    turn_action = cmd_input
                    break

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
                    self.clear_ui_disturbances()
                    return result

                if not cmd_input:
                    continue

                prospective_queue = [*script_queue, cmd_input]
                projection = self.build_queue_projection(prospective_queue, enemy)
                if not projection.legal:
                    input(f"\033[91m{projection.error} Press Enter...\033[0m")
                    continue

                script_queue = prospective_queue
                self.update_planning_snapshot(turn_number, enemy, script_queue, regen_amount, round_openers)
                continue

            if turn_action:
                self.clear_screen()
                action_result = self.execute_player_turn_action(turn_action)
                print(f"\n\033[96m[{action_result['label']}]\033[0m")
                print("\033[90m" + "=" * 54 + "\033[0m")
                print(action_result["message"])
                self.pause_to_read("[Press Enter to commit the quiet turn...]")
                bots_ran = False
            else:
                self.clear_screen()
                self.print_queue_execution_banner(turn_number, script_queue, enemy)
            execution_commands = list(script_queue)
            step_total = len(execution_commands)
            step_index = 0
            resolved_stack_actions = []

            pending_window = None
            pending_stager_target = None
            pending_buffer_target = None
            execution_queue = list(execution_commands)
            queue_index = 0
            while not turn_action and queue_index < len(execution_queue):
                cmd = execution_queue[queue_index]
                step_index += 1
                if is_item_command(cmd):
                    meta = self.build_queue_action_metadata(cmd)
                    flag_notes = []
                    if pending_window:
                        source = pending_window.get("source", "adjacency")
                        flag_notes.append(f"{source} window expired before a live payload consumed it")
                    clear_adjacency_window(enemy, pending_window)
                    pending_window = None
                    if pending_stager_target:
                        flag_notes.append(
                            f"stager window on [{pending_stager_target}] expired without a matching adjacent offensive payload"
                        )
                        pending_stager_target = None
                    if pending_buffer_target:
                        flag_notes.append(
                            f"buffer window on [{pending_buffer_target}] expired without a matching adjacent offensive payload"
                        )
                        pending_buffer_target = None
                    self.play_transient_frames(build_player_action_frames(cmd, meta, enemy, flag_notes))
                    result = self.execute_preflight_item_live(cmd, enemy)
                    self.print_action_output_log(step_index, step_total, cmd, result, flag_notes, [])
                    self.pause_to_read("[Press Enter to continue execution...]")
                    if enemy.subsystems["OS"].current_hp <= 0:
                        break
                    queue_index += 1
                    continue
                parsed = None
                try:
                    parsed, script_data, target_subsystem = command_target(self.arsenal, cmd, self.player)
                except ValueError as exc:
                    result = type("ActionResult", (), {"success": False, "message": str(exc)})()
                    self.print_action_output_log(step_index, step_total, cmd, result, [], [])
                    self.pause_to_read("[Press Enter to continue execution...]")
                    queue_index += 1
                    continue

                cost = self.arsenal.get_command_cost(parsed)
                overflow_spent, base_spent, overflow_lost = consume_stack_ram(
                    self.player,
                    cost,
                    self.stack_overflow_ram,
                )
                self.stack_overflow_ram = 0

                meta = self.build_queue_action_metadata(cmd)
                flag_notes = []
                if parsed:
                    flag_notes = self.arsenal.describe_flag_stack(parsed, owner=self.player)
                if overflow_spent > 0:
                    flag_notes.append(f"overflow reserve committed {overflow_spent} RAM into this payload")
                if base_spent > 0:
                    flag_notes.append(f"live pool committed {base_spent} RAM into this payload")
                if overflow_lost > 0:
                    flag_notes.append(f"unused overflow reserve {overflow_lost} dissipated after commit")
                self.play_transient_frames(build_player_action_frames(cmd, meta, enemy, flag_notes))

                feedback_lines = []
                feedback_lines.extend(apply_held_damage(enemy, target_subsystem) if target_subsystem else [])
                if enemy.subsystems["OS"].current_hp <= 0 and not self.encounter_resolution:
                    self.encounter_resolution = {
                        "state": "bricked",
                        "reason": "stored detonation cooked the core before a live finish landed",
                        "command": "held-charge",
                    }
                    result = type(
                        "ActionResult",
                        (),
                        {
                            "success": True,
                            "message": (
                                "SUCCESS: Staged charge detonated before the live payload committed.\n"
                                "         The buffered pressure collapsed the hostile core by delayed blast."
                            ),
                        },
                    )()
                    self.print_action_output_log(step_index, step_total, cmd, result, flag_notes, feedback_lines)
                    self.pause_to_read("[Press Enter to continue execution...]")
                    break

                feedback_lines.extend(apply_adjacency_window(enemy, pending_window, target_subsystem))
                pre_enemy = deepcopy(enemy)
                enemy_feedback_before = capture_enemy_feedback_state(enemy)
                executed_live = False
                metadata = {}
                stager_consumed = False
                buffer_consumed = False

                if parsed.base_cmd == "jmp":
                    if queue_index + 2 < len(execution_queue):
                        first = execution_queue[queue_index + 1]
                        second = execution_queue[queue_index + 2]
                        execution_queue[queue_index + 1], execution_queue[queue_index + 2] = second, first
                        result = type(
                            "ActionResult",
                            (),
                            {
                                "success": True,
                                "message": (
                                    "SUCCESS: Branch shim rewired the local stack.\n"
                                    f"         '{second}' will now resolve before '{first}'."
                                ),
                            },
                        )()
                    else:
                        result = type(
                            "ActionResult",
                            (),
                            {
                                "success": True,
                                "message": (
                                    "SUCCESS: Branch shim resolved, but no full two-payload window remained to swap."
                                ),
                            },
                        )()
                elif parsed.base_cmd == "stager":
                    pending_stager_target = target_subsystem
                    result = type(
                        "ActionResult",
                        (),
                        {
                            "success": True,
                            "message": (
                                f"SUCCESS: Deferred-detonation buffer armed on [{target_subsystem}].\n"
                                "         The next adjacent offensive payload on that lane can be banked instead of landing immediately."
                            ),
                        },
                    )()
                elif parsed.base_cmd == "buffer":
                    pending_buffer_target = target_subsystem
                    result = type(
                        "ActionResult",
                        (),
                        {
                            "success": True,
                            "message": (
                                f"SUCCESS: Containment buffer armed on [{target_subsystem}].\n"
                                "         The next adjacent offensive payload on that lane will trap excess damage instead of dumping it into the hardware."
                            ),
                        },
                    )()
                elif (
                    pending_stager_target
                    and target_subsystem == pending_stager_target
                    and script_data.get("type") in {"brute_force", "exploit"}
                ):
                    shadow_result, delta = simulate_command_delta(self.arsenal, cmd, self.player, enemy, self.state)
                    stored = max(0, delta.get(target_subsystem, 0))
                    feedback_lines.extend(bank_excess_damage(enemy, target_subsystem, stored, source="stager"))
                    pending_stager_target = None
                    stager_consumed = True
                    metadata = getattr(shadow_result, "metadata", {}) or {}
                    if shadow_result.success:
                        result = type(
                            "ActionResult",
                            (),
                            {
                                "success": True,
                                "message": (
                                    f"SUCCESS: {parsed.base_cmd} was intercepted by the stager on [{target_subsystem}].\n"
                                    f"         Deferred charge stored: {stored} damage."
                                ),
                            },
                        )()
                    else:
                        result = type("ActionResult", (), {"success": False, "message": shadow_result.message})()
                else:
                    result = self.execute_action(cmd, enemy)
                    executed_live = True
                    metadata = getattr(result, "metadata", {}) or {}
                    if (
                        pending_buffer_target
                        and target_subsystem == pending_buffer_target
                        and script_data.get("type") in {"brute_force", "exploit"}
                    ):
                        contained = max(0, int(metadata.get("overkill_damage", 0)))
                        if contained > 0:
                            metadata["contained_overkill"] = contained
                            feedback_lines.extend(bank_excess_damage(enemy, target_subsystem, contained, source="buffer"))
                        else:
                            feedback_lines.append(
                                f"buffer on [{target_subsystem}] found no excess pressure to trap."
                            )
                        pending_buffer_target = None
                        buffer_consumed = True
                    if metadata.get("worm_seed", 0) > 0:
                        encounter_metadata["worm_seed"] = max(encounter_metadata["worm_seed"], metadata.get("worm_seed", 0))
                        if metadata.get("worm_source"):
                            encounter_metadata["worm_source"] = metadata["worm_source"]
                    encounter_metadata["bus_splash_events"] += metadata.get("bus_splash_events", 0)
                    encounter_metadata["bus_splash_damage"] += metadata.get("bus_splash_damage", 0)

                if pending_stager_target and parsed.base_cmd != "stager" and not stager_consumed:
                    feedback_lines.append(
                        f"stager window on [{pending_stager_target}] expired without a matching adjacent offensive payload."
                    )
                    pending_stager_target = None
                if pending_buffer_target and parsed.base_cmd != "buffer" and not buffer_consumed:
                    feedback_lines.append(
                        f"buffer window on [{pending_buffer_target}] expired without a matching adjacent offensive payload."
                    )
                    pending_buffer_target = None

                clear_adjacency_window(enemy, pending_window)
                pending_window = next_adjacency_window(self.arsenal, cmd, self.player)

                if result.success and executed_live:
                    feedback_lines.extend(
                        build_action_feedback(
                            meta.get("name", cmd),
                            meta,
                            enemy,
                            enemy_feedback_before,
                            capture_enemy_feedback_state(enemy),
                        )
                    )

                if not self.encounter_resolution:
                    resolution, reason = classify_resolution(cmd, parsed, pre_enemy, enemy, metadata)
                    if resolution:
                        self.encounter_resolution = {
                            "state": resolution,
                            "reason": reason,
                            "command": cmd,
                        }

                self.print_action_output_log(step_index, step_total, cmd, result, flag_notes, feedback_lines)
                if result.success and executed_live:
                    self.process_exploit_chain(cmd, enemy)
                if result.success and parsed:
                    resolved_stack_actions.append(
                        {
                            "script_name": parsed.base_cmd,
                            "target": target_subsystem,
                            "flags": list(parsed.flags),
                            "payload_dna": self.arsenal.get_payload_dna(parsed, owner=self.player),
                            "script_type": script_data.get("type", "unknown"),
                        }
                    )
                self.pause_to_read("[Press Enter to continue execution...]")

                if enemy.subsystems["OS"].current_hp <= 0:
                    break
                queue_index += 1

            if resolved_stack_actions:
                enemy.observe_player_stack(resolved_stack_actions)

            if not turn_action:
                bots_ran = self.run_support_bots(turn_number, enemy)
                if bots_ran and enemy.subsystems["OS"].current_hp > 0:
                    self.pause_to_read("[Press Enter to close the support-bot pass...]")
                self.print_queue_resolution(enemy)

            if enemy.subsystems["OS"].current_hp <= 0:
                self.clear_screen()
                resolution = self.encounter_resolution or {
                    "state": "bricked",
                    "reason": "core fell without a clean takeover signature",
                    "command": "unknown",
                }
                banner_color = "\033[92m" if resolution["state"] == "rooted" else "\033[91m"
                banner_label = "ROOT ACCESS ESTABLISHED" if resolution["state"] == "rooted" else "NODE BRICKED"
                print(f"\n{banner_color}" + "#" * 50)
                print(f"##  {banner_label:^42}  ##")
                print("#" * 50 + "\033[0m")
                time.sleep(1.2)
                if resolution["state"] == "rooted":
                    print(f"\n\033[92m[+] SUCCESS: clean takeover on {enemy.name}.\033[0m")
                else:
                    print(f"\n\033[91m[!] RESULT: {enemy.name} was bricked during the breach.\033[0m")
                print(f"\033[90m[RESOLUTION] {resolution['reason']}\033[0m")
                print("\033[92m[+] Terminating connection...\033[0m")
                time.sleep(2)
                self.pause_to_read("[Press Enter to sever the link...]")
                update_objective("exit")
                self.player.end_encounter()
                self.clear_planning_snapshot()
                self.clear_ui_disturbances()
                return EncounterResult("victory", resolution["state"], metadata=encounter_metadata)

            if not turn_action:
                input("\033[90m[Press Enter for hostile response...]\033[0m")
            self.turn_phase = "engage"
            lines, reason = self.run_enemy_response(enemy)
            update_objective("enemy_turn")
            if enemy.subsystems["OS"].current_hp > 0 and self.player.subsystems["OS"].current_hp > 0:
                self.turn_phase = "cleanup"
                update_objective("cleanup")
                input("\033[90m[Press Enter for turn summary...]\033[0m")
                self.print_turn_summary(turn_number, enemy)
                input("\033[90m[Press Enter to plan the next turn...]\033[0m")

        self.player.end_encounter()
        self.clear_planning_snapshot()
        self.clear_ui_disturbances()
        update_objective("exit")

        if self.player.subsystems["OS"].current_hp <= 0:
            print("\n\033[91m[!] FATAL ERROR: Player OS reached 0. SYSTEM CRASH.\033[0m")
            self.state.game_over = True
            self.pause_to_read("[Press Enter to acknowledge the crash...]")
            reason = "burn_notice" if enemy.current_intent.get("kind") == "finisher" else "combat_defeat"
            return EncounterResult("defeat", reason, metadata=encounter_metadata)

        return EncounterResult("unknown", metadata=encounter_metadata)
