import random

from game_state import ThreatLedger


class Subsystem:
    def __init__(self, name: str, hp: int):
        self.name = name
        self.max_hp = hp
        self.current_hp = hp
        self.is_destroyed = hp <= 0

    def take_damage(self, amount: int):
        actual_damage = min(self.current_hp, max(0, amount))
        self.current_hp = max(0, self.current_hp - amount)
        if self.current_hp == 0:
            self.is_destroyed = True
        return actual_damage

    def repair(self, amount: int):
        restored = min(self.max_hp - self.current_hp, max(0, amount))
        self.current_hp += restored
        if self.current_hp > 0:
            self.is_destroyed = False
        return restored


class SupportBot:
    def __init__(
        self,
        name: str = "Scrap Bot",
        ram_reservation: int = 1,
        script_ram_cap: int = 2,
        cadence: int = 2,
        payload: str | None = None,
    ):
        self.name = name
        self.ram_reservation = ram_reservation
        self.script_ram_cap = script_ram_cap
        self.cadence = cadence
        self.payload = payload

    @classmethod
    def from_legacy(cls, data):
        if isinstance(data, SupportBot):
            data.ensure_runtime_defaults()
            return data

        return cls(
            name=data.get("name", "Scrap Bot"),
            ram_reservation=data.get("ram_reservation", 1),
            script_ram_cap=data.get("script_ram_cap", 2),
            cadence=data.get("cadence", 2),
            payload=data.get("payload"),
        )

    def ensure_runtime_defaults(self):
        if not hasattr(self, "name"):
            self.name = "Scrap Bot"
        if not hasattr(self, "ram_reservation"):
            self.ram_reservation = 1
        if not hasattr(self, "script_ram_cap"):
            self.script_ram_cap = 2
        if not hasattr(self, "cadence"):
            self.cadence = 2
        if not hasattr(self, "payload"):
            self.payload = None

    @property
    def status(self):
        return "ready" if self.payload else "standby"

    def should_trigger(self, turn_number: int):
        return bool(self.payload) and turn_number > 0 and turn_number % max(1, self.cadence) == 0

    def get_summary_label(self):
        return f"{self.name.upper()}:{self.status.upper()}"


