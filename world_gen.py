import random
from collections import deque


class Node:
    def __init__(self, ip_address, node_type, difficulty):
        self.ip_address = ip_address
        self.node_type = node_type
        self.difficulty = difficulty
        self.is_hostile = node_type not in ["shop"]
        self.cached_enemy = None
        self.recon_log = []
        self.route_depth = 1
        self.compromise_state = "live"
        self.root_access = False
        self.locked_data = False
        self.module_slots = 0
        self.map_flags = []
        self.installed_module = None
        self.domain_id = ip_address
        self.subnet_id = None
        self.worm_level = 0
        self.worm_origin = None
        self.worm_corruption = 0
        self.pending_subsystem_damage = {}
        self.forensic_complete = False
        self.revolt_state = None
        self.lockdown_turns = 0
        self.spawn_seed = 0

    def ensure_runtime_defaults(self):
        if not hasattr(self, "cached_enemy"):
            self.cached_enemy = None
        if not hasattr(self, "recon_log"):
            self.recon_log = []
        if not hasattr(self, "route_depth"):
            self.route_depth = 1
        if not hasattr(self, "compromise_state"):
            self.compromise_state = "live"
        if not hasattr(self, "root_access"):
            self.root_access = False
        if not hasattr(self, "locked_data"):
            self.locked_data = False
        if not hasattr(self, "module_slots"):
            self.module_slots = 0
        if not hasattr(self, "map_flags"):
            self.map_flags = []
        if not hasattr(self, "installed_module"):
            self.installed_module = None
        if not hasattr(self, "domain_id"):
            self.domain_id = self.ip_address
        if not hasattr(self, "subnet_id"):
            self.subnet_id = None
        if not hasattr(self, "worm_level"):
            self.worm_level = 0
        if not hasattr(self, "worm_origin"):
            self.worm_origin = None
        if not hasattr(self, "worm_corruption"):
            self.worm_corruption = 0
        if not hasattr(self, "pending_subsystem_damage"):
            self.pending_subsystem_damage = {}
        if not hasattr(self, "forensic_complete"):
            self.forensic_complete = False
        if not hasattr(self, "revolt_state"):
            self.revolt_state = None
        if not hasattr(self, "lockdown_turns"):
            self.lockdown_turns = 0
        if not hasattr(self, "spawn_seed"):
            self.spawn_seed = 0


class InternetMap:
    def __init__(self, subnet_name):
        self.subnet_name = subnet_name
        self.nodes = []
        self.links = {}
        self.forward_links = {}
        self.backward_links = {}
        self.entry_links = set()
        self.node_depths = {}
        self.subnet_id = subnet_name
        self.domain_id = None

    def add_node(self, node):
        if hasattr(node, "ensure_runtime_defaults"):
            node.ensure_runtime_defaults()
        self.nodes.append(node)
        index = len(self.nodes) - 1
        self.links[index] = set()
        self.forward_links[index] = set()
        self.backward_links[index] = set()
        return index

    def link_nodes(self, source_index, target_index, *, bidirectional=False):
        self.forward_links.setdefault(source_index, set()).add(target_index)
        self.backward_links.setdefault(target_index, set()).add(source_index)
        self.links.setdefault(source_index, set()).add(target_index)
        self.links.setdefault(target_index, set()).add(source_index)

        if bidirectional:
            self.forward_links.setdefault(target_index, set()).add(source_index)
            self.backward_links.setdefault(source_index, set()).add(target_index)

    def set_entry_link(self, node_index):
        self.entry_links.add(node_index)

    def can_route_to(self, node_index, cleared_nodes):
        if node_index in self.entry_links:
            return True
        return any(source_index in cleared_nodes for source_index in self.backward_links.get(node_index, set()))

    def can_traverse_from(self, current_index, node_index, cleared_nodes):
        if current_index is None:
            return self.can_route_to(node_index, cleared_nodes)
        if node_index == current_index:
            return True
        if node_index not in self.links.get(current_index, set()):
            return False
        if node_index in cleared_nodes:
            return True
        if node_index in self.entry_links:
            return True
        if current_index in self.backward_links.get(node_index, set()) and current_index in cleared_nodes:
            return True
        return self.can_route_to(node_index, cleared_nodes)

    def get_unlock_sources(self, node_index):
        return sorted(self.backward_links.get(node_index, set()))

    def ensure_runtime_defaults(self):
        if not hasattr(self, "forward_links"):
            self.forward_links = {index: set(neighbors) for index, neighbors in self.links.items()}
        if not hasattr(self, "backward_links"):
            self.backward_links = {index: set() for index in range(len(self.nodes))}
            for source_index, neighbors in self.forward_links.items():
                for target_index in neighbors:
                    self.backward_links.setdefault(target_index, set()).add(source_index)
        if not hasattr(self, "entry_links"):
            self.entry_links = set()
        if not hasattr(self, "node_depths"):
            self.node_depths = {}
        if not hasattr(self, "subnet_id"):
            self.subnet_id = self.subnet_name
        if not hasattr(self, "domain_id"):
            self.domain_id = None
        for index, node in enumerate(self.nodes):
            if hasattr(node, "ensure_runtime_defaults"):
                node.ensure_runtime_defaults()
            node.route_depth = self.node_depths.get(index, getattr(node, "route_depth", 1))
            node.subnet_id = self.subnet_id
            node.domain_id = f"{self.subnet_name}:{node.ip_address}" if self.domain_id is None else f"{self.subnet_id}:{node.ip_address}"

    def get_outbound_hops(self, node_index):
        return sorted(self.forward_links.get(node_index, set()))

    def get_inbound_hops(self, node_index):
        return sorted(self.backward_links.get(node_index, set()))


