import yaml

from runtime_paths import get_resource_root, resolve_resource_path


class DataLoader:
    BASE_DIR = get_resource_root()

    @staticmethod
    def load_yaml(filepath: str) -> dict:
        """Helper to load a YAML file safely."""
        resolved_path = resolve_resource_path(filepath)

        if not resolved_path.exists():
            print(f"\033[91m[sys] Warning: {resolved_path} not found. Returning empty dictionary.\033[0m")
            return {}

        with resolved_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    @staticmethod
    def load_all() -> dict:
        """Loads all configuration data from YAML files."""
        print("\033[96m[sys] Loading external configuration data via PyYAML...\033[0m")
        return {
            "enemies": DataLoader.load_yaml("enemies.yaml"),
            "arsenal": DataLoader.load_yaml("arsenal.yaml"),
            "events": DataLoader.load_yaml("events.yaml")
        }
