# manafest/backends/snap.py

import subprocess
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def search(query: str) -> list[dict]:
    """
    Snap search: parse lines of `snap find <query>`.
    """
    try:
        out = subprocess.check_output(
            ["snap", "find", query],
            stderr=subprocess.DEVNULL,
            timeout=20
        ).decode().splitlines()
    except Exception:
        return []

    results = []
    for line in out:
        # skip header and empty lines
        if not line.strip() or line.startswith("Name"):
            continue
        parts = [p for p in line.split() if p]
        # Format: Name     Version  Publisher   Notes  Summary
        name    = parts[0]
        version = parts[1] if len(parts) > 1 else ""
        summary = " ".join(parts[4:]) if len(parts) > 4 else ""
        results.append({
            "name": name,
            "version": version,
            "arch": "",       # snap is arch-agnostic
            "summary": summary
        })
    return results

def install(name: str) -> bool:
    cmd = ["sudo", "snap", "install", name]
    try:
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        logger.debug("Snap install failed %s → %s", cmd, e)
        return False

def remove(name: str) -> bool:
    cmd = ["sudo", "snap", "remove", name]
    try:
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        logger.debug("Snap remove failed %s → %s", cmd, e)
        return False

def info(name: str) -> dict:
    """
    snap info <name>
    """
    try:
        out = subprocess.check_output(
            ["snap", "info", name],
            stderr=subprocess.DEVNULL,
            timeout=20
        ).decode().splitlines()
    except Exception:
        return {}
    data = {}
    for l in out:
        if l.startswith("name:"):
            data["name"] = l.split(":",1)[1].strip()
        elif l.startswith("tracking:"):
            data["version"] = l.split(":",1)[1].strip()
        elif l.startswith("summary:"):
            data["summary"] = l.split(":",1)[1].strip()
    data.setdefault("arch", "")  # snaps run containerized
    return data

def update() -> bool:
    """
    `snap refresh` updates all snaps.
    """
    try:
        subprocess.check_call(["sudo", "snap", "refresh"])
        return True
    except Exception:
        return False

def upgrade() -> bool:
    """
    alias of update for snaps
    """
    return update()