class SubnetRegion:
    def __init__(self, subnet_id, subnet_name, domain_id, world_map, depth=1):
        self.subnet_id = subnet_id
        self.subnet_name = subnet_name
        self.domain_id = domain_id
        self.world_map = world_map
        self.depth = depth
        self.neighbors = set()
        self.cleared_nodes = set()
        self.current_anchor = min(world_map.entry_links) if world_map.entry_links else 0
        self.sweep_level = 0
        self.sweep_max = max(4, len(world_map.nodes) + 1)
        self.supercruise_heat = 0

    def ensure_runtime_defaults(self):
        if hasattr(self.world_map, "ensure_runtime_defaults"):
            self.world_map.ensure_runtime_defaults()
        if not hasattr(self, "neighbors"):
            self.neighbors = set()
        else:
            self.neighbors = set(self.neighbors)
        if not hasattr(self, "cleared_nodes"):
            self.cleared_nodes = set()
        else:
            self.cleared_nodes = set(self.cleared_nodes)
        if not hasattr(self, "current_anchor"):
            self.current_anchor = min(self.world_map.entry_links) if self.world_map.entry_links else 0
        if not hasattr(self, "sweep_level"):
            self.sweep_level = 0
        if not hasattr(self, "sweep_max"):
            self.sweep_max = max(4, len(self.world_map.nodes) + 1)
        if not hasattr(self, "supercruise_heat"):
            self.supercruise_heat = 0

    def hostile_node_indices(self):
        return {
            index
            for index, node in enumerate(self.world_map.nodes)
            if node.node_type != "shop"
        }

    def is_conquered(self):
        return self.hostile_node_indices().issubset(self.cleared_nodes)

    def get_gatekeeper_index(self):
        for index, node in enumerate(self.world_map.nodes):
            if node.node_type == "gatekeeper":
                return index
        return None


class DomainRegion:
    def __init__(self, domain_id, name, depth=1):
        self.domain_id = domain_id
        self.name = name
        self.depth = depth
        self.subnet_ids = []
        self.neighbor_domains = set()

    def ensure_runtime_defaults(self):
        if not hasattr(self, "subnet_ids"):
            self.subnet_ids = []
        if not hasattr(self, "neighbor_domains"):
            self.neighbor_domains = set()
        else:
            self.neighbor_domains = set(self.neighbor_domains)


