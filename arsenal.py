import random
from dataclasses import dataclass

from payload_dna import build_payload_signature, merge_payload_dna, normalize_payload_dna


class CommandResult:
    def __init__(self, success: bool, message: str, metadata: dict | None = None):
        self.success = success
        self.message = message
        self.metadata = metadata or {}


@dataclass
class ParsedCommand:
    raw: str
    base_cmd: str
    flags: list
    target_subsystem: str | None
    has_target: bool


class Arsenal:
    def __init__(self, arsenal_data: dict):
        self.scripts = arsenal_data.get("scripts", {}) if arsenal_data else {}
        self.flags = arsenal_data.get("flags", {}) if arsenal_data else {}
        self.alias_map = {}
        for command_name, script_data in self.scripts.items():
            script_data["_dna"] = normalize_payload_dna(script_data.get("dna"))
        for flag_name, flag_data in self.flags.items():
            flag_data["_dna"] = normalize_payload_dna(flag_data.get("dna"))
        for command_name, script_data in self.scripts.items():
            for alias in script_data.get("aliases", []):
                self.alias_map[alias] = command_name

    def resolve_script_name(self, command_name: str):
        return self.alias_map.get(command_name, command_name)

    def get_owned_allowed_flags(self, script_name: str, owner=None):
        allowed_flags = list(self.scripts.get(script_name, {}).get("allowed_flags", []))
        if owner and hasattr(owner, "owns_flag"):
            allowed_flags = [flag for flag in allowed_flags if owner.owns_flag(flag)]
        return allowed_flags

    def get_script_dna(self, script_name: str) -> dict[str, tuple[str, ...]]:
        return dict(self.scripts.get(script_name, {}).get("_dna") or normalize_payload_dna(None))

    def get_flag_dna(self, flag_name: str) -> dict[str, tuple[str, ...]]:
        return dict(self.flags.get(flag_name, {}).get("_dna") or normalize_payload_dna(None))

    def get_payload_dna(self, command: ParsedCommand | str, owner=None) -> dict[str, tuple[str, ...]]:
        parsed = command if isinstance(command, ParsedCommand) else self.parse_command(command, owner=owner)
        dna_records = [self.get_script_dna(parsed.base_cmd)]
        dna_records.extend(self.get_flag_dna(flag) for flag in parsed.flags)
        return merge_payload_dna(*dna_records)

    def describe_flag_stack(self, command: ParsedCommand | str, owner=None) -> list[str]:
        parsed = command if isinstance(command, ParsedCommand) else self.parse_command(command, owner=owner)
        if not parsed.flags:
            return []

        script_data = self.scripts.get(parsed.base_cmd, {})
        script_type = script_data.get("type", "tool")
        notes = []
        for flag in parsed.flags:
            data = self.flags.get(flag, {})
            if flag == "--ransom":
                notes.append("--ransom -> wraps landed damage into Crypto payout.")
            elif flag == "--stealth":
                if script_type == "scan":
                    exposure = abs(data.get("exposure_delta", 15))
                    notes.append(f"--stealth -> lowers recon exposure by {exposure}.")
                else:
                    notes.append("--stealth -> lowers observable traffic if the payload stays masked.")
            elif flag == "--ghost":
                exposure = abs(data.get("exposure_delta", 10))
                notes.append(f"--ghost -> light OPSEC wrapper, recon exposure {exposure} lower.")
            elif flag == "--worm":
                notes.append("--worm -> residual damage propagates if the first lane collapses.")
            elif flag == "--burst":
                notes.append(
                    f"--burst -> +{data.get('damage_bonus', 0)} damage, +{data.get('noise_bonus', 0)} trace noise."
                )
            elif flag == "--fork":
                notes.append("--fork -> a secondary thread spills pressure into a second live subsystem.")
            elif flag == "--volatile":
                notes.append(
                    f"--volatile -> unsafe overclock: +{data.get('damage_bonus', 0)} damage, "
                    f"+{data.get('noise_bonus', 0)} trace noise."
                )
            elif flag == "--cascade":
                notes.append("--cascade -> forces extra spillover through adjacent subsystem buses.")
            else:
                notes.append(f"{flag} -> modifier armed.")
        return notes

    def parse_command(self, command_str: str, owner=None) -> ParsedCommand:
        tokens = command_str.strip().split()
        if not tokens:
            raise ValueError("Error: No command entered.")

        base_cmd = self.resolve_script_name(tokens[0])
        if base_cmd not in self.scripts:
            raise ValueError(f"Error: Command '{base_cmd}' not recognized.")
        if owner and hasattr(owner, "owns_script") and not owner.owns_script(base_cmd):
            raise ValueError(f"Error: Payload '{base_cmd}' is not installed on this rig.")

        script_data = self.scripts[base_cmd]
        flags = []
        target_subsystem = None
        idx = 1

        while idx < len(tokens):
            token = tokens[idx]
            if token == "-target":
                if idx + 1 >= len(tokens):
                    raise ValueError("Error: '-target' requires a subsystem name.")
                target_subsystem = tokens[idx + 1].upper()
                idx += 2
                continue

            if token.startswith("--"):
                if token not in self.flags:
                    raise ValueError(f"Error: Flag '{token}' not recognized.")
                if owner and hasattr(owner, "owns_flag") and not owner.owns_flag(token):
                    raise ValueError(f"Error: Flag '{token}' is not installed on this rig.")
                if token in flags:
                    raise ValueError(f"Error: Flag '{token}' provided more than once.")
                flags.append(token)
                idx += 1
                continue

            raise ValueError(f"Error: Unexpected token '{token}'.")

        supports_target = script_data.get("supports_target", True)
        if target_subsystem and not supports_target:
            raise ValueError(f"Error: Command '{base_cmd}' does not accept '-target'.")

        if not target_subsystem and script_data.get("default_target"):
            target_subsystem = script_data["default_target"].upper()

        allowed_flags = script_data.get("allowed_flags")
        if allowed_flags is not None:
            invalid_flags = [flag for flag in flags if flag not in allowed_flags]
            if invalid_flags:
                raise ValueError(
                    f"Error: {base_cmd} does not support {' ,'.join(invalid_flags)}.".replace(" ,", ", ")
                )

        return ParsedCommand(
            raw=command_str,
            base_cmd=base_cmd,
            flags=flags,
            target_subsystem=target_subsystem,
            has_target=target_subsystem is not None,
        )

    def get_command_cost(self, command: ParsedCommand | str, owner=None):
        parsed = command if isinstance(command, ParsedCommand) else self.parse_command(command, owner=owner)
        cost = self.scripts[parsed.base_cmd]["ram"]
        for flag in parsed.flags:
            cost += self.flags[flag]["ram"]
        return cost

    def get_resolved_target(self, parsed: ParsedCommand):
        script_data = self.scripts.get(parsed.base_cmd, {})
        if parsed.target_subsystem:
            return parsed.target_subsystem
        default_target = script_data.get("default_target")
        if default_target:
            return str(default_target).upper()
        if script_data.get("type") in {"brute_force", "exploit"}:
            return "OS"
        return None

    def build_attack_profile(self, parsed: ParsedCommand, player, enemy, game_state=None):
        script_data = self.scripts[parsed.base_cmd]
        script_type = script_data.get("type", "unknown")
        target_subsystem = self.get_resolved_target(parsed) or "OS"
        payload_dna = self.get_payload_dna(parsed)

        if target_subsystem not in enemy.subsystems:
            raise ValueError(f"Error: Target subsystem [{target_subsystem}] does not exist.")

        target = enemy.subsystems[target_subsystem]
        if target.is_destroyed:
            raise ValueError(f"Error: Target [{target_subsystem}] is already offline.")

        base_damage = script_data.get("damage", 0)
        is_weakness = target_subsystem == enemy.weakness

        base_damage += sum(self.flags.get(flag, {}).get("damage_bonus", 0) for flag in parsed.flags)

        if parsed.base_cmd == "ping":
            if target_subsystem == "NET":
                base_damage += 1
        elif parsed.base_cmd == "masscan":
            base_damage = 0
        elif parsed.base_cmd == "hydra":
            if enemy.has_auth_surface(target_subsystem):
                base_damage += 3
            else:
                base_damage = max(1, base_damage - 3)
            if enemy.has_credential_pressure(target_subsystem):
                base_damage += 2
        elif parsed.base_cmd == "ddos":
            if target_subsystem in {"NET", "SEC"}:
                base_damage += 2
            botnet_power = game_state.get_domain_botnet_power() if game_state and hasattr(game_state, "get_domain_botnet_power") else 0
            if botnet_power > 0:
                base_damage += botnet_power * 2
        elif parsed.base_cmd == "sqlmap" and (
            target_subsystem in {"MEM", "STO"}
            or enemy.has_db_surface(target_subsystem)
            or enemy.has_web_surface(target_subsystem)
        ):
            base_damage += 2
            if enemy.has_endpoint_hits(target_subsystem):
                base_damage += 2
        elif parsed.base_cmd == "siphon" and (
            target_subsystem in {"MEM", "STO"} or enemy.has_db_surface(target_subsystem)
        ):
            base_damage += 2
        elif parsed.base_cmd == "overflow" and target_subsystem in {"MEM", "NET"}:
            base_damage += 2
        elif parsed.base_cmd == "shred" and target.current_hp <= max(1, target.max_hp // 2):
            base_damage += 3
        elif parsed.base_cmd == "spray" and (target_subsystem in {"SEC", "NET"} or enemy.has_auth_surface(target_subsystem)):
            base_damage += 2
        elif parsed.base_cmd == "hammer" and target_subsystem == "OS" and enemy.subsystems["SEC"].is_destroyed:
            base_damage += 2

        if is_weakness:
            base_damage *= 2

        adaptive_block, adaptive_reasons = enemy.get_adaptive_mitigation(
            parsed.base_cmd,
            script_type,
            target_subsystem,
            parsed.flags,
            payload_dna,
        )
        timing_bonus = 0
        fingerprint_bonus = 0
        adaptive_soften = 0
        if script_type in {"brute_force", "exploit"} and parsed.base_cmd != "ping" and enemy.get_timing_window(target_subsystem) > 0:
            timing_bonus = 1
            adaptive_soften += 1
            base_damage += timing_bonus
        if script_type == "exploit" and enemy.get_fingerprint_window(target_subsystem) > 0:
            fingerprint_bonus = 2
            adaptive_soften += 2
            base_damage += fingerprint_bonus
        if adaptive_soften > 0 and adaptive_block > 0:
            adaptive_block = max(0, adaptive_block - adaptive_soften)
        if adaptive_block > 0 and base_damage > 0:
            base_damage = max(0, base_damage - adaptive_block)

        firewall_absorb = 0
        if target_subsystem == "OS" and not enemy.subsystems["SEC"].is_destroyed:
            if base_damage <= 0:
                os_damage = 0
                redirected = 0
            else:
                os_damage = max(1, base_damage // 3)
                redirected = max(0, base_damage - os_damage)
            firewall_absorb = redirected
            base_damage = os_damage

        return {
            "parsed": parsed,
            "script_data": script_data,
            "script_type": script_type,
            "target_subsystem": target_subsystem,
            "target": target,
            "damage": base_damage,
            "is_weakness": is_weakness,
            "adaptive_block": adaptive_block,
            "adaptive_reasons": adaptive_reasons,
            "timing_bonus": timing_bonus,
            "fingerprint_bonus": fingerprint_bonus,
            "firewall_absorb": firewall_absorb,
            "payload_dna": payload_dna,
        }

    @staticmethod
    def split_damage_chunks(total_damage: int, hits: int):
        if total_damage <= 0 or hits <= 0:
            return []
        hits = max(1, min(hits, total_damage))
        chunks = [1] * hits
        remainder = total_damage - hits
        for _ in range(remainder):
            chunks[random.randrange(hits)] += 1
        random.shuffle(chunks)
        return chunks

    def execute(self, command_str: str, player, enemy, game_state, phase: str = "combat") -> CommandResult:
        try:
            parsed = self.parse_command(command_str, owner=player)
        except ValueError as exc:
            return CommandResult(False, str(exc))

        script_data = self.scripts[parsed.base_cmd]
        base_cmd = parsed.base_cmd
        used_flags = parsed.flags
        target_subsystem = self.get_resolved_target(parsed) or "OS"
        payload_dna = self.get_payload_dna(parsed)

        if base_cmd == "nmap":
            if target_subsystem not in enemy.subsystems:
                return CommandResult(False, f"Error: Target subsystem [{target_subsystem}] does not exist.")
            if not player.can_scan():
                return CommandResult(False, "Error: NET is offline. You cannot sustain a scan right now.")

            if not parsed.has_target:
                enemy.reveal_surface()
                notes = []
                if "--stealth" in used_flags:
                    notes.append("         Low-signature SYN sweep completed through a masked route.")
                notes.extend(enemy.get_surface_report_lines())
                extra_lines = ("\n".join(notes) + "\n") if notes else ""
                return CommandResult(
                    True,
                    "\033[96mSUCCESS: 'nmap' service scan complete.\n"
                    f"{extra_lines}"
                    "         Open services, host banner, and subsystem map resolved.\n"
                    "         Exact integrity remains masked.\033[0m",
                )

            if not enemy.topology_revealed:
                return CommandResult(False, "Error: No service map available for deep fingerprinting.")

            if enemy.subsystems["SEC"].current_hp > 0 and enemy.security_breach_turns <= 0:
                return CommandResult(
                    False,
                    "Error: Version detection blocked by active perimeter controls.",
                )

            service_summary = enemy.get_service_summary(target_subsystem)
            if target_subsystem == enemy.weakness:
                enemy.weakness_revealed = True
                stealth_line = "         Version probes stayed below the louder detection thresholds.\n" if "--stealth" in used_flags else ""
                return CommandResult(
                    True,
                    "\033[96mSUCCESS: 'nmap' version detection complete.\n"
                    f"{stealth_line}"
                    f"         [{target_subsystem}] services: {service_summary}.\n"
                    f"         Fingerprint cache primed on [{target_subsystem}] for the next adjacent payload.\n"
                    f"\033[93m         Exposure confirmed on [{target_subsystem}]. Exploit chain integrity is poor there.\033[0m",
                )

            stealth_line = "         Version probes stayed below the louder detection thresholds.\n" if "--stealth" in used_flags else ""
            return CommandResult(
                True,
                "\033[96mSUCCESS: 'nmap' version detection complete.\n"
                f"{stealth_line}"
                f"         [{target_subsystem}] services: {service_summary}.\n"
                f"         Fingerprint cache primed on [{target_subsystem}] for the next adjacent exploit window.\n"
                f"         [{target_subsystem}] is exposed, but no primary weakness fingerprint matched.\033[0m",
            )

        if base_cmd == "masscan":
            if not player.can_scan():
                return CommandResult(False, "Error: NET is offline. Rapid scan traffic is unavailable.")
            if parsed.has_target:
                return CommandResult(False, "Error: 'masscan' is a wide scan. Omit '-target'.")

            enemy.topology_revealed = True
            botnet_power = game_state.get_domain_botnet_power() if game_state and hasattr(game_state, "get_domain_botnet_power") else 0
            exposed_lanes = []
            surface_lines = []
            for entry in enemy.get_ports_for_subsystem():
                surface_lines.append(
                    f"         {entry['port']:<8} open  {entry['service']:<12} {entry['banner']} -> [{entry['subsystem']}]"
                )
                subsystem_key = entry["subsystem"]
                if subsystem_key not in exposed_lanes:
                    exposed_lanes.append(subsystem_key)

            lane_budget = min(len(exposed_lanes), 2 + min(2, botnet_power // 2))
            primed_lanes = []
            for subsystem_key in exposed_lanes[:lane_budget]:
                enemy.arm_timing_window(subsystem_key, 1)
                primed_lanes.append(subsystem_key)

            notes = []
            if "--stealth" in used_flags or "--ghost" in used_flags:
                notes.append("         Low-profile half-open flood stayed beneath the noisier route alarms.")
            if botnet_power > 0:
                notes.append(f"         Botnet fanout widened the sweep to {lane_budget} exposed lane(s).")
            if primed_lanes:
                notes.append(f"         Timing windows primed on: {', '.join(primed_lanes)}.")

            extra_lines = ("\n".join(notes + surface_lines) + "\n") if (notes or surface_lines) else ""
            return CommandResult(
                True,
                "\033[96mSUCCESS: 'masscan' burst sweep complete.\n"
                f"{extra_lines}"
                "         Service spray finished. Port topology surfaced; host identity remains masked.\033[0m",
            )

        if base_cmd == "enum":
            if target_subsystem not in enemy.subsystems:
                return CommandResult(False, f"Error: Target subsystem [{target_subsystem}] does not exist.")
            if not player.can_scan():
                return CommandResult(False, "Error: NET is offline. Diagnostic telemetry is unavailable.")
            if not parsed.has_target:
                return CommandResult(False, "Error: 'enum' requires '-target <SUBSYSTEM>'.")
            if not enemy.topology_revealed:
                return CommandResult(False, "Error: No mapped service surface available for enumeration.")

            target = enemy.subsystems[target_subsystem]
            enemy.reveal_telemetry(target_subsystem)
            enemy.intent_revealed = True
            pressure = enemy.classify_pressure(target)
            notes = []
            if "--stealth" in used_flags:
                notes.append("         Low-signature telemetry scrape completed.")
            if target_subsystem == "NET":
                enemy.recon_discount = max(enemy.recon_discount, 20)
                notes.append("         Traffic rhythm captured. Quiet window primed for the next recon action.")
            elif target_subsystem == "MEM":
                notes.append("         Process cadence mapped. Hostile move timing is easier to predict.")
            elif target_subsystem == "SEC":
                notes.append("         Firewall profile archived. You now know exactly how thick the shell is.")
            elif target_subsystem == "STO":
                notes.append("         Backup/export paths resolved. Loot-bearing storage looks easier to prioritize.")
            elif target_subsystem == "OS":
                notes.append("         Scheduler and uptime counters resolved. Core kill pressure is now measurable.")

            extra_lines = ("\n".join(notes) + "\n") if notes else ""
            return CommandResult(
                True,
                "\033[96mSUCCESS: 'enum' host enumeration complete.\n"
                f"{extra_lines}"
                f"         [{target_subsystem}] services: {enemy.get_service_summary(target_subsystem)}.\n"
                f"         [{target_subsystem}] exact integrity: {target.current_hp}/{target.max_hp} HP ({pressure}).\n"
                "         Process table and live hostile intent resolved.\033[0m",
            )

        if base_cmd == "whois":
            if not player.can_scan():
                return CommandResult(False, "Error: NET is offline. You cannot sustain a breadcrumb scrape right now.")

            enemy.reveal_identity()
            enemy.recon_discount = max(enemy.recon_discount, 10)
            ghost_line = "         Low-noise owner lookup completed through a masked route.\n" if "--ghost" in used_flags or "--stealth" in used_flags else ""
            whois_lines = "\n".join(enemy.get_whois_summary_lines()) + "\n"
            return CommandResult(
                True,
                "\033[96mSUCCESS: 'whois' owner lookup complete.\n"
                f"{ghost_line}"
                f"{whois_lines}"
                "         Registrant metadata cached. Your next recon action carries a smaller exposure bill.\033[0m",
            )

        if base_cmd == "dirb":
            if target_subsystem not in enemy.subsystems:
                return CommandResult(False, f"Error: Target subsystem [{target_subsystem}] does not exist.")
            if not player.can_scan():
                return CommandResult(False, "Error: NET is offline. Endpoint busting is unavailable.")
            if not parsed.has_target:
                return CommandResult(False, "Error: 'dirb' requires '-target <SUBSYSTEM>'.")
            if not enemy.topology_revealed:
                return CommandResult(False, "Error: No mapped surface available for endpoint discovery.")

            target = enemy.subsystems[target_subsystem]
            enemy.reveal_telemetry(target_subsystem)
            enemy.mark_endpoint_hits(target_subsystem)
            notes = []
            if "--ghost" in used_flags or "--stealth" in used_flags:
                notes.append("         Content discovery stayed under a quieter signature profile.")
            if not enemy.has_web_surface(target_subsystem):
                notes.append("         No clean HTTP surface answered, but exposed management artifacts still leaked telemetry.")
            elif target_subsystem == "SEC":
                notes.append("         Auth surface mapped. Administrative paths are now visible.")
            elif target_subsystem == "STO":
                notes.append("         Export and archive paths resolved across the storage surface.")
            elif target_subsystem == "NET":
                notes.append("         Edge routes and application entrypoints resolved.")
            else:
                notes.append("         Management endpoints resolved around the target lane.")
            extra_lines = ("\n".join(notes) + "\n") if notes else ""
            return CommandResult(
                True,
                "\033[96mSUCCESS: 'dirb' content discovery complete.\n"
                f"{extra_lines}"
                f"         Hits: {enemy.get_endpoint_summary(target_subsystem)}.\n"
                f"         [{target_subsystem}] exact integrity: {target.current_hp}/{target.max_hp} HP.\033[0m",
            )

        if base_cmd == "spoof":
            was_signature_locked = enemy.player_signature_revealed
            scrubbed = enemy.scrub_player_recon_stage(1)
            enemy.blur_adaptation(2)
            player.signature_revealed = enemy.player_signature_revealed
            player.topology_exposed = enemy.player_topology_revealed
            if scrubbed >= 1:
                notes = ["SUCCESS: Spoof packets injected."]
                if was_signature_locked:
                    notes.append("         Enemy signature lock degraded to a rough topology map.")
                else:
                    notes.append("         Enemy topology map corrupted. They have to scan you again.")
                notes.append("         Pattern caches drifted; the host's recent response model is less reliable.")
                return CommandResult(True, "\n".join(notes))

            return CommandResult(
                True,
                "SUCCESS: Spoof packets injected.\n"
                "         No live recon lock was present, but hostile traffic models were still pushed off your trail.",
            )

        if base_cmd == "patch":
            restored = player.subsystems["OS"].repair(script_data.get("repair", 0))
            lane_key = None
            lane_restored = 0
            non_os_targets = [
                key for key in ("SEC", "NET", "MEM", "STO")
                if player.subsystems[key].current_hp < player.subsystems[key].max_hp
            ]
            if non_os_targets:
                lane_key = min(
                    non_os_targets,
                    key=lambda key: (player.subsystems[key].current_hp / max(1, player.subsystems[key].max_hp), key),
                )
                lane_restored = player.subsystems[lane_key].repair(2)
            ram_restored = 0
            if player.current_ram < player.get_effective_max_ram():
                ram_restored = min(1, player.get_effective_max_ram() - player.current_ram)
                player.current_ram += ram_restored
            notes = [f"SUCCESS: Applied emergency patch. Restored {restored} Core OS integrity."]
            if lane_key and lane_restored > 0:
                notes.append(f"         Service reload stitched [{lane_key}] for {lane_restored} integrity.")
            if ram_restored > 0:
                notes.append(f"         Local caches warmed back up. Restored {ram_restored} RAM.")
            return CommandResult(True, "\n".join(notes))

        if base_cmd == "harden":
            if target_subsystem not in player.subsystems:
                return CommandResult(False, f"Error: Defensive target [{target_subsystem}] does not exist.")
            guard_amount = script_data.get("guard", 0)
            guard_turns = script_data.get("turns", 1)
            notes = []
            if enemy.intent_revealed and enemy.current_intent.get("target") == target_subsystem:
                guard_amount += 2
                notes.append("         Intent read matched. ACL policy hardened against the live incoming lane.")
            player.grant_guard(target_subsystem, guard_amount, guard_turns)
            notes.insert(
                0,
                f"SUCCESS: Hardened [{target_subsystem}] with an ACL shell worth {guard_amount} integrity for {guard_turns} turn(s).",
            )
            return CommandResult(True, "\n".join(notes))

        if base_cmd == "honeypot":
            player.arm_scan_jammer(script_data.get("turns", 1))
            return CommandResult(
                True,
                "SUCCESS: Honeypot surface seeded.\n"
                "         The next hostile recon attempt will burn into false telemetry.",
            )

        if base_cmd == "canary":
            if target_subsystem not in player.subsystems:
                return CommandResult(False, f"Error: Defensive target [{target_subsystem}] does not exist.")
            player.arm_tripwire(
                target_subsystem,
                script_data.get("trap_damage", 5),
                script_data.get("turns", 1),
            )
            return CommandResult(
                True,
                f"SUCCESS: Canary armed on [{target_subsystem}].\n"
                "         If the next hostile move commits there, the callback will detonate.",
            )

        if base_cmd == "sinkhole":
            if target_subsystem not in player.subsystems:
                return CommandResult(False, f"Error: Defensive target [{target_subsystem}] does not exist.")
            player.arm_mirror(
                target_subsystem,
                script_data.get("turns", 1),
                script_data.get("ratio", 1.0),
                script_data.get("flat_damage", 0),
            )
            return CommandResult(
                True,
                f"SUCCESS: Sinkhole armed on [{target_subsystem}].\n"
                "         The next hostile move committed there will be routed back into its source.",
            )

        if base_cmd == "rekey":
            lock_cleared = player.clear_ram_lock()
            scrubbed = enemy.scrub_player_recon_stage(1)
            enemy.clear_adaptation_state()
            player.signature_revealed = enemy.player_signature_revealed
            player.topology_exposed = enemy.player_topology_revealed

            notes = ["SUCCESS: Session rekey completed."]
            if lock_cleared:
                notes.append("         Stale control handles were flushed from local memory.")
            if scrubbed > 0:
                notes.append("         Hostile recon peeled back by one layer.")
            notes.append("         Hostile response caches tied to the old session key were invalidated.")
            if not lock_cleared and scrubbed == 0:
                notes.append("         No stale lock or recon residue was present, but route keys were rotated.")
            return CommandResult(True, "\n".join(notes))

        if base_cmd == "jmp":
            return CommandResult(
                True,
                "SUCCESS: Branch shim loaded.\n"
                "         The live stack controller will swap the next two queued payloads when this directive resolves.",
            )

        if base_cmd == "stager":
            return CommandResult(
                True,
                f"SUCCESS: Deferred-detonation buffer armed on [{target_subsystem}].\n"
                "         The next adjacent offensive payload on that lane will be captured instead of landing immediately.",
            )

        if base_cmd == "buffer":
            return CommandResult(
                True,
                f"SUCCESS: Containment shim armed on [{target_subsystem}].\n"
                "         The next adjacent offensive payload there will trap any excess damage instead of dumping it all into the hardware.",
            )

        if base_cmd == "airmon-ng":
            if target_subsystem not in enemy.subsystems:
                return CommandResult(False, f"Error: Target subsystem [{target_subsystem}] does not exist.")
            if target_subsystem != "SEC":
                return CommandResult(False, "Error: 'airmon-ng' can only disrupt the [SEC] subsystem.")

            target = enemy.subsystems["SEC"]
            base_damage = script_data.get("damage", 0)
            actual_dmg = target.take_damage(base_damage)
            enemy.security_breach_turns = max(enemy.security_breach_turns, script_data.get("disrupt_turns", 2))

            feedback_lines = [
                f"SUCCESS: 'airmon-ng' pushed the interface into monitor mode and peeled [{target_subsystem}] for {enemy.security_breach_turns} turns.",
                f"         Dealt {actual_dmg} damage to the perimeter controls.",
            ]

            if "--stealth" not in used_flags:
                noise_amount = max(10, base_damage * 10)
                game_state.threat_ledger.add_noise(script_data.get("type", "exploit"), noise_amount)
                feedback_lines.append(f"         \033[91m> TRACE: {noise_amount} exploit noise logged.\033[0m")
            else:
                feedback_lines.append("         \033[92m> STEALTH: Spectrum masked during the breach.\033[0m")

            if target.is_destroyed:
                feedback_lines.append(f"         \033[91m*** [{target_subsystem}] CRITICAL FAILURE. OFFLINE. ***\033[0m")
                cascade = enemy.subsystems["OS"].take_damage(2)
                if cascade > 0:
                    feedback_lines.append(f"         \033[93m> CASCADE: [{target_subsystem}] collapse jolted Core OS for {cascade}.\033[0m")

            enemy.observe_player_action(parsed, script_data, target_subsystem, success=True, payload_dna=payload_dna)
            if "--stealth" in used_flags:
                enemy.blur_adaptation(1)
                feedback_lines.append("         \033[92m> STEALTH: Host adaptation caches lost resolution on the masked traffic.\033[0m")
            alert_stage = enemy.apply_counterintel_pressure(parsed, script_data, target_subsystem, payload_dna=payload_dna)
            if alert_stage == 1:
                feedback_lines.append("         \033[93m> COUNTER-INTEL: The breach exposed a rough map of your node.\033[0m")
            elif alert_stage == 2:
                feedback_lines.append("         \033[91m> COUNTER-INTEL: Your signature is burned. The host knows your weak angle.\033[0m")

            return CommandResult(True, "\n".join(feedback_lines))

        if target_subsystem not in enemy.subsystems:
            return CommandResult(False, f"Error: Target subsystem [{target_subsystem}] does not exist.")

        try:
            profile = self.build_attack_profile(parsed, player, enemy, game_state)
        except ValueError as exc:
            return CommandResult(False, str(exc))

        target = profile["target"]
        target_subsystem = profile["target_subsystem"]
        script_type = profile["script_type"]
        base_damage = profile["damage"]
        is_weakness = profile["is_weakness"]
        adaptive_block = profile["adaptive_block"]
        adaptive_reasons = profile["adaptive_reasons"]
        timing_bonus = profile["timing_bonus"]
        fingerprint_bonus = profile["fingerprint_bonus"]
        payload_dna = profile["payload_dna"]
        firewall_absorb = 0
        if profile["firewall_absorb"] > 0:
            firewall_absorb = enemy.subsystems["SEC"].take_damage(profile["firewall_absorb"])

        if base_cmd == "ping" and enemy.topology_revealed and not enemy.intent_revealed:
            enemy.intent_revealed = True

        actual_dmg = target.take_damage(base_damage)
        total_damage = actual_dmg
        overkill_damage = max(0, base_damage - actual_dmg)
        result_metadata = {
            "worm_seed": 0,
            "worm_source": None,
            "bus_splash_events": 0,
            "bus_splash_damage": 0,
            "overkill_damage": overkill_damage,
            "contained_overkill": 0,
            "payload_signature": build_payload_signature(payload_dna),
        }
        feedback_lines = [f"SUCCESS: Executed '{base_cmd}' on [{target_subsystem}]. Dealt {actual_dmg} damage."]

        if base_cmd == "ping" and enemy.topology_revealed and enemy.intent_revealed:
            feedback_lines.append(
                "         \033[96m> RTT SAMPLE: response timing exposed a cleaner read on the hostile job queue.\033[0m"
            )
        if base_cmd == "ping" and actual_dmg > 0:
            feedback_lines.append(
                f"         \033[96m> TIMING MARK: [{target_subsystem}] now has a cleaner adjacent follow-up window.\033[0m"
            )
        if timing_bonus > 0:
            feedback_lines.append(
                f"         \033[96m> TIMING WINDOW: recent packet timing shaved {timing_bonus} extra pressure into [{target_subsystem}].\033[0m"
            )
        if fingerprint_bonus > 0:
            feedback_lines.append(
                f"         \033[96m> FINGERPRINT CACHE: version data on [{target_subsystem}] gave the exploit +{fingerprint_bonus} cleaner damage.\033[0m"
            )

        if base_cmd == "hydra":
            auth_surface = enemy.has_auth_surface(target_subsystem)
            attempts = random.randint(3, 5) if auth_surface else random.randint(1, 2)
            if enemy.has_credential_pressure(target_subsystem):
                attempts += 1
            landed = self.split_damage_chunks(actual_dmg, attempts)
            feedback_lines[0] = (
                f"SUCCESS: Executed 'hydra' on [{target_subsystem}]. "
                f"{len(landed) if landed else 0} valid login(s) landed for {actual_dmg} total damage."
            )
            if auth_surface:
                feedback_lines.append(
                    f"         \033[93m> AUTH SURFACE: {enemy.get_service_summary(target_subsystem)} accepted a real brute-force window.\033[0m"
                )
            else:
                feedback_lines.append(
                    "         \033[90m> NO AUTH SURFACE: the run degraded into blind password noise on a bad target lane.\033[0m"
                )
            if enemy.has_credential_pressure(target_subsystem):
                feedback_lines.append(
                    "         \033[93m> REUSED CREDS: earlier spray traffic primed the lane for faster valid hits.\033[0m"
                )
            for idx, chunk in enumerate(landed, start=1):
                feedback_lines.append(f"         \033[93m> HYDRA: login burst {idx} landed for {chunk} damage.\033[0m")

        if base_cmd == "ddos":
            botnet_power = game_state.get_domain_botnet_power() if game_state and hasattr(game_state, "get_domain_botnet_power") else 0
            feedback_lines[0] = (
                f"SUCCESS: Executed 'ddos' on [{target_subsystem}]. "
                f"Flood pressure landed for {actual_dmg} damage."
            )
            if target_subsystem in {"NET", "SEC"}:
                feedback_lines.append(
                    "         \033[93m> SATURATION LANE: the flood is most effective against routing and perimeter control.\033[0m"
                )
            if botnet_power > 0:
                feedback_lines.append(
                    f"         \033[96m> BOTNET SCALE: {botnet_power} seeded domain(s) added +{botnet_power * 2} distributed pressure.\033[0m"
                )
            else:
                feedback_lines.append(
                    "         \033[90m> LOCAL SWARM: no rooted botnet seeds were available, so the flood stayed small.\033[0m"
                )
            if target_subsystem == "NET" and actual_dmg > 0:
                enemy.intent_jam_turns = max(getattr(enemy, "intent_jam_turns", 0), 1)
                feedback_lines.append(
                    "         \033[96m> ROUTE CHOKE: uplink congestion may stall the host's next control cycle.\033[0m"
                )

        if base_cmd == "sqlmap" and actual_dmg > 0:
            if enemy.has_endpoint_hits(target_subsystem):
                feedback_lines.append(
                    "         \033[93m> ENDPOINT HIT: prior directory discovery gave the injection cleaner reach.\033[0m"
                )
            if target_subsystem == "STO":
                leak = 8
                game_state.player_crypto += leak
                feedback_lines.append(
                    f"         \033[95m> DATA EXFIL: dumped {leak} Crypto worth of records from the storage lane.\033[0m"
                )
            elif target_subsystem == "MEM":
                enemy.intent_jam_turns = max(enemy.intent_jam_turns, 1)
                feedback_lines.append(
                    "         \033[96m> QUERY FAULT: backend state desynced; the next hostile action is likely to stall.\033[0m"
                )

        if base_cmd == "siphon" and actual_dmg > 0:
            siphon_gain = actual_dmg
            if target_subsystem == "STO":
                siphon_gain += 3
            elif target_subsystem == "MEM":
                siphon_gain += 2
            if enemy.has_endpoint_hits(target_subsystem):
                siphon_gain += 1
            game_state.player_crypto += siphon_gain
            feedback_lines.append(
                f"         \033[95m> SIPHON: drained {siphon_gain} Crypto from [{target_subsystem}] service residue.\033[0m"
            )

        if base_cmd == "spray" and target_subsystem == "SEC" and actual_dmg > 0:
            enemy.security_breach_turns = max(enemy.security_breach_turns, 1)
            feedback_lines.append(
                "         \033[93m> SPRAY: repeated auth guesses destabilized the perimeter for one turn.\033[0m"
            )
        if base_cmd == "spray" and actual_dmg > 0 and enemy.has_auth_surface(target_subsystem):
            enemy.arm_credential_pressure(target_subsystem, 2)
            feedback_lines.append(
                "         \033[93m> CREDENTIAL PRESSURE: the lane is primed for a follow-up brute-force run.\033[0m"
            )

        if base_cmd == "shred" and actual_dmg > 0 and target_subsystem in {"STO", "MEM"}:
            enemy.arm_repair_lock(target_subsystem, 2)
            feedback_lines.append(
                f"         \033[93m> SHRED: recovery artifacts on [{target_subsystem}] were torn up for 2 turns.\033[0m"
            )

        if base_cmd == "overflow" and actual_dmg > 0 and target_subsystem in {"MEM", "NET"}:
            enemy.intent_jam_turns = max(enemy.intent_jam_turns, 1)
            feedback_lines.append(
                "         \033[96m> CORRUPTION: service state destabilized; the next hostile action may fail cleanly.\033[0m"
            )

        if base_cmd == "hammer" and actual_dmg > 0 and target_subsystem == "OS" and enemy.subsystems["SEC"].is_destroyed:
            enemy.intent_jam_turns = max(enemy.intent_jam_turns, 1)
            side_pool = [
                key for key in ("NET", "MEM", "STO")
                if not enemy.subsystems[key].is_destroyed
            ]
            if side_pool:
                side_target = random.choice(side_pool)
                side_damage = enemy.subsystems[side_target].take_damage(2)
                total_damage += side_damage
                feedback_lines.append(
                    f"         \033[93m> KERNEL PANIC: crash spill ripped [{side_target}] for {side_damage} collateral damage.\033[0m"
                )
            feedback_lines.append(
                "         \033[96m> PANIC WINDOW: the host control loop is likely to stall on its next action.\033[0m"
            )

        if firewall_absorb > 0:
            feedback_lines.append(
                f"         \033[93m> FIREWALL: [SEC] intercepted {firewall_absorb} damage before it hit Core OS.\033[0m"
            )

        if adaptive_block > 0:
            reason_text = ", ".join(adaptive_reasons) if adaptive_reasons else "host adapted"
            feedback_lines.append(
                f"         \033[93m> ADAPTIVE DEFENSE: {reason_text}. {adaptive_block} damage was neutralized.\033[0m"
            )

        if is_weakness and base_damage > 0:
            if not enemy.weakness_revealed:
                feedback_lines.append("         \033[93m> EXPOSURE: hidden weak path confirmed. Damage doubled.\033[0m")
                enemy.weakness_revealed = True
            else:
                feedback_lines.append("         \033[93m> EXPOSURE: known weak path hit. Damage doubled.\033[0m")

        if "--worm" in used_flags and target.is_destroyed and base_damage > actual_dmg:
            overflow = base_damage - actual_dmg
            alive_subs = [key for key, subsystem in enemy.subsystems.items() if not subsystem.is_destroyed]
            if alive_subs:
                jump_target = random.choice(alive_subs)
                jump_damage = enemy.subsystems[jump_target].take_damage(overflow)
                total_damage += jump_damage
                feedback_lines.append(
                    f"         \033[93m> WORM: residual payload propagated into [{jump_target}] for {jump_damage} damage.\033[0m"
                )

        if "--fork" in used_flags and total_damage > 0:
            fork_pool = [
                key
                for key, subsystem in enemy.subsystems.items()
                if key != target_subsystem and not subsystem.is_destroyed
            ]
            if fork_pool:
                fork_target = random.choice(fork_pool)
                fork_damage = max(1, total_damage // 2)
                dealt = enemy.subsystems[fork_target].take_damage(fork_damage)
                total_damage += dealt
                feedback_lines.append(
                    f"         \033[93m> FORK: secondary thread clipped [{fork_target}] for {dealt} damage.\033[0m"
                )

        splash_pressure = 0
        splash_depth = 1
        if "--volatile" in used_flags and total_damage > 0:
            splash_pressure = max(splash_pressure, max(1, total_damage // 2))
            splash_depth = max(splash_depth, 2)
        if "--cascade" in used_flags and total_damage > 0:
            splash_pressure = max(splash_pressure, max(1, total_damage // 2))
            splash_depth = max(splash_depth, 2)
        if base_cmd in {"overflow", "hammer"} and total_damage > 0:
            splash_pressure = max(splash_pressure, max(1, total_damage // 2))
            splash_depth = max(splash_depth, 2)
        elif base_cmd == "shred" and target_subsystem in {"MEM", "STO"} and total_damage > 0:
            splash_pressure = max(splash_pressure, max(1, total_damage // 3))

        if splash_pressure > 0:
            splash_lines, splash_damage = enemy.apply_bus_splash(
                target_subsystem,
                splash_pressure,
                depth=splash_depth,
            )
            if splash_damage > 0:
                total_damage += splash_damage
                result_metadata["bus_splash_events"] += 1
                result_metadata["bus_splash_damage"] += splash_damage
                feedback_lines.extend(splash_lines)

        if "--ransom" in used_flags:
            game_state.player_crypto += total_damage
            feedback_lines.append(f"         \033[95m> RANSOM: monetized {total_damage} points of damage into Crypto.\033[0m")

        if "--worm" in used_flags and total_damage > 0:
            seed_strength = max(1, (total_damage // 3) + (2 if target.is_destroyed else 0))
            result_metadata["worm_seed"] = max(result_metadata["worm_seed"], seed_strength)
            result_metadata["worm_source"] = target_subsystem
            feedback_lines.append(
                f"         \033[95m> WORM SEED: residual traffic escaped the node with {seed_strength} route-mesh pressure.\033[0m"
            )

        if "--stealth" not in used_flags and script_type in {"brute_force", "exploit"}:
            noise_amount = max(
                10,
                total_damage * 10 + sum(self.flags.get(flag, {}).get("noise_bonus", 0) for flag in used_flags),
            )
            game_state.threat_ledger.add_noise(script_type, noise_amount)
            feedback_lines.append(f"         \033[91m> TRACE: {noise_amount} {script_type} noise logged.\033[0m")
        elif "--stealth" in used_flags:
            feedback_lines.append("         \033[92m> STEALTH: payload masked under a lower-noise route.\033[0m")

        if target.is_destroyed:
            feedback_lines.append(f"         \033[91m*** [{target_subsystem}] CRITICAL FAILURE. OFFLINE. ***\033[0m")
            if target_subsystem != "OS":
                cascade = enemy.subsystems["OS"].take_damage(2)
                if cascade > 0:
                    total_damage += cascade
                    feedback_lines.append(
                        f"         \033[93m> CASCADE: [{target_subsystem}] failure propagated into Core OS for {cascade}.\033[0m"
                    )
                if target_subsystem == "STO":
                    spill = 18
                    game_state.player_crypto += spill
                    feedback_lines.append(f"         \033[95m> DATA LEAK: extracted {spill} Crypto from the collapsed storage lane.\033[0m")
                elif target_subsystem == "NET":
                    feedback_lines.append("         \033[96m> BLACKOUT: hostile scan and trace quality dropped with the network plane.\033[0m")
                elif target_subsystem == "MEM":
                    feedback_lines.append("         \033[96m> DESYNC: hostile payload scheduling is now unstable.\033[0m")
                elif target_subsystem == "SEC":
                    feedback_lines.append("         \033[96m> OPEN CORE: direct access to [OS] is no longer being shunted by perimeter controls.\033[0m")

        enemy.observe_player_action(parsed, script_data, target_subsystem, success=True, payload_dna=payload_dna)
        if "--stealth" in used_flags:
            enemy.blur_adaptation(1)
            feedback_lines.append("         \033[92m> STEALTH: Host adaptation caches lost resolution on the masked traffic.\033[0m")
        alert_stage = enemy.apply_counterintel_pressure(parsed, script_data, target_subsystem, payload_dna=payload_dna)
        if alert_stage == 1:
            feedback_lines.append("         \033[93m> COUNTER-INTEL: The host now has a rough map of your node.\033[0m")
        elif alert_stage == 2:
            feedback_lines.append("         \033[91m> COUNTER-INTEL: Signature burned. Expect targeted punishment.\033[0m")

        return CommandResult(True, "\n".join(feedback_lines), metadata=result_metadata)
