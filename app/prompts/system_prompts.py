import yaml
import os

def load_system_prompt():
    path = os.path.join(os.path.dirname(__file__), "system_prompts.yaml")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["system_prompt"]