class DomainNetwork:
    def __init__(self, name, day):
        self.name = name
        self.day = day
        self.domains = {}
        self.subnets = {}
        self.entry_subnet_id = None

    def add_domain(self, domain):
        self.domains[domain.domain_id] = domain

    def add_subnet(self, subnet):
        self.subnets[subnet.subnet_id] = subnet
        self.domains[subnet.domain_id].subnet_ids.append(subnet.subnet_id)
        if self.entry_subnet_id is None:
            self.entry_subnet_id = subnet.subnet_id

    def link_subnets(self, left_id, right_id):
        self.subnets[left_id].neighbors.add(right_id)
        self.subnets[right_id].neighbors.add(left_id)

        left_domain = self.subnets[left_id].domain_id
        right_domain = self.subnets[right_id].domain_id
        if left_domain != right_domain:
            self.domains[left_domain].neighbor_domains.add(right_domain)
            self.domains[right_domain].neighbor_domains.add(left_domain)

    def get_subnet(self, subnet_id):
        return self.subnets.get(subnet_id)

    def get_domain(self, domain_id):
        return self.domains.get(domain_id)

    def neighboring_subnet_ids(self, subnet_id):
        subnet = self.get_subnet(subnet_id)
        if not subnet:
            return []
        return sorted(subnet.neighbors)

    def is_subnet_conquered(self, subnet_id):
        subnet = self.get_subnet(subnet_id)
        return bool(subnet and subnet.is_conquered())

    def all_subnets_conquered(self):
        return all(subnet.is_conquered() for subnet in self.subnets.values())

    def shortest_path(self, start_subnet_id, target_subnet_id):
        if start_subnet_id == target_subnet_id:
            return [start_subnet_id]
        queue = deque([(start_subnet_id, [start_subnet_id])])
        visited = {start_subnet_id}
        while queue:
            current, path = queue.popleft()
            for neighbor_id in self.neighboring_subnet_ids(current):
                if neighbor_id in visited:
                    continue
                next_path = path + [neighbor_id]
                if neighbor_id == target_subnet_id:
                    return next_path
                visited.add(neighbor_id)
                queue.append((neighbor_id, next_path))
        return []

    def resolve_subnet_target(self, token, current_subnet_id=None):
        raw = (token or "").strip().lower()
        if not raw:
            return None
        if raw in {"current", "active", "here"}:
            return current_subnet_id

        for subnet_id, subnet in self.subnets.items():
            if raw in {
                subnet_id.lower(),
                subnet.subnet_name.lower(),
                subnet.subnet_name.lower().replace(" ", "_"),
            }:
                return subnet_id

        for domain_id, domain in self.domains.items():
            if raw not in {
                domain_id.lower(),
                domain.name.lower(),
                domain.name.lower().replace(" ", "_"),
            }:
                continue
            preferred = [
                subnet_id
                for subnet_id in domain.subnet_ids
                if not self.is_subnet_conquered(subnet_id)
            ]
            if preferred:
                return preferred[0]
            return domain.subnet_ids[0] if domain.subnet_ids else None

        return None

    def ensure_runtime_defaults(self):
        if not hasattr(self, "day"):
            self.day = 1
        if not hasattr(self, "domains"):
            self.domains = {}
        if not hasattr(self, "subnets"):
            self.subnets = {}
        if not hasattr(self, "entry_subnet_id"):
            self.entry_subnet_id = None
        for domain in self.domains.values():
            if hasattr(domain, "ensure_runtime_defaults"):
                domain.ensure_runtime_defaults()
        for subnet in self.subnets.values():
            if hasattr(subnet, "ensure_runtime_defaults"):
                subnet.ensure_runtime_defaults()
        if self.entry_subnet_id is None and self.subnets:
            self.entry_subnet_id = next(iter(self.subnets.keys()))

    def iter_macro_neighbors(self, subnet_id, node_index):
        subnet = self.get_subnet(subnet_id)
        if not subnet:
            return []

        refs = {(subnet_id, neighbor_index) for neighbor_index in subnet.world_map.links.get(node_index, set())}
        local_gate = subnet.get_gatekeeper_index()
        is_bridge_node = node_index == local_gate or node_index in subnet.world_map.entry_links

        if is_bridge_node:
            for neighbor_subnet_id in subnet.neighbors:
                neighbor_subnet = self.get_subnet(neighbor_subnet_id)
                if not neighbor_subnet:
                    continue
                neighbor_gate = neighbor_subnet.get_gatekeeper_index()
                if neighbor_gate is not None:
                    refs.add((neighbor_subnet_id, neighbor_gate))
                for entry_index in neighbor_subnet.world_map.entry_links:
                    refs.add((neighbor_subnet_id, entry_index))

        return sorted(refs)


