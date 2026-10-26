#!/usr/bin/env python3
import os
import sys
import json
import ast
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

OFFENSIVE_ROOT = os.getenv("OFFENSIVE_ROOT", "/opt/offensive")
REGISTRY_PATH = os.path.join(OFFENSIVE_ROOT, "master_registry.json")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("OMNI_AI_MODEL", "qwen2.5")

IGNORE_DIRS = {".git", "venv", "backups", "__pycache__", "node_modules", ".pytest_cache"}
IGNORE_EXTS = {".pyc", ".bak", ".log"}

def scan_file(filepath, ext):
    meta = {"type": ext.lstrip("."), "size_bytes": os.path.getsize(filepath)}
    try:
        if ext == ".py":
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content)
            meta["docstring"] = ast.get_docstring(tree) or ""
            meta["functions"] = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        elif ext in [".sh", ".env", ".envrc"] or filepath.endswith(".zshrc"):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            meta["line_count"] = len(lines)
            meta["exports"] = [line.strip() for line in lines if "export " in line or "=" in line]
    except Exception as e:
        meta["error"] = str(e)
    return meta

def build_master_registry():
    """Compiles a comprehensive awareness manifest including tree, zshrc, global envs, and venv."""
    print("[*] Building master system registry...")
    registry = {
        "last_updated": datetime.now().isoformat(),
        "hostname": os.uname().nodename,
        "user": os.getenv("USER", "unknown"),
        "components": {}
    }

    # 1. Scan Full /opt/offensive Tree
    tree_data = {}
    for root, dirs, files in os.walk(OFFENSIVE_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        rel_root = os.path.relpath(root, OFFENSIVE_ROOT)
        current = tree_data
        if rel_root != ".":
            for part in rel_root.split(os.sep):
                current = current.setdefault(part, {})
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in IGNORE_EXTS:
                continue
            filepath = os.path.join(root, file)
            current[file] = scan_file(filepath, ext)
    registry["components"]["offensive_tree"] = tree_data

    # 2. Scan External Shell Config (~/.zshrc)
    zshrc_path = os.path.expanduser("~/.zshrc")
    if os.path.exists(zshrc_path):
        registry["components"]["zshrc"] = scan_file(zshrc_path, ".zshrc")

    # 3. Scan Global Env File (/opt/offensive.env)
    global_env = "/opt/offensive.env"
    if os.path.exists(global_env):
        registry["components"]["global_env"] = scan_file(global_env, ".env")

    # 4. Inspect Virtual Environment (/opt/offensive/venv)
    venv_path = os.path.join(OFFENSIVE_ROOT, "venv")
    if os.path.exists(venv_path):
        pip_path = os.path.join(venv_path, "bin", "pip")
        installed_packages = []
        if os.path.exists(pip_path):
            try:
                res = subprocess.run([pip_path, "list", "--format=json"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    installed_packages = json.loads(res.stdout)
            except Exception:
                pass
        registry["components"]["venv"] = {
            "path": venv_path,
            "python_version": sys.version,
            "installed_packages": installed_packages
        }

    os.makedirs(os.path.dirname(os.path.abspath(REGISTRY_PATH)), exist_ok=True)
    # OFFENSIVE_REGISTRY_BACKUP_GUARD_V1
    import os as _aw_os, shutil as _aw_shutil
    from datetime import datetime as _aw_datetime
    _aw_registry = _aw_os.path.abspath(_aw_os.fspath(REGISTRY_PATH))
    _aw_os.makedirs(_aw_os.path.dirname(_aw_registry), exist_ok=True)
    if _aw_os.path.isfile(_aw_registry):
        _aw_backup_dir = _aw_os.path.join(_aw_os.path.dirname(_aw_os.path.abspath(__file__)), 'backups', 'master-registry')
        _aw_os.makedirs(_aw_backup_dir, exist_ok=True)
        _aw_prefix = _aw_os.path.basename(_aw_registry) + '.bak.'
        _aw_name = _aw_prefix + _aw_datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        _aw_shutil.copy2(_aw_registry, _aw_os.path.join(_aw_backup_dir, _aw_name))
        _aw_old = sorted((n for n in _aw_os.listdir(_aw_backup_dir) if n.startswith(_aw_prefix)), reverse=True)
        for _aw_stale in _aw_old[20:]:
            _aw_os.unlink(_aw_os.path.join(_aw_backup_dir, _aw_stale))
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        
    print(f"[+] Master registry successfully updated at {REGISTRY_PATH}")

def query_ollama(prompt):
    if not os.path.exists(REGISTRY_PATH):
        build_master_registry()
        
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    url = f"{OLLAMA_HOST}/api/generate"
    system_prompt = (
        "You are the master controller intelligence of the /opt/offensive ecosystem. "
        "You have complete architectural awareness of the local directory tree, ~/.zshrc shell configurations, "
        "/opt/offensive.env global variables, and the /opt/offensive/venv virtual environment state. "
        "Analyze requests with deep awareness of how these components interconnect."
    )

    payload = {
        "model": MODEL_NAME,
        "prompt": f"{system_prompt}\n\nMaster Registry State:\n{json.dumps(registry_data, indent=2)}\n\nCommand/Task:\n{prompt}",
        "stream": False,
        "options": {"temperature": 0.2}
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("response", "No response generated.")
    except urllib.error.URLError as e:
        return f"[!] Ollama connection error at {OLLAMA_HOST}: {e.reason}"

def main():
    if len(sys.argv) < 2:
        print("Usage: offensivectl.py [scan|audit|prune|status|recursive] [custom AI prompt]")
        sys.exit(1)

    command = sys.argv[1].lower()
    
    if command == "scan":
        build_master_registry()
    elif command == "status":
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH, "r") as f:
                reg = json.load(f)
            print(json.dumps(reg, indent=2))
        else:
            print("[-] Master registry not found. Run 'offensivectl.py scan' first.")
    elif command == "recursive":
        # # OFFENSIVE_RECURSIVE_INSPECTOR_DISPATCH
        _off_root = os.path.dirname(os.path.realpath(__file__))
        _off_inspector = os.path.join(_off_root, "core", "recursive_inspector.py")
        if not os.path.isfile(_off_inspector):
            print(f"[!] Recursive inspector missing: {_off_inspector}")
            sys.exit(2)
        _off_args = sys.argv[2:]
        if any(a == "--root" or a.startswith("--root=") for a in _off_args):
            print("[!] The recursive scan root is fixed to /opt/offensive.")
            sys.exit(2)
        if not any(a == "--output" or a.startswith("--output=") for a in _off_args):
            _off_stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            _off_output = os.path.join(_off_root, ".awareness", f"static-inventory-{_off_stamp}.json")
            _off_args.extend(["--output", _off_output])
        _off_result = subprocess.run([
            sys.executable, _off_inspector, "--root", _off_root, *_off_args
        ], check=False)
        sys.exit(_off_result.returncode)
    elif command in ["audit", "prune"]:
        prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Perform a thorough audit of all configurations across ~/.zshrc, /opt/offensive.env, the venv packages, and the codebase tree. Check for misalignments or dead variables."
        print(f"[*] Running Ollama AI {command} analysis...")
        result = query_ollama(prompt)
        print("\n==========================================")
        print(f" OffensiveCtl Master {command.upper()} Report")
        print("==========================================")
        print(result)
        print("==========================================")
    else:
        # Treat entire argument string as an AI query with full registry context
        prompt = " ".join(sys.argv[1:])
        print("[*] Querying master controller AI...")
        print(query_ollama(prompt))

if __name__ == "__main__":
    main()
