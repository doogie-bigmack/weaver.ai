"""Configuration-based model setup."""

import os

import yaml

from .mock import MockAdapter
from .openai_adapter import OpenAIAdapter
from .router import ModelRouter


def setup_router_from_config(config_path: str = "models.yaml") -> ModelRouter:
    """Set up model router from configuration file.

    Example config:
    ```yaml
    models:
      - name: mock
        type: mock

      - name: gpt3
        type: openai
        model: gpt-3.5-turbo

      - name: gpt4
        type: openai
        model: gpt-4

    default: mock
    ```
    """
    router = ModelRouter()

    # If no config file, just use mock
    if not os.path.exists(config_path):
        return router

    with open(config_path) as f:
        config = yaml.safe_load(f)

    for model_config in config.get("models", []):
        name = model_config["name"]
        model_type = model_config["type"]

        if model_type == "mock":
            adapter = MockAdapter(name)
        elif model_type == "openai":
            model = model_config.get("model", "gpt-3.5-turbo")
            adapter = OpenAIAdapter(model)
        else:
            continue  # Skip unknown types

        router.register(name, adapter)

    # Set default model
    if "default" in config:
        router.default_model = config["default"]

    return router
