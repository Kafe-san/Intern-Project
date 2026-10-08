import json
from pathlib import Path


def load_config(config_path=None):

    if config_path is None:
        project_root = Path(__file__).resolve().parent.parent
        config_path = project_root / "config" / "config.json"

    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    validate_config(config)

    return config

    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    validate_config(config)

    return config


def validate_config(config):

    required_sections = [
        "benchmark",
        "model",
        "docker",
        "inference",
        "monitoring",
        "database"
    ]

    for section in required_sections:

        if section not in config:
            raise ValueError(
                f"Missing configuration section: {section}"
            )


    if not config["model"].get("name"):
        raise ValueError(
            "Model name cannot be empty."
        )


    if not config["inference"].get("prompt"):
        raise ValueError(
            "Inference prompt cannot be empty."
        )


    samples = config["monitoring"].get("samples")

    if not isinstance(samples, int) or samples <= 0:
        raise ValueError(
            "monitoring.samples must be a positive integer."
        )


    interval = config["monitoring"].get(
        "interval_seconds"
    )

    if not isinstance(interval, (int, float)) or interval <= 0:
        raise ValueError(
            "monitoring.interval_seconds must be positive."
        )


    if not config["database"].get("path"):
        raise ValueError(
            "Database path cannot be empty."
        )


if __name__ == "__main__":

    config = load_config()

    print("Configuration loaded successfully.")
    print()
    print(json.dumps(
        config,
        indent=4
    ))