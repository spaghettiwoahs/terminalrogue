import random


class Node:
    def __init__(self, ip_address, node_type, difficulty):
        self.ip_address = ip_address
        self.node_type = node_type
        self.difficulty = difficulty
        self.is_hostile = node_type not in ["shop"]
        self.cached_enemy = None
        self.recon_log = []


class InternetMap:
    def __init__(self, subnet_name):
        self.subnet_name = subnet_name
        self.nodes = []
        self.links = {}
        self.entry_links = set()
        self.node_depths = {}

    def add_node(self, node):
        self.nodes.append(node)
        index = len(self.nodes) - 1
        self.links[index] = set()
        return index

    def link_nodes(self, left_index, right_index):
        self.links.setdefault(left_index, set()).add(right_index)
        self.links.setdefault(right_index, set()).add(left_index)

    def set_entry_link(self, node_index):
        self.entry_links.add(node_index)

    def can_route_to(self, node_index, cleared_nodes):
        if node_index in self.entry_links:
            return True
        return any(linked_index in cleared_nodes for linked_index in self.links.get(node_index, set()))

    def get_unlock_sources(self, node_index):
        return sorted(self.links.get(node_index, set()))


class WorldGenerator:
    @staticmethod
    def generate_ip():
        return f"{random.randint(11, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 255)}"

    @staticmethod
    def create_map(ledger, day):
        """Procedurally generates a subnet map based on Threat Ledger data."""
        print(f"\033[96m[sys] Synthesizing Subnet Map for Day {day}...\033[0m")

        # Difficulty scales with run depth and global noise
        if day == 1:
            base_diff = 1
        else:
            base_diff = day + (ledger.brute_force_noise + ledger.exploit_noise) // 100

        world = InternetMap(f"Subnet_{random.randint(1000, 9999)}")

        # Generate 4-6 nodes per map with a mix of soft civilian targets and riskier infrastructure.
        num_nodes = random.randint(4, 5) if day == 1 else random.randint(4, 6)
        if day == 1:
            low_day_pool = ["personal", "minecraft"]
        else:
            low_day_pool = ["personal", "minecraft", "iot", "server"]
        high_day_pool = ["personal", "minecraft", "iot", "server", "corporate", "honeypot"]
        node_pool = low_day_pool if day <= 2 else high_day_pool
        if day == 1:
            include_shop = True
        elif day <= 2:
            include_shop = random.random() < 0.55
        else:
            include_shop = random.random() < 0.4
        hostile_nodes = (num_nodes - 1) - (1 if include_shop else 0)

        for _ in range(hostile_nodes):
            node_type = random.choice(node_pool)
            difficulty_adjustment = 0
            if node_type == "minecraft":
                difficulty_adjustment = -1
            elif node_type in {"server", "corporate", "honeypot"}:
                difficulty_adjustment = 1
            world.add_node(
                Node(
                    WorldGenerator.generate_ip(),
                    node_type,
                    max(1, base_diff + difficulty_adjustment),
                )
            )

        if include_shop:
            world.add_node(Node(WorldGenerator.generate_ip(), "shop", max(1, base_diff - 1)))

        # The final node of every subnet is an ISP Gatekeeper
        gatekeeper_diff = base_diff + 1 if day == 1 else base_diff + 5
        world.add_node(Node(WorldGenerator.generate_ip(), "gatekeeper", gatekeeper_diff))

        gatekeeper_index = next((idx for idx, node in enumerate(world.nodes) if node.node_type == "gatekeeper"), -1)
        shop_index = next((idx for idx, node in enumerate(world.nodes) if node.node_type == "shop"), None)
        branch_indices = [
            idx
            for idx, node in enumerate(world.nodes)
            if node.node_type not in {"shop", "gatekeeper"}
        ]
        random.shuffle(branch_indices)

        if branch_indices:
            entry_count = min(len(branch_indices), random.randint(1, 2))
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
            frontier.append(node_index)

        for node_index in remaining_indices:
            parent_index = random.choice(frontier) if frontier else gatekeeper_index
            if parent_index is not None and parent_index >= 0:
                world.link_nodes(parent_index, node_index)
                world.node_depths[node_index] = world.node_depths.get(parent_index, 1) + 1
            else:
                world.node_depths[node_index] = 1
            frontier.append(node_index)

            if len(frontier) > 2 and random.random() < 0.35:
                possible_extra = [
                    candidate
                    for candidate in frontier
                    if candidate != node_index and abs(world.node_depths.get(candidate, 1) - world.node_depths[node_index]) <= 1
                ]
                if possible_extra:
                    world.link_nodes(node_index, random.choice(possible_extra))

        if shop_index is not None:
            if frontier and random.random() < 0.8:
                parent_index = random.choice(frontier)
                world.link_nodes(parent_index, shop_index)
                world.node_depths[shop_index] = world.node_depths.get(parent_index, 1) + 1
            else:
                world.set_entry_link(shop_index)
                world.node_depths[shop_index] = 1

        if gatekeeper_index >= 0:
            world.set_entry_link(gatekeeper_index)
            gate_depth = max(world.node_depths.values(), default=1) + 1
            world.node_depths[gatekeeper_index] = gate_depth

            if frontier:
                link_count = min(len(frontier), random.randint(1, 2))
                for parent_index in random.sample(frontier, link_count):
                    world.link_nodes(parent_index, gatekeeper_index)
            if shop_index is not None and random.random() < 0.25:
                world.link_nodes(shop_index, gatekeeper_index)

        return world