class WorldGenerator:
    DOMAIN_NAMES = (
        "Backbone Delta",
        "Metro Spine",
        "Transit Ridge",
        "Archive Shelf",
        "Carrier Fold",
        "Signal Basin",
    )

    @staticmethod
    def generate_ip(rng: random.Random):
        return f"{rng.randint(11, 255)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 255)}"

    @staticmethod
    def create_map(ledger, day, *, subnet_name=None, difficulty_bias=0, announce=True, rng=None, pressure=1):
        """Procedurally generates a single subnet map."""
        rng = rng or random.Random()
        if announce:
            print(f"\033[96m[sys] Synthesizing Subnet Map for Day {day}...\033[0m")

        base_diff = max(1, pressure + difficulty_bias)
        world = InternetMap(subnet_name or f"Subnet_{rng.randint(1000, 9999)}")

        if pressure <= 2:
            num_nodes = rng.randint(4, 5)
            node_pool = ["personal", "minecraft", "civilian"]
            include_shop = True
        elif pressure <= 4:
            num_nodes = rng.randint(5, 6)
            node_pool = ["personal", "minecraft", "iot", "server", "civilian", "lab", "relay"]
            include_shop = rng.random() < 0.6
        else:
            num_nodes = rng.randint(6, 8)
            node_pool = ["personal", "minecraft", "iot", "server", "corporate", "honeypot", "lab", "relay", "media"]
            include_shop = rng.random() < 0.45
        hostile_nodes = (num_nodes - 1) - (1 if include_shop else 0)

        for _ in range(hostile_nodes):
            node_type = rng.choice(node_pool)
            difficulty_adjustment = 0
            if node_type == "minecraft":
                difficulty_adjustment = -1
            elif node_type in {"server", "corporate", "honeypot", "relay", "lab"}:
                difficulty_adjustment = 1
            node = Node(
                WorldGenerator.generate_ip(rng),
                node_type,
                max(1, base_diff + difficulty_adjustment),
            )
            node.spawn_seed = rng.randint(1, 2_000_000_000)
            world.add_node(node)

        if include_shop:
            node = Node(WorldGenerator.generate_ip(rng), "shop", max(1, base_diff - 1))
            node.spawn_seed = rng.randint(1, 2_000_000_000)
            world.add_node(node)

        gatekeeper_diff = base_diff + max(2, pressure // 2)
        gatekeeper = Node(WorldGenerator.generate_ip(rng), "gatekeeper", gatekeeper_diff)
        gatekeeper.spawn_seed = rng.randint(1, 2_000_000_000)
        world.add_node(gatekeeper)

        gatekeeper_index = next((idx for idx, node in enumerate(world.nodes) if node.node_type == "gatekeeper"), -1)
        shop_index = next((idx for idx, node in enumerate(world.nodes) if node.node_type == "shop"), None)
        branch_indices = [
            idx
            for idx, node in enumerate(world.nodes)
            if node.node_type not in {"shop", "gatekeeper"}
        ]
        rng.shuffle(branch_indices)

        if branch_indices:
            entry_count = 1
            entry_indices = branch_indices[:entry_count]
            remaining_indices = branch_indices[entry_count:]
        else:
            entry_indices = []
            remaining_indices = []

        if not entry_indices and branch_indices:
            entry_indices = [branch_indices[0]]
            remaining_indices = branch_indices[1:]

        frontier = []
        for node_index in entry_indices:
            world.set_entry_link(node_index)
            world.node_depths[node_index] = 1
            world.nodes[node_index].route_depth = 1
            frontier.append(node_index)

        if len(entry_indices) > 1:
            backbone_root = entry_indices[0]
            for extra_entry in entry_indices[1:]:
                world.link_nodes(backbone_root, extra_entry, bidirectional=True)

        for node_index in remaining_indices:
            parent_index = rng.choice(frontier) if frontier else gatekeeper_index
            if parent_index is not None and parent_index >= 0:
                world.link_nodes(parent_index, node_index)
                world.node_depths[node_index] = world.node_depths.get(parent_index, 1) + 1
            else:
                world.node_depths[node_index] = 1
            world.nodes[node_index].route_depth = world.node_depths[node_index]
            frontier.append(node_index)

            if len(frontier) > 2 and rng.random() < 0.35:
                possible_extra = [
                    candidate
                    for candidate in frontier
                    if candidate != node_index and world.node_depths.get(candidate, 1) < world.node_depths[node_index]
                ]
                if possible_extra:
                    world.link_nodes(rng.choice(possible_extra), node_index)

        if shop_index is not None:
            if frontier and rng.random() < 0.8:
                parent_index = rng.choice(frontier)
                world.link_nodes(parent_index, shop_index)
                world.node_depths[shop_index] = world.node_depths.get(parent_index, 1) + 1
            else:
                world.set_entry_link(shop_index)
                world.node_depths[shop_index] = 1
            world.nodes[shop_index].route_depth = world.node_depths[shop_index]
            if not world.links.get(shop_index) and entry_indices:
                world.link_nodes(entry_indices[0], shop_index, bidirectional=True)

        if gatekeeper_index >= 0:
            gate_depth = max(world.node_depths.values(), default=1) + 1
            world.node_depths[gatekeeper_index] = gate_depth
            world.nodes[gatekeeper_index].route_depth = gate_depth

            if frontier:
                link_count = min(len(frontier), rng.randint(1, 2))
                for parent_index in rng.sample(frontier, link_count):
                    world.link_nodes(parent_index, gatekeeper_index)
            if shop_index is not None and rng.random() < 0.25:
                world.link_nodes(shop_index, gatekeeper_index)

        for index, node in enumerate(world.nodes):
            node.route_depth = world.node_depths.get(index, 1)
            node.domain_id = f"{world.subnet_name}:{node.ip_address}"
            node.subnet_id = world.subnet_id

        return world

    @staticmethod
    def create_network(state):
        pressure = state.get_difficulty_pressure() if hasattr(state, "get_difficulty_pressure") else 1
        rng = random.Random(state.make_seed("network", state.day, pressure, state.trace_level))
        network = DomainNetwork(f"RouteMesh_{rng.randint(1000, 9999)}", state.day)

        if pressure <= 2:
            domain_count = 1
        elif pressure <= 5:
            domain_count = 2
        else:
            domain_count = 3

        previous_domain_border = None
        subnet_counter = 0

        for domain_index in range(domain_count):
            domain_name = WorldGenerator.DOMAIN_NAMES[domain_index % len(WorldGenerator.DOMAIN_NAMES)]
            domain_id = f"D{domain_index + 1}"
            domain = DomainRegion(domain_id, domain_name, depth=domain_index + 1)
            network.add_domain(domain)

            if pressure <= 2 and domain_index == 0:
                subnet_count = 2
            else:
                subnet_count = 2 if rng.random() < 0.52 else 3

            local_subnet_ids = []
            for local_index in range(subnet_count):
                subnet_counter += 1
                subnet_id = f"S{subnet_counter}"
                subnet_name = f"{domain_id}-Subnet_{rng.randint(1000, 9999)}"
                subnet_rng = random.Random(state.make_seed("subnet", state.day, subnet_id, pressure, domain_index, local_index))
                subnet_map = WorldGenerator.create_map(
                    state.threat_ledger,
                    state.day,
                    subnet_name=subnet_name,
                    difficulty_bias=domain_index + local_index,
                    announce=False,
                    rng=subnet_rng,
                    pressure=pressure + local_index,
                )
                subnet_map.subnet_id = subnet_id
                subnet_map.domain_id = domain_id
                for node in subnet_map.nodes:
                    if hasattr(node, "ensure_runtime_defaults"):
                        node.ensure_runtime_defaults()
                    node.subnet_id = subnet_id
                    node.domain_id = f"{subnet_id}:{node.ip_address}"
                subnet = SubnetRegion(
                    subnet_id,
                    subnet_name,
                    domain_id,
                    subnet_map,
                    depth=(domain_index * 3) + local_index + 1,
                )
                network.add_subnet(subnet)
                local_subnet_ids.append(subnet_id)

                if len(local_subnet_ids) > 1:
                    network.link_subnets(local_subnet_ids[-2], subnet_id)

                if len(local_subnet_ids) > 2 and rng.random() < 0.35:
                    network.link_subnets(local_subnet_ids[0], subnet_id)

            if previous_domain_border and local_subnet_ids:
                network.link_subnets(previous_domain_border, local_subnet_ids[0])

            if local_subnet_ids:
                previous_domain_border = local_subnet_ids[-1]

        return network
