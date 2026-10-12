import os
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def resolve_safe_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)

def read_file_tool(path: str) -> Dict[str, Any]:
    full_path = resolve_safe_path(path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File '{path}' does not exist."}
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {
            "success": True,
            "path": path,
            "size_bytes": len(content),
            "content": content
        }
    except Exception as e:
        return {"success": False, "error": f"Error reading file '{path}': {str(e)}"}

def list_files_tool(directory: str = "data/invoices") -> Dict[str, Any]:
    full_path = resolve_safe_path(directory)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"Directory '{directory}' does not exist."}
    try:
        entries = []
        for name in os.listdir(full_path):
            p = os.path.join(full_path, name)
            entries.append({
                "name": name,
                "is_dir": os.path.isdir(p),
                "size_bytes": os.path.getsize(p) if os.path.isfile(p) else 0
            })
        return {"success": True, "directory": directory, "files": entries}
    except Exception as e:
        return {"success": False, "error": f"Error listing directory '{directory}': {str(e)}"}
