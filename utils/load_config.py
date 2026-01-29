import yaml
from pathlib import Path

def load_config(config_file: str = "config.yaml") -> dict:
    """
    Load the YAML configuration file.

    Args:
        config_file (str): Path to the YAML config file (relative to project root).

    Returns:
        dict: Dictionary containing the configuration.
    """
    # Resolve the path relative to the project root
    project_root = Path(__file__).parent.parent  # utils/ -> project root
    config_path = project_root / config_file

    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config

# Among Optional[str] and str | None, the latter is preferred in modern Python typing.
# prefer dict over Dict from typing for simplicity.