class Player:
    SIGNATURE_TARGETS = ["SEC", "NET", "MEM", "STO"]
    DEFENSIVE_TARGETS = ["OS", "SEC", "NET", "MEM", "STO"]
    STUDENT_SCRIPT_LOADOUT = (
        "ping",
        "hydra",
    )
    STUDENT_FLAG_LOADOUT = (
        "--burst",
    )
    BLACK_ICE_SCRIPT_LOADOUT = (
        "honeypot",
        "spoof",
    )
    BLACK_ICE_FLAG_LOADOUT = (
        "--ghost",
    )
    ROOKIE_SCRIPT_LOADOUT = (
        "ping",
        "hydra",
    )
    ROOKIE_FLAG_LOADOUT = (
        "--burst",
    )

    def __init__(self, profile: str = "rookie"):
        self.profile = profile
        self.handle = "player"
        self.title = "Drifter"
        self.local_ip = self.generate_local_ip()
        self.signature_subsystem = random.choice(self.SIGNATURE_TARGETS)
        self.support_bots = []
        self.max_ram = 8
        self.current_ram = 8
        self.encounter_ram_modifier = 0
        self.temp_ram_penalty = 0
        self.temp_ram_turns = 0
        self.topology_exposed = False
        self.signature_revealed = False
        self.guard_banks = {}
        self.guard_turns = {}
        self.scan_jammer_turns = 0
        self.tripwire_target = None
        self.tripwire_turns = 0
        self.tripwire_damage = 0
        self.mirror_target = None
        self.mirror_turns = 0
        self.mirror_ratio = 1.0
        self.mirror_flat_damage = 0
        self.owned_scripts = set()
        self.owned_flags = set()
        self.consumables = {}
        self.subsystems = {}
        self.configure_profile(profile)

    @staticmethod
    def generate_local_ip():
        return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(2, 254)}"

    def configure_profile(self, profile: str):
        if profile == "legend":
            profile = "student"
        elif profile in {"burned", "legacy", "skip"}:
            profile = "rookie"

        self.profile = profile
        self.local_ip = self.generate_local_ip()
        self.signature_subsystem = random.choice(self.SIGNATURE_TARGETS)
        self.support_bots = []
        self.topology_exposed = False
        self.signature_revealed = False
        self.encounter_ram_modifier = 0
        self.temp_ram_penalty = 0
        self.temp_ram_turns = 0
        self.guard_banks = {key: 0 for key in self.DEFENSIVE_TARGETS}
        self.guard_turns = {key: 0 for key in self.DEFENSIVE_TARGETS}
        self.scan_jammer_turns = 0
        self.tripwire_target = None
        self.tripwire_turns = 0
        self.tripwire_damage = 0
        self.mirror_target = None
        self.mirror_turns = 0
        self.mirror_ratio = 1.0
        self.mirror_flat_damage = 0
        self.owned_scripts = set()
        self.owned_flags = set()
        self.consumables = {}

        if profile == "student":
            self.handle = "newblood"
            self.title = "Sandbox Trainee"
            self.max_ram = 9
            os_hp = 52
            sub_hp = 10
            self.set_toolkit(self.STUDENT_SCRIPT_LOADOUT, self.STUDENT_FLAG_LOADOUT)
        else:
            self.handle = "newblood"
            self.title = "Grid Drifter"
            self.max_ram = 8
            os_hp = 50
            sub_hp = 10
            self.set_toolkit(self.ROOKIE_SCRIPT_LOADOUT, self.ROOKIE_FLAG_LOADOUT)
            self.grant_consumable("ram_capsule", 1)

        self.current_ram = self.max_ram
        self.subsystems = {
            "OS": Subsystem("Core OS", os_hp),
            "SEC": Subsystem("Firewall", sub_hp),
            "NET": Subsystem("Proxy", sub_hp),
            "MEM": Subsystem("Memory", sub_hp),
            "STO": Subsystem("Storage", sub_hp),
        }

    def ensure_runtime_defaults(self):
        if not hasattr(self, "profile"):
            self.profile = "rookie"
        if not hasattr(self, "handle"):
            self.handle = "newblood"
        if not hasattr(self, "title"):
            self.title = "Grid Drifter"
        if not hasattr(self, "local_ip"):
            self.local_ip = self.generate_local_ip()
        if not hasattr(self, "signature_subsystem"):
            self.signature_subsystem = random.choice(self.SIGNATURE_TARGETS)
        if not hasattr(self, "support_bots"):
            self.support_bots = []
        else:
            self.support_bots = [SupportBot.from_legacy(bot) for bot in self.support_bots]
        if not hasattr(self, "encounter_ram_modifier"):
            self.encounter_ram_modifier = 0
        if not hasattr(self, "temp_ram_penalty"):
            self.temp_ram_penalty = 0
        if not hasattr(self, "temp_ram_turns"):
            self.temp_ram_turns = 0
        if not hasattr(self, "topology_exposed"):
            self.topology_exposed = False
        if not hasattr(self, "signature_revealed"):
            self.signature_revealed = False
        if not hasattr(self, "guard_banks"):
            self.guard_banks = {key: 0 for key in self.DEFENSIVE_TARGETS}
        if not hasattr(self, "guard_turns"):
            self.guard_turns = {key: 0 for key in self.DEFENSIVE_TARGETS}
        if not hasattr(self, "scan_jammer_turns"):
            self.scan_jammer_turns = 0
        if not hasattr(self, "tripwire_target"):
            self.tripwire_target = None
        if not hasattr(self, "tripwire_turns"):
            self.tripwire_turns = 0
        if not hasattr(self, "tripwire_damage"):
            self.tripwire_damage = 0
        if not hasattr(self, "mirror_target"):
            self.mirror_target = None
        if not hasattr(self, "mirror_turns"):
            self.mirror_turns = 0
        if not hasattr(self, "mirror_ratio"):
            self.mirror_ratio = 1.0
        if not hasattr(self, "mirror_flat_damage"):
            self.mirror_flat_damage = 0
        if not hasattr(self, "owned_scripts"):
            self.owned_scripts = set()
        else:
            self.owned_scripts = set(self.owned_scripts)
        if not hasattr(self, "owned_flags"):
            self.owned_flags = set()
        else:
            self.owned_flags = set(self.owned_flags)
        if not hasattr(self, "consumables"):
            self.consumables = {}
        if not self.owned_scripts and not self.owned_flags:
            if self.profile == "student":
                self.set_toolkit(self.STUDENT_SCRIPT_LOADOUT, self.STUDENT_FLAG_LOADOUT)
            else:
                self.set_toolkit(self.ROOKIE_SCRIPT_LOADOUT, self.ROOKIE_FLAG_LOADOUT)

    def reset_for_new_run(self):
        self.configure_profile("rookie")

    def set_toolkit(self, scripts=(), flags=()):
        self.owned_scripts = {script for script in scripts if script}
        self.owned_flags = {flag for flag in flags if flag}

    def grant_script(self, script_id: str):
        if script_id:
            self.owned_scripts.add(script_id)

    def grant_scripts(self, script_ids):
        for script_id in script_ids or []:
            self.grant_script(script_id)

    def grant_flag(self, flag_id: str):
        if flag_id:
            self.owned_flags.add(flag_id)

    def grant_flags(self, flag_ids):
        for flag_id in flag_ids or []:
            self.grant_flag(flag_id)

    def unlock_black_ice_suite(self):
        self.grant_scripts(self.BLACK_ICE_SCRIPT_LOADOUT)
        self.grant_flags(self.BLACK_ICE_FLAG_LOADOUT)

    def owns_script(self, script_id: str):
        return script_id in self.owned_scripts

    def owns_flag(self, flag_id: str):
        return flag_id in self.owned_flags

    def begin_encounter(self):
        self.current_ram = self.get_effective_max_ram()
        self.encounter_ram_modifier = 0
        self.temp_ram_penalty = 0
        self.temp_ram_turns = 0
        self.topology_exposed = False
        self.signature_revealed = False
        self.guard_banks = {key: 0 for key in self.DEFENSIVE_TARGETS}
        self.guard_turns = {key: 0 for key in self.DEFENSIVE_TARGETS}
        self.scan_jammer_turns = 0
        self.tripwire_target = None
        self.tripwire_turns = 0
        self.tripwire_damage = 0
        self.mirror_target = None
        self.mirror_turns = 0
        self.mirror_ratio = 1.0
        self.mirror_flat_damage = 0

    def end_encounter(self):
        self.encounter_ram_modifier = 0
        self.temp_ram_penalty = 0
        self.temp_ram_turns = 0
        self.topology_exposed = False
        self.signature_revealed = False
        self.guard_banks = {key: 0 for key in self.DEFENSIVE_TARGETS}
        self.guard_turns = {key: 0 for key in self.DEFENSIVE_TARGETS}
        self.scan_jammer_turns = 0
        self.tripwire_target = None
        self.tripwire_turns = 0
        self.tripwire_damage = 0
        self.mirror_target = None
        self.mirror_turns = 0
        self.mirror_ratio = 1.0
        self.mirror_flat_damage = 0
        self.current_ram = self.get_effective_max_ram()

    def get_effective_max_ram(self):
        mem_penalty = max(0, (self.subsystems["MEM"].max_hp - self.subsystems["MEM"].current_hp) // 4)
        bot_reservation = sum(bot.ram_reservation for bot in self.support_bots)
        return max(1, self.max_ram + self.encounter_ram_modifier - self.temp_ram_penalty - mem_penalty - bot_reservation)

    def apply_ram_lock(self, amount: int, turns: int):
        self.temp_ram_penalty = max(self.temp_ram_penalty, amount)
        self.temp_ram_turns = max(self.temp_ram_turns, turns)
        self.current_ram = min(self.current_ram, self.get_effective_max_ram())

    def tick_end_of_turn(self):
        if self.temp_ram_turns > 0:
            self.temp_ram_turns -= 1
            if self.temp_ram_turns == 0:
                self.temp_ram_penalty = 0

        if self.scan_jammer_turns > 0:
            self.scan_jammer_turns -= 1

        if self.tripwire_turns > 0:
            self.tripwire_turns -= 1
            if self.tripwire_turns == 0:
                self.tripwire_target = None
                self.tripwire_damage = 0

        if self.mirror_turns > 0:
            self.mirror_turns -= 1
            if self.mirror_turns == 0:
                self.mirror_target = None
                self.mirror_ratio = 1.0
                self.mirror_flat_damage = 0

        for key in self.DEFENSIVE_TARGETS:
            if self.guard_turns.get(key, 0) > 0:
                self.guard_turns[key] -= 1
                if self.guard_turns[key] == 0:
                    self.guard_banks[key] = 0

    def can_scan(self):
        return not self.subsystems["NET"].is_destroyed

    def can_disconnect(self):
        return not self.subsystems["NET"].is_destroyed

    def get_signature_bonus_text(self, subsystem_key: str):
        if subsystem_key == "NET":
            return "Your uplink is exposed."
        if subsystem_key == "MEM":
            return "Your memory bus is exposed."
        if subsystem_key == "SEC":
            return "Your firewall lattice is exposed."
        return "Your storage cluster is exposed."

    def get_support_bot_summary(self):
        if not self.support_bots:
            return "BOT BAY     EMPTY"

        labels = []
        for bot in self.support_bots[:2]:
            labels.append(bot.get_summary_label())

        suffix = " +" if len(self.support_bots) > 2 else ""
        return f"BOT BAY     {', '.join(labels)}{suffix}"

    def get_ram_regen(self):
        mem = self.subsystems["MEM"]
        if mem.current_hp <= 0:
            return 1
        ratio = mem.current_hp / max(1, mem.max_hp)
        if ratio <= 0.34:
            return 2
        if ratio <= 0.67:
            return 3
        return 4

    def regen_ram(self):
        regen = self.get_ram_regen()
        self.current_ram = min(self.get_effective_max_ram(), self.current_ram + regen)
        return regen

    def grant_guard(self, subsystem_key: str, amount: int, turns: int = 1):
        self.guard_banks[subsystem_key] = self.guard_banks.get(subsystem_key, 0) + max(0, amount)
        self.guard_turns[subsystem_key] = max(self.guard_turns.get(subsystem_key, 0), turns)

    def absorb_guard(self, subsystem_key: str, damage: int):
        guard = self.guard_banks.get(subsystem_key, 0)
        blocked = min(guard, max(0, damage))
        if blocked > 0:
            self.guard_banks[subsystem_key] -= blocked
            if self.guard_banks[subsystem_key] <= 0:
                self.guard_banks[subsystem_key] = 0
                self.guard_turns[subsystem_key] = 0
        return blocked, max(0, damage - blocked)

    def arm_scan_jammer(self, turns: int = 1):
        self.scan_jammer_turns = max(self.scan_jammer_turns, turns)

    def consume_scan_jammer(self):
        if self.scan_jammer_turns <= 0:
            return False
        self.scan_jammer_turns = 0
        return True

    def arm_tripwire(self, subsystem_key: str, damage: int, turns: int = 1):
        self.tripwire_target = subsystem_key
        self.tripwire_damage = max(0, damage)
        self.tripwire_turns = max(1, turns)

    def consume_tripwire(self, subsystem_key: str):
        if self.tripwire_turns <= 0 or self.tripwire_target != subsystem_key:
            return 0
        damage = self.tripwire_damage
        self.tripwire_target = None
        self.tripwire_turns = 0
        self.tripwire_damage = 0
        return damage

    def arm_mirror(self, subsystem_key: str, turns: int = 1, ratio: float = 1.0, flat_damage: int = 0):
        self.mirror_target = subsystem_key
        self.mirror_turns = max(1, turns)
        self.mirror_ratio = max(0.0, ratio)
        self.mirror_flat_damage = max(0, flat_damage)

    def consume_mirror(self, subsystem_key: str, incoming_damage: int = 0):
        if self.mirror_turns <= 0 or self.mirror_target != subsystem_key:
            return 0
        reflected = max(0, int(incoming_damage * self.mirror_ratio) + self.mirror_flat_damage)
        self.mirror_target = None
        self.mirror_turns = 0
        self.mirror_ratio = 1.0
        self.mirror_flat_damage = 0
        return reflected

    def clear_ram_lock(self):
        had_lock = self.temp_ram_penalty > 0 or self.temp_ram_turns > 0
        self.temp_ram_penalty = 0
        self.temp_ram_turns = 0
        self.current_ram = min(self.current_ram, self.get_effective_max_ram())
        return had_lock

    def has_active_defenses(self, subsystem_key: str | None = None):
        keys = [subsystem_key] if subsystem_key else self.DEFENSIVE_TARGETS
        for key in keys:
            if self.guard_banks.get(key, 0) > 0:
                return True
        if self.scan_jammer_turns > 0 and subsystem_key in {None, "NET"}:
            return True
        if self.tripwire_turns > 0 and (subsystem_key is None or self.tripwire_target == subsystem_key):
            return True
        if self.mirror_turns > 0 and (subsystem_key is None or self.mirror_target == subsystem_key):
            return True
        return False

    def strip_active_defenses(self, subsystem_key: str | None = None):
        removed = []
        keys = [subsystem_key] if subsystem_key else list(self.DEFENSIVE_TARGETS)
        for key in keys:
            if self.guard_banks.get(key, 0) > 0:
                self.guard_banks[key] = 0
                self.guard_turns[key] = 0
                removed.append(f"acl:{key}")

        if subsystem_key in {None, "NET"} and self.scan_jammer_turns > 0:
            self.scan_jammer_turns = 0
            removed.append("honeypot")

        if self.tripwire_turns > 0 and (subsystem_key is None or self.tripwire_target == subsystem_key):
            removed.append(f"canary:{self.tripwire_target}")
            self.tripwire_target = None
            self.tripwire_turns = 0
            self.tripwire_damage = 0

        if self.mirror_turns > 0 and (subsystem_key is None or self.mirror_target == subsystem_key):
            removed.append(f"sinkhole:{self.mirror_target}")
            self.mirror_target = None
            self.mirror_turns = 0
            self.mirror_ratio = 1.0
            self.mirror_flat_damage = 0

        return removed

    def grant_consumable(self, item_id: str, quantity: int = 1):
        if quantity <= 0:
            return
        self.consumables[item_id] = self.consumables.get(item_id, 0) + quantity

    def get_consumable_count(self, item_id: str):
        return self.consumables.get(item_id, 0)

    def consume_consumable(self, item_id: str):
        count = self.consumables.get(item_id, 0)
        if count <= 0:
            return False
        if count == 1:
            self.consumables.pop(item_id, None)
        else:
            self.consumables[item_id] = count - 1
        return True

    def get_consumable_summary(self):
        if not self.consumables:
            return "NONE"
        labels = [f"{item_id}x{count}" for item_id, count in sorted(self.consumables.items())]
        return ", ".join(labels[:2]) + (" +" if len(labels) > 2 else "")

    def get_defense_summary(self):
        labels = []
        if self.scan_jammer_turns > 0:
            labels.append("HONEYPOT")
        if self.tripwire_turns > 0 and self.tripwire_target:
            labels.append(f"CANARY:{self.tripwire_target}")
        if self.mirror_turns > 0 and self.mirror_target:
            labels.append(f"SINK:{self.mirror_target}")

        for key in self.DEFENSIVE_TARGETS:
            amount = self.guard_banks.get(key, 0)
            if amount > 0:
                labels.append(f"ACL:{key}+{amount}")

        return "DEFENSE     " + (", ".join(labels) if labels else "OPEN")

    def install_support_bot(self, name="Scrap Bot", ram_reservation=1, script_ram_cap=2, cadence=2):
        bot = SupportBot(
            name=name,
            ram_reservation=ram_reservation,
            script_ram_cap=script_ram_cap,
            cadence=cadence,
        )
        self.support_bots.append(bot)
        self.current_ram = min(self.current_ram, self.get_effective_max_ram())
        return bot


class Enemy:
    SERVICE_POOLS = {
        "SEC": (
            {"port": "22/tcp", "service": "ssh", "banner": "OpenSSH"},
            {"port": "23/tcp", "service": "telnet", "banner": "BusyBox telnetd"},
            {"port": "3389/tcp", "service": "rdp", "banner": "Microsoft Terminal Services"},
            {"port": "5985/tcp", "service": "winrm", "banner": "WS-Man"},
            {"port": "8443/tcp", "service": "https-admin", "banner": "Admin TLS gateway"},
            {"port": "587/tcp", "service": "smtp-auth", "banner": "Submission relay"},
            {"port": "1194/udp", "service": "openvpn", "banner": "OpenVPN edge"},
        ),
        "NET": (
            {"port": "53/udp", "service": "dns", "banner": "Recursive resolver"},
            {"port": "80/tcp", "service": "http", "banner": "HTTP management plane"},
            {"port": "443/tcp", "service": "https", "banner": "TLS application edge"},
            {"port": "8080/tcp", "service": "proxy", "banner": "Proxy frontend"},
            {"port": "1883/tcp", "service": "mqtt", "banner": "MQTT broker"},
            {"port": "554/tcp", "service": "rtsp", "banner": "RTSP control plane"},
            {"port": "161/udp", "service": "snmp", "banner": "SNMP agent"},
        ),
        "MEM": (
            {"port": "135/tcp", "service": "rpc", "banner": "RPC endpoint mapper"},
            {"port": "445/tcp", "service": "smb", "banner": "SMB session service"},
            {"port": "6379/tcp", "service": "redis", "banner": "Redis cache"},
            {"port": "11211/tcp", "service": "memcached", "banner": "Memcached slab cache"},
            {"port": "1099/tcp", "service": "java-rmi", "banner": "RMI registry"},
            {"port": "4369/tcp", "service": "epmd", "banner": "Erlang port mapper"},
        ),
        "STO": (
            {"port": "21/tcp", "service": "ftp", "banner": "FTP service"},
            {"port": "2049/tcp", "service": "nfs", "banner": "NFS export"},
            {"port": "3306/tcp", "service": "mysql", "banner": "MySQL listener"},
            {"port": "5432/tcp", "service": "postgres", "banner": "PostgreSQL listener"},
            {"port": "1433/tcp", "service": "mssql", "banner": "SQL Server listener"},
            {"port": "873/tcp", "service": "rsync", "banner": "Rsync daemon"},
            {"port": "445/tcp", "service": "smb", "banner": "SMB file service"},
        ),
    }
    HTTP_SERVICES = {"http", "https", "https-admin", "proxy", "rtsp"}
    AUTH_SERVICES = {"ssh", "telnet", "rdp", "winrm", "smtp-auth", "openvpn", "ftp", "smb", "http", "https", "https-admin", "proxy"}
    DB_SERVICES = {"mysql", "postgres", "mssql", "redis", "memcached"}
    ENDPOINT_HINTS = {
        "SEC": ("/login", "/admin", "/console", "/auth", "/vpn"),
        "NET": ("/status", "/api", "/proxy", "/route", "/edge"),
        "MEM": ("/debug", "/metrics", "/workers", "/session", "/cache"),
        "STO": ("/backup", "/dump", "/export", "/archive", "/db"),
    }

    def __init__(
        self,
        enemy_id: str,
        enemy_data: dict,
        ledger: ThreatLedger,
        modifier_data: dict = None,
        ability_library: dict = None,
    ):
        self.id = enemy_id
        self.name = enemy_data.get("name", "Unknown Node")
        self.description = enemy_data.get("description", "No intel available.")
        self.weapon = enemy_data.get("weapon", "Counter-Suite")
        base_os = enemy_data.get("base_os", 10)
        budget = enemy_data.get("budget", 0)

        self.damage_multiplier = 1.0
        self.player_ram_modifier = 0
        self.player_crypto_bonus = 0
        self.trace_penalty = 0
        self.disconnect_lock = enemy_data.get("disconnect_lock", False)

        ability_names = list(enemy_data.get("abilities", []))

        if modifier_data:
            self.name = modifier_data.get("prefix", "") + self.name
            base_os += modifier_data.get("base_os_bonus", 0)
            budget += modifier_data.get("budget_bonus", 0)
            self.damage_multiplier = modifier_data.get("enemy_damage_multiplier", 1.0)
            self.player_ram_modifier = modifier_data.get("player_ram_modifier", 0)
            self.player_crypto_bonus = modifier_data.get("player_crypto_bonus", 0)
            self.trace_penalty = modifier_data.get("trace_penalty", 0)
            for bonus_ability in modifier_data.get("bonus_abilities", []):
                if bonus_ability not in ability_names:
                    ability_names.append(bonus_ability)

        weakness = str(enemy_data.get("weakness", "NONE")).upper()
        if weakness == "RANDOM":
            weakness = random.choice(["SEC", "NET", "MEM", "STO"])
        self.weakness = weakness
        self.owner_profile = self.generate_owner_profile()

        self.identity_revealed = False
        self.weapon_revealed = False
        self.topology_revealed = False
        self.telemetry_targets = set()
        self.intent_revealed = False
        self.weakness_revealed = False
        self.recon_exposure = 0
        self.recon_discount = 0
        self.player_topology_revealed = False
        self.player_signature_revealed = False
        self.security_breach_turns = 0
        self.turn_counter = 0
        self.forced_finisher_turn = enemy_data.get("forced_finisher_turn")
        self.current_intent = {"name": "Idle", "kind": "idle", "damage": 0}
        self.intent_jam_turns = 0
        self.last_player_script = None
        self.player_script_streak = 0
        self.last_player_target = None
        self.player_target_streak = 0
        self.player_loud_streak = 0

        self.subsystems = {
            "OS": Subsystem("Core OS", base_os),
            "SEC": Subsystem("Firewall", 0),
            "NET": Subsystem("Proxy", 0),
            "MEM": Subsystem("Memory", 10),
            "STO": Subsystem("Storage", 10),
        }
        self.player_focus_counts = {key: 0 for key in self.subsystems}
        self.endpoint_hits = set()
        self.credential_pressure_turns = {key: 0 for key in self.subsystems}
        self.repair_lock_turns = {key: 0 for key in self.subsystems}
        self.timing_windows = {key: 0 for key in self.subsystems}
        self.fingerprint_windows = {key: 0 for key in self.subsystems}

        self.allocate_budget(budget, ledger)
        self.open_ports = self.generate_attack_surface()
        self.endpoints = self.generate_endpoint_hints()

        ability_library = ability_library or {}
        self.abilities = []
        for ability_name in ability_names:
            if ability_name in ability_library:
                payload = dict(ability_library[ability_name])
                payload["id"] = ability_name
                self.abilities.append(payload)

    def ensure_runtime_defaults(self):
        if not hasattr(self, "owner_profile"):
            self.owner_profile = self.generate_owner_profile()
        if not hasattr(self, "open_ports"):
            self.open_ports = self.generate_attack_surface()
        if not hasattr(self, "endpoints"):
            self.endpoints = self.generate_endpoint_hints()
        if not hasattr(self, "endpoint_hits"):
            self.endpoint_hits = set()
        else:
            self.endpoint_hits = set(self.endpoint_hits)
        if not hasattr(self, "credential_pressure_turns"):
            self.credential_pressure_turns = {key: 0 for key in self.subsystems}
        else:
            for key in self.subsystems:
                self.credential_pressure_turns.setdefault(key, 0)
        if not hasattr(self, "repair_lock_turns"):
            self.repair_lock_turns = {key: 0 for key in self.subsystems}
        else:
            for key in self.subsystems:
                self.repair_lock_turns.setdefault(key, 0)
        if not hasattr(self, "timing_windows"):
            self.timing_windows = {key: 0 for key in self.subsystems}
        else:
            for key in self.subsystems:
                self.timing_windows.setdefault(key, 0)
        if not hasattr(self, "fingerprint_windows"):
            self.fingerprint_windows = {key: 0 for key in self.subsystems}
        else:
            for key in self.subsystems:
                self.fingerprint_windows.setdefault(key, 0)

    @property
    def is_scanned(self):
        return self.topology_revealed

    @is_scanned.setter
    def is_scanned(self, value):
        self.topology_revealed = bool(value)

    @property
    def telemetry_revealed(self):
        return len(self.telemetry_targets) >= len(self.subsystems)

    def reveal_surface(self):
        self.identity_revealed = True
        self.weapon_revealed = True
        self.topology_revealed = True

    def reveal_identity(self):
        self.identity_revealed = True

    def generate_owner_profile(self):
        node_id = self.id.lower()
        name = self.name.lower()
        if any(token in node_id for token in ("grandma", "laptop", "minecraft", "streamer", "family")):
            return ("consumer isp", "residential subscriber", "dynamic allocation")
        if any(token in node_id for token in ("campus", "research")):
            return ("regional university network", "campus operations", "shared academic allocation")
        if any(token in node_id for token in ("civic", "sentinel", "omnicorp", "aegis")):
            return ("managed backbone provider", "enterprise security operations", "registered infrastructure block")
        if any(token in node_id for token in ("weather", "ipcam", "fridge", "plc")):
            return ("embedded fleet operator", "field device management", "industrial or iot allocation")
        if "mail" in node_id:
            return ("mail transit provider", "message relay operations", "registered edge relay")
        if "router" in node_id or "vpn" in node_id:
            return ("regional transit operator", "network edge services", "static transit allocation")
        if "backup" in node_id or "nas" in node_id or "archive" in name:
            return ("storage contractor", "backup operations", "retention network")
        return ("small hosting provider", "single tenant services", "colo address space")

    def generate_attack_surface(self):
        if self.id == "training_drone":
            return [
                {"port": "22/tcp", "service": "ssh", "banner": "Dropbear SSH", "subsystem": "SEC"},
                {"port": "8080/tcp", "service": "proxy", "banner": "Training proxy", "subsystem": "NET"},
                {"port": "3306/tcp", "service": "mysql", "banner": "Demo datastore", "subsystem": "STO"},
            ]
        if self.id == "aegis_black_ice":
            return [
                {"port": "443/tcp", "service": "https", "banner": "Policy ingress", "subsystem": "SEC"},
                {"port": "8443/tcp", "service": "https-admin", "banner": "Counter-intrusion console", "subsystem": "SEC"},
                {"port": "53/udp", "service": "dns", "banner": "Sinkhole resolver", "subsystem": "NET"},
                {"port": "6379/tcp", "service": "redis", "banner": "Response cache", "subsystem": "MEM"},
                {"port": "5432/tcp", "service": "postgres", "banner": "Incident ledger", "subsystem": "STO"},
            ]

        chosen = []
        used_ports = set()
        target_count = random.randint(3, 4)
        preferred = []
        if self.weakness in self.SERVICE_POOLS:
            preferred.append(self.weakness)
        preferred.extend(["NET", "SEC", "MEM", "STO"])

        for subsystem_key in preferred:
            if len(chosen) >= target_count:
                break
            pool = [dict(entry) for entry in self.SERVICE_POOLS.get(subsystem_key, ()) if entry["port"] not in used_ports]
            if not pool:
                continue
            sample = random.choice(pool)
            sample["subsystem"] = subsystem_key
            used_ports.add(sample["port"])
            chosen.append(sample)

        while len(chosen) < 3:
            subsystem_key = random.choice(["SEC", "NET", "MEM", "STO"])
            pool = [dict(entry) for entry in self.SERVICE_POOLS.get(subsystem_key, ()) if entry["port"] not in used_ports]
            if not pool:
                break
            sample = random.choice(pool)
            sample["subsystem"] = subsystem_key
            used_ports.add(sample["port"])
            chosen.append(sample)

        return sorted(chosen, key=lambda entry: int(entry["port"].split("/")[0]))

    def generate_endpoint_hints(self):
        endpoint_map = {}
        for subsystem_key in ("SEC", "NET", "MEM", "STO"):
            base_paths = list(self.ENDPOINT_HINTS.get(subsystem_key, ()))
            count = 2 if self.has_web_surface(subsystem_key) else 1
            endpoint_map[subsystem_key] = random.sample(base_paths, k=min(count, len(base_paths)))
        return endpoint_map

    def get_ports_for_subsystem(self, subsystem_key: str | None = None):
        if subsystem_key is None:
            return list(self.open_ports)
        return [entry for entry in self.open_ports if entry["subsystem"] == subsystem_key]

    def has_auth_surface(self, subsystem_key: str | None = None):
        return any(entry["service"] in self.AUTH_SERVICES for entry in self.get_ports_for_subsystem(subsystem_key))

    def has_web_surface(self, subsystem_key: str | None = None):
        return any(entry["service"] in self.HTTP_SERVICES for entry in self.get_ports_for_subsystem(subsystem_key))

    def has_db_surface(self, subsystem_key: str | None = None):
        return any(entry["service"] in self.DB_SERVICES for entry in self.get_ports_for_subsystem(subsystem_key))

    def get_surface_report_lines(self):
        lines = []
        for entry in self.open_ports:
            lines.append(
                f"         {entry['port']:<8} open  {entry['service']:<12} {entry['banner']} -> [{entry['subsystem']}]"
            )
        return lines

    def get_service_summary(self, subsystem_key: str | None = None):
        ports = self.get_ports_for_subsystem(subsystem_key)
        if not ports:
            return "no open services"
        return ", ".join(f"{entry['port']} {entry['service']}" for entry in ports)

    def get_endpoint_summary(self, subsystem_key: str):
        hints = self.endpoints.get(subsystem_key, [])
        if not hints:
            return "no directory hits"
        return ", ".join(hints)

    def mark_endpoint_hits(self, subsystem_key: str):
        self.endpoint_hits.add(subsystem_key)

    def has_endpoint_hits(self, subsystem_key: str):
        return subsystem_key in self.endpoint_hits

    def arm_credential_pressure(self, subsystem_key: str, turns: int = 2):
        self.credential_pressure_turns[subsystem_key] = max(
            self.credential_pressure_turns.get(subsystem_key, 0),
            max(1, turns),
        )

    def has_credential_pressure(self, subsystem_key: str):
        return self.credential_pressure_turns.get(subsystem_key, 0) > 0

    def arm_repair_lock(self, subsystem_key: str, turns: int = 2):
        self.repair_lock_turns[subsystem_key] = max(
            self.repair_lock_turns.get(subsystem_key, 0),
            max(1, turns),
        )

    def get_repair_lock_turns(self, subsystem_key: str):
        return self.repair_lock_turns.get(subsystem_key, 0)

    def arm_timing_window(self, subsystem_key: str, turns: int = 1):
        self.timing_windows[subsystem_key] = max(
            self.timing_windows.get(subsystem_key, 0),
            max(1, turns),
        )

    def get_timing_window(self, subsystem_key: str):
        return self.timing_windows.get(subsystem_key, 0)

    def arm_fingerprint_window(self, subsystem_key: str, turns: int = 2):
        self.fingerprint_windows[subsystem_key] = max(
            self.fingerprint_windows.get(subsystem_key, 0),
            max(1, turns),
        )

    def get_fingerprint_window(self, subsystem_key: str):
        return self.fingerprint_windows.get(subsystem_key, 0)

    def get_whois_summary_lines(self):
        owner, role, allocation = self.owner_profile
        return [
            f"         org: {owner}",
            f"         role: {role}",
            f"         netrange: {allocation}",
        ]

    def reveal_telemetry(self, target_key: str | None = None):
        self.reveal_surface()
        if target_key is None:
            self.telemetry_targets = set(self.subsystems.keys())
        else:
            self.telemetry_targets.add(target_key)

    def has_telemetry_for(self, target_key: str):
        return self.telemetry_revealed or target_key in self.telemetry_targets

    def get_visible_name(self):
        return self.name if self.identity_revealed else "UNKNOWN HOST"

    def get_visible_weapon(self):
        return self.weapon if self.weapon_revealed else "UNKNOWN"

    def get_recon_alert_stage(self):
        if self.player_signature_revealed:
            return 2
        if self.player_topology_revealed:
            return 1
        return 0

    def get_recon_alert_text(self):
        stage = self.get_recon_alert_stage()
        if stage == 0:
            text = "Cold link. No hostile handshake detected yet."
        elif stage == 1:
            text = "Surface leak. They have a rough map of your node."
        else:
            text = "Burning link. Your signature is already on their scope."

        if self.recon_discount > 0:
            text += f" Quiet window primed (-{self.recon_discount} exposure on next recon action)."
        return text

    def apply_recon_exposure(self, amount: int):
        self.recon_exposure += max(0, amount)
        new_stage = self.get_recon_alert_stage()

        if self.recon_exposure >= 75:
            self.player_topology_revealed = True
            self.player_signature_revealed = True
            if new_stage < 2:
                return 2
            return 0

        if self.recon_exposure >= 40:
            self.player_topology_revealed = True
            if new_stage < 1:
                return 1

        return 0

    def allocate_budget(self, budget: int, ledger: ThreatLedger):
        if budget <= 0:
            return

        primary_threat = ledger.get_primary_threat()

        if primary_threat == "brute_force":
            self.subsystems["SEC"].max_hp += budget
            self.subsystems["SEC"].current_hp += budget
        elif primary_threat == "exploit":
            self.subsystems["NET"].max_hp += budget
            self.subsystems["NET"].current_hp += budget
        else:
            half = budget // 2
            self.subsystems["SEC"].max_hp += half
            self.subsystems["SEC"].current_hp += half
            self.subsystems["NET"].max_hp += (budget - half)
            self.subsystems["NET"].current_hp += (budget - half)

        for key in ("SEC", "NET"):
            self.subsystems[key].is_destroyed = self.subsystems[key].current_hp <= 0

    def get_ability_by_kind(self, kind: str):
        for ability in self.abilities:
            if ability.get("kind") == kind:
                return ability
        return None

    def get_damage_ability_pool(self, player: Player):
        pool = []
        for ability in self.abilities:
            kind = ability.get("kind")
            if kind not in {"attack", "trace", "repair", "ram_lock", "drain", "strip_defense"}:
                continue

            weight = ability.get("weight", 1)
            target = ability.get("target")

             # With NET offline the node loses most of its tracking and recon throughput.
            if kind == "trace" and self.subsystems["NET"].is_destroyed:
                continue

            if kind == "repair":
                target_subsystem = self.subsystems.get(target, self.subsystems["SEC"])
                if target_subsystem.current_hp >= target_subsystem.max_hp:
                    continue
            elif kind == "strip_defense":
                chosen_target = target if target in player.subsystems else None
                if not player.has_active_defenses(chosen_target):
                    continue
            elif target in player.subsystems and player.subsystems[target].is_destroyed:
                continue

            if self.player_signature_revealed and target == player.signature_subsystem:
                weight += 2

            pool.extend([ability] * max(1, weight))

        return pool

    def get_attack_ability_for_target(self, target_key: str):
        for ability in self.abilities:
            if ability.get("kind") == "attack" and ability.get("target") == target_key:
                return ability
        for ability in self.abilities:
            if ability.get("kind") == "drain" and ability.get("target") == target_key:
                return ability
        return None

    def observe_player_action(self, parsed_command, script_data: dict, target_subsystem: str | None = None, success: bool = True):
        if not success:
            return

        script_name = parsed_command.base_cmd
        script_type = script_data.get("type", "unknown")
        offensive = script_type in {"brute_force", "exploit"}
        loud = offensive and "--stealth" not in parsed_command.flags

        if script_name == self.last_player_script:
            self.player_script_streak += 1
        else:
            self.last_player_script = script_name
            self.player_script_streak = 1

        if offensive and target_subsystem in self.subsystems:
            if target_subsystem == self.last_player_target:
                self.player_target_streak += 1
            else:
                self.last_player_target = target_subsystem
                self.player_target_streak = 1
            self.player_focus_counts[target_subsystem] = self.player_focus_counts.get(target_subsystem, 0) + 1
        elif not offensive:
            self.last_player_target = None
            self.player_target_streak = 0

        if loud:
            self.player_loud_streak += 1
        else:
            self.player_loud_streak = max(0, self.player_loud_streak - 1)

    def blur_adaptation(self, amount: int = 1):
        amount = max(1, amount)
        self.player_script_streak = max(0, self.player_script_streak - amount)
        if self.player_script_streak == 0:
            self.last_player_script = None

        self.player_target_streak = max(0, self.player_target_streak - amount)
        if self.last_player_target in self.player_focus_counts:
            self.player_focus_counts[self.last_player_target] = max(
                0,
                self.player_focus_counts.get(self.last_player_target, 0) - amount,
            )
        if self.player_target_streak == 0:
            self.last_player_target = None

        self.player_loud_streak = max(0, self.player_loud_streak - amount)

    def clear_adaptation_state(self):
        self.last_player_script = None
        self.player_script_streak = 0
        self.last_player_target = None
        self.player_target_streak = 0
        self.player_loud_streak = 0
        self.player_focus_counts = {key: 0 for key in self.subsystems}

    def get_adaptive_mitigation(self, script_name: str, script_type: str, target_subsystem: str, flags):
        if script_type not in {"brute_force", "exploit"} or target_subsystem not in self.subsystems:
            return 0, []

        mitigation = 0
        reasons = []

        if script_name == self.last_player_script and self.player_script_streak >= 1:
            cached = min(3, self.player_script_streak)
            mitigation += cached
            reasons.append("payload signature cached")

        if target_subsystem == self.last_player_target and self.player_target_streak >= 1:
            screened = min(3, self.player_target_streak)
            mitigation += screened
            if target_subsystem == "OS":
                reasons.append("core lane screened")
            else:
                reasons.append(f"{target_subsystem} route screened")

        if target_subsystem == "OS" and not self.subsystems["SEC"].is_destroyed and self.player_focus_counts.get("OS", 0) >= 2:
            mitigation += 1
            reasons.append("firewall routing tightened")

        if "--stealth" in flags and mitigation > 0:
            mitigation = max(0, mitigation - 1)

        return mitigation, reasons

    def apply_counterintel_pressure(self, parsed_command, script_data: dict, target_subsystem: str | None = None):
        script_type = script_data.get("type", "unknown")
        if script_type not in {"brute_force", "exploit"} or "--stealth" in parsed_command.flags:
            return 0

        exposure = 8 + min(16, self.player_loud_streak * 4)
        if target_subsystem == self.last_player_target and self.player_target_streak >= 2:
            exposure += 6
        if parsed_command.base_cmd == self.last_player_script and self.player_script_streak >= 2:
            exposure += 4
        if target_subsystem == "OS":
            exposure += 4

        return self.apply_recon_exposure(exposure)

    def get_adaptation_summary(self):
        labels = []
        if self.player_script_streak >= 2 and self.last_player_script:
            labels.append(f"caching {self.last_player_script}")
        if self.player_target_streak >= 2 and self.last_player_target:
            labels.append(f"screening {self.last_player_target}")
        if self.player_loud_streak >= 2:
            labels.append("tracking noisy traffic")
        return " | ".join(labels[:3])

    def choose_reactive_intent(self, player: Player):
        defense_breaker = self.get_ability_by_kind("strip_defense")
        if defense_breaker:
            likely_target = None
            if self.last_player_target in player.subsystems and player.has_active_defenses(self.last_player_target):
                likely_target = self.last_player_target
            elif player.mirror_target and player.has_active_defenses(player.mirror_target):
                likely_target = player.mirror_target
            elif player.tripwire_target and player.has_active_defenses(player.tripwire_target):
                likely_target = player.tripwire_target
            elif player.scan_jammer_turns > 0:
                likely_target = "NET"
            if likely_target:
                return self.build_intent(defense_breaker, target_override=likely_target)

        if self.player_target_streak >= 2 and self.last_player_target == "OS":
            repair_ability = self.get_ability_by_kind("repair")
            if repair_ability and not self.subsystems["SEC"].is_destroyed:
                sec = self.subsystems["SEC"]
                if sec.current_hp < sec.max_hp:
                    return self.build_intent(repair_ability)

        if self.player_loud_streak >= 2 and not self.subsystems["NET"].is_destroyed:
            trace_ability = self.get_ability_by_kind("trace")
            if trace_ability:
                return self.build_intent(trace_ability)

        if self.player_script_streak >= 2 or self.player_target_streak >= 2:
            ram_lock = self.get_ability_by_kind("ram_lock")
            if ram_lock and not player.subsystems["MEM"].is_destroyed:
                return self.build_intent(ram_lock)

            if not player.subsystems["MEM"].is_destroyed:
                mem_attack = self.get_attack_ability_for_target("MEM")
                if mem_attack:
                    return self.build_intent(mem_attack)

            if not player.subsystems["NET"].is_destroyed:
                net_attack = self.get_attack_ability_for_target("NET")
                if net_attack:
                    return self.build_intent(net_attack)

        return None

    def prep_turn(self, player: Player):
        self.turn_counter += 1

        if self.intent_jam_turns > 0:
            self.intent_jam_turns -= 1
            self.current_intent = {"name": "Signal Jammed", "kind": "idle", "damage": 0}
            return

        if self.forced_finisher_turn and self.turn_counter >= self.forced_finisher_turn:
            finisher = self.get_ability_by_kind("finisher")
            if finisher:
                self.current_intent = self.build_intent(finisher)
                return

        if not self.player_topology_revealed and not self.subsystems["NET"].is_destroyed:
            scan_ability = self.get_ability_by_kind("scan_topology")
            if scan_ability:
                self.current_intent = self.build_intent(scan_ability)
                return

        if self.player_topology_revealed and not self.player_signature_revealed and not self.subsystems["NET"].is_destroyed:
            fingerprint = self.get_ability_by_kind("scan_signature")
            if fingerprint:
                self.current_intent = self.build_intent(fingerprint)
                return

        reactive_intent = self.choose_reactive_intent(player)
        if reactive_intent:
            self.current_intent = reactive_intent
            return

        repair_threshold = max(1, self.subsystems["SEC"].max_hp // 3)
        if self.subsystems["SEC"].current_hp <= repair_threshold:
            repair_ability = self.get_ability_by_kind("repair")
            if repair_ability and random.random() < 0.5:
                self.current_intent = self.build_intent(repair_ability)
                return

        pool = self.get_damage_ability_pool(player)
        chosen = random.choice(pool) if pool else {"name": "Idle", "kind": "idle", "damage": 0}
        self.current_intent = self.build_intent(chosen)

    def build_intent(self, ability: dict, target_override: str | None = None):
        intent = dict(ability)
        intent.setdefault("name", "Idle")
        intent.setdefault("kind", "idle")
        intent.setdefault("damage", 0)
        if target_override:
            intent["target"] = target_override
        mem_ratio = self.subsystems["MEM"].current_hp / max(1, self.subsystems["MEM"].max_hp)
        if intent["kind"] in {"attack", "drain", "finisher"}:
            base_damage = int(intent.get("damage", 0) * self.damage_multiplier * max(0.4, mem_ratio))
            intent["damage"] = max(1, base_damage)
        if intent["kind"] == "repair":
            intent["amount"] = max(1, int(intent.get("amount", 0) * max(0.5, mem_ratio)))
        return intent

    def scrub_player_recon_stage(self, stages: int = 1):
        scrubbed = 0
        for _ in range(max(1, stages)):
            if self.player_signature_revealed:
                self.player_signature_revealed = False
                scrubbed += 1
                continue
            if self.player_topology_revealed:
                self.player_topology_revealed = False
                scrubbed += 1
        if not self.player_topology_revealed:
            self.recon_exposure = min(self.recon_exposure, 39)
        elif not self.player_signature_revealed:
            self.recon_exposure = min(self.recon_exposure, 74)
        return scrubbed

    def resolve_intent(self, player: Player, game_state):
        intent = self.current_intent
        kind = intent.get("kind", "idle")
        lines = []
        visible_name = self.get_visible_name()

        if kind == "scan_topology":
            if player.consume_scan_jammer():
                lines.append(f"{visible_name} tried to map your node, but your honeypot fed it garbage.")
                return lines, None
            player.topology_exposed = True
            self.player_topology_revealed = True
            lines.append(f"{visible_name} mapped your node topology.")
            return lines, None

        if kind == "scan_signature":
            if player.consume_scan_jammer():
                lines.append(f"{visible_name} tried to fingerprint you, but your honeypot burned the trace.")
                return lines, None
            reflected = player.consume_mirror(player.signature_subsystem, intent.get("damage", 0))
            if reflected > 0:
                dealt = self.subsystems["OS"].take_damage(reflected)
                lines.append(f"Your sinkhole on [{player.signature_subsystem}] kicked the scan back for {dealt} damage.")
                lines.append(f"{visible_name}'s signature sweep collapsed before it completed.")
                return lines, None
            trap_damage = player.consume_tripwire(player.signature_subsystem)
            if trap_damage > 0:
                dealt = self.subsystems["OS"].take_damage(trap_damage)
                lines.append(
                    f"Your canary on [{player.signature_subsystem}] backfired into {visible_name} for {dealt} damage."
                )
                lines.append(f"{visible_name}'s signature sweep collapsed before it completed.")
                return lines, None
            player.signature_revealed = True
            self.player_signature_revealed = True
            lines.append(
                f"{visible_name} fingerprinted [{player.signature_subsystem}]. "
                f"{player.get_signature_bonus_text(player.signature_subsystem)}"
            )
            return lines, None

        if kind == "repair":
            target_key = intent.get("target", "SEC")
            target = self.subsystems.get(target_key, self.subsystems["SEC"])
            if self.get_repair_lock_turns(target_key) > 0:
                lines.append(
                    f"{visible_name} tried to run {intent['name']} on [{target_key}], "
                    "but the lane was too corrupted to recover."
                )
                return lines, None
            restored = target.repair(intent.get("amount", 0))
            lines.append(f"{visible_name} ran {intent['name']} and restored {restored} integrity to [{target_key}].")
            return lines, None

        if kind == "trace":
            trace_gain = intent.get("trace", 0)
            game_state.trace_level += trace_gain
            lines.append(f"{visible_name} executed {intent['name']}. Trace Level increased by {trace_gain}.")
            return lines, None

        if kind == "ram_lock":
            amount = intent.get("amount", 0)
            turns = intent.get("turns", 1)
            reflected = player.consume_mirror(intent.get("target", "MEM"), amount + 1)
            if reflected > 0:
                dealt = self.subsystems["OS"].take_damage(reflected)
                lines.append(
                    f"Your sinkhole on [{intent.get('target', 'MEM')}] reflected the control spike for {dealt} damage."
                )
                lines.append(f"{visible_name}'s control payload collapsed before it locked your RAM.")
                return lines, None
            trap_damage = player.consume_tripwire(intent.get("target", "OS"))
            if trap_damage > 0:
                dealt = self.subsystems["OS"].take_damage(trap_damage)
                lines.append(
                    f"Your canary on [{intent.get('target', 'OS')}] detonated into {visible_name} for {dealt} damage."
                )
                lines.append(f"{visible_name}'s control payload fizzled before it locked your RAM.")
                return lines, None
            player.apply_ram_lock(amount, turns)
            lines.append(
                f"{visible_name} executed {intent['name']}. "
                f"Your RAM ceiling is reduced by {amount} for {turns} turns."
            )
            return lines, None

        if kind == "strip_defense":
            target_key = intent.get("target")
            reflected = 0
            if target_key:
                reflected = player.consume_mirror(target_key, intent.get("damage", 0))
            if reflected > 0:
                dealt = self.subsystems["OS"].take_damage(reflected)
                lines.append(f"Your sinkhole on [{target_key}] flashed the breach tools back for {dealt} damage.")
                lines.append(f"{visible_name}'s defense breaker lost lock.")
                return lines, None

            trap_damage = player.consume_tripwire(target_key) if target_key else 0
            if trap_damage > 0:
                dealt = self.subsystems["OS"].take_damage(trap_damage)
                lines.append(f"Your canary on [{target_key}] detonated into {visible_name} for {dealt} damage.")
                lines.append(f"{visible_name}'s defense breaker collapsed before it landed.")
                return lines, None

            removed = player.strip_active_defenses(target_key)
            if removed:
                lines.append(
                    f"{visible_name} ran {intent['name']} and stripped "
                    f"{', '.join(removed)}."
                )
            else:
                lines.append(f"{visible_name} ran {intent['name']} but found no live defenses to break.")
            return lines, None

        if kind in {"attack", "drain", "finisher"}:
            target_key = intent.get("target", "OS")
            target = player.subsystems.get(target_key, player.subsystems["OS"])
            damage = intent.get("damage", 0)

            trap_damage = player.consume_tripwire(target_key)
            if trap_damage > 0 and kind != "finisher":
                dealt = self.subsystems["OS"].take_damage(trap_damage)
                lines.append(f"Your canary on [{target_key}] detonated into {visible_name} for {dealt} damage.")
                lines.append(f"{visible_name}'s {intent['name']} collapsed before it executed.")
                return lines, None

            if self.player_signature_revealed and target_key == player.signature_subsystem:
                damage += intent.get("signature_bonus", 2)
                lines.append(f"{visible_name} exploited your revealed [{target_key}] signature for bonus damage.")

            reflected = player.consume_mirror(target_key, damage)
            if reflected > 0 and kind != "finisher":
                dealt = self.subsystems["OS"].take_damage(reflected)
                lines.append(f"Your sinkhole on [{target_key}] reflected the hit back for {dealt} damage.")
                lines.append(f"{visible_name}'s {intent['name']} lost coherence and collapsed.")
                return lines, None

            if target_key == "OS" and not player.subsystems["SEC"].is_destroyed:
                os_damage = max(1, damage // 3)
                redirected = max(0, damage - os_damage)
                sec_spill = player.subsystems["SEC"].take_damage(redirected)
                damage = os_damage
                if sec_spill > 0:
                    lines.append(f"Your firewall intercepted {sec_spill} damage before it reached Core OS.")

            blocked, remaining_damage = player.absorb_guard(target_key, damage)
            if blocked > 0:
                lines.append(f"Your ACL shell absorbed {blocked} damage on [{target_key}].")

            dealt = target.take_damage(remaining_damage)
            lines.append(f"{visible_name} used {intent['name']} on your [{target_key}] and dealt {dealt} damage.")

            if kind == "drain":
                crypto_loss = min(game_state.player_crypto, intent.get("crypto", 0))
                game_state.player_crypto -= crypto_loss
                if crypto_loss > 0:
                    lines.append(f"{crypto_loss} Crypto was siphoned from your storage.")

            if target.is_destroyed and target_key != "OS":
                cascade = player.subsystems["OS"].take_damage(2)
                if cascade > 0:
                    lines.append(f"[{target_key}] collapse rattled your Core OS for {cascade} damage.")
                if target_key == "NET":
                    lines.append("Your uplink collapsed. Deep scans and clean disconnects are offline.")
                elif target_key == "MEM":
                    lines.append("Your memory banks are damaged. Available RAM is dropping.")
                elif target_key == "SEC":
                    lines.append("Your firewall lattice is down. Enemy recon accelerates.")
                elif target_key == "STO":
                    lines.append("Your storage cluster is in failure. Loot is no longer secure.")

            if kind == "finisher":
                return lines, "burn_notice"

            return lines, None

        lines.append(f"{visible_name} idled.")
        return lines, None

    def tick_end_of_turn(self):
        if self.security_breach_turns > 0:
            self.security_breach_turns -= 1
        for key in self.subsystems:
            if self.credential_pressure_turns.get(key, 0) > 0:
                self.credential_pressure_turns[key] -= 1
            if self.repair_lock_turns.get(key, 0) > 0:
                self.repair_lock_turns[key] -= 1
            if self.timing_windows.get(key, 0) > 0:
                self.timing_windows[key] -= 1
            if self.fingerprint_windows.get(key, 0) > 0:
                self.fingerprint_windows[key] -= 1

    @staticmethod
    def classify_shell(subsystem: Subsystem):
        if subsystem.max_hp <= 4:
            return "THIN"
        if subsystem.max_hp <= 8:
            return "LIGHT"
        if subsystem.max_hp <= 12:
            return "STANDARD"
        if subsystem.max_hp <= 16:
            return "HARDENED"
        return "FORTIFIED"

    @staticmethod
    def classify_pressure(subsystem: Subsystem):
        if subsystem.current_hp <= 0:
            return "OFFLINE"

        ratio = subsystem.current_hp / max(1, subsystem.max_hp)
        if ratio <= 0.25:
            return "CRITICAL"
        if ratio <= 0.5:
            return "SHAKY"
        if ratio <= 0.75:
            return "PRESSURED"
        return "STABLE"

    def print_status(self):
        print(f"\n\033[96m--- TARGET: {self.get_visible_name()} ---\033[0m")
        print(f"\033[90m[COUNTERMEASURE] {self.get_visible_weapon()}\033[0m")
        if not self.topology_revealed:
            print("\033[90m[PORT MAP] UNRESOLVED\033[0m")
            print("\033[90m[WEAK POINT] UNRESOLVED\033[0m")
            print("\033[90m[SUBSYSTEMS] UNRESOLVED\033[0m")
        else:
            if self.weakness_revealed:
                print(f"\033[93m[WEAK POINT] [{self.weakness}] (2x damage once reached)\033[0m")
            else:
                if self.subsystems["SEC"].is_destroyed or self.security_breach_turns > 0:
                    print("\033[90m[WEAK POINT] FINGERPRINT PENDING (perimeter open)\033[0m")
                else:
                    print("\033[90m[WEAK POINT] MASKED BY PERIMETER CONTROLS\033[0m")

            print(f"\033[90m[PORT MAP] {self.get_service_summary()}\033[0m")

            for key, sub in self.subsystems.items():
                if self.has_telemetry_for(key):
                    color = "\033[91m" if sub.current_hp == 0 else "\033[92m"
                    print(f"{color}[{key}] {sub.name}: {sub.current_hp}/{sub.max_hp} HP\033[0m")
                else:
                    status = "OFFLINE" if sub.current_hp == 0 else "ONLINE"
                    print(f"\033[90m[{key}] {sub.name}: PRESENT / {status} / HP UNKNOWN\033[0m")

            if self.security_breach_turns > 0:
                print(f"\033[93m[SECURITY] Firewall disrupted for {self.security_breach_turns} more turn(s).\033[0m")

            adaptation_summary = self.get_adaptation_summary()
            if adaptation_summary:
                print(f"\033[93m[ADAPTIVE DEFENSE] {adaptation_summary}\033[0m")

        print("\033[96m----------------------------\033[0m\n")
