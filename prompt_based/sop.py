import os
import json

SOP_PATH = os.path.join(os.path.dirname(__file__), "sop.json")

with open(SOP_PATH, "r", encoding="utf-8") as f:
    SOP = json.load(f)


def get_sop_as_text() -> str:
    
    def render(obj, indent=0):
        lines = []
        pad = "  " * indent
        if isinstance(obj, dict):
            for k, v in obj.items():
                lines.append(f"{pad}{k.replace('_', ' ').upper()}:")
                lines.extend(render(v, indent + 1))
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    lines.extend(render(item, indent))
                else:
                    lines.append(f"{pad}- {item}")
        else:
            lines.append(f"{pad}{obj}")
        return lines
    return "\n".join(render(SOP))
