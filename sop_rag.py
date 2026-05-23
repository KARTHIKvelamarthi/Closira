"""
sop_rag.py — Dynamically loads and chunks any arbitrary JSON SOP data.
"""

import os
import json

SOP_PATH = os.path.join(os.path.dirname(__file__), "sop.json")

def load_sop():
    with open(SOP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_sop_chunks():
    """
    Dynamically converts any nested JSON structure into document chunks.
    If a top-level key maps to a list of dicts, it chunks each element individually.
    Otherwise, it chunks by top-level keys.
    
    Returns:
        list[dict]: Document chunks of structure {"id": str, "text": str, "category": str}
    """
    sop = load_sop()
    chunks = []

    def render_to_text(obj, indent=0):
        lines = []
        pad = "  " * indent
        if isinstance(obj, dict):
            for k, v in obj.items():
                lines.append(f"{pad}{k.replace('_', ' ').upper()}:")
                lines.extend(render_to_text(v, indent + 1))
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    lines.extend(render_to_text(item, indent))
                else:
                    lines.append(f"{pad}- {item}")
        else:
            lines.append(f"{pad}{obj}")
        return lines

    for key, val in sop.items():
        # If it is a list of dictionaries (like plans or services), chunk them individually for higher resolution
        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
            for idx, item in enumerate(val):
                name_val = item.get("name") or item.get("title") or item.get("id") or str(idx)
                chunk_id = f"{key}_{str(name_val).lower().replace(' ', '_')}"
                
                item_text = "\n".join(render_to_text(item))
                text_content = f"{key.replace('_', ' ').upper()}:\n{item_text}"
                
                chunks.append({
                    "id": chunk_id,
                    "text": text_content,
                    "category": key
                })
        else:
            # Otherwise, group the entire top-level section as a single chunk
            chunk_id = key
            rendered_lines = render_to_text(val)
            text_content = f"{key.replace('_', ' ').upper()}:\n" + "\n".join(rendered_lines)
            
            chunks.append({
                "id": chunk_id,
                "text": text_content,
                "category": key
            })

    return chunks
