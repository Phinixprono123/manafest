# manafest/backends/flatpak.py

import subprocess
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def search(query: str) -> list[dict]:
    """
    Call `flatpak search` and return a list of dicts:
    {name, version, arch, summary}.
    """
    try:
        out = subprocess.check_output(
            ["flatpak", "search", query],
            stderr=subprocess.DEVNULL,
            timeout=20
        ).decode().splitlines()
    except Exception:
        return []

    results = []
    for line in out:
        # skip header or empty lines
        if not line.strip() or line.startswith("Name"):
            continue
        # split on two-or-more spaces
        parts = [p for p in line.split("  ") if p.strip()]
        name = parts[0].strip()
        # often Application ID is parts[1], summary at end
        summary = parts[-1].strip() if len(parts) > 1 else ""
        results.append({
            "name": name,
            "version": "",
            "arch": "",
            "summary": summary
        })
    return results

def install(name: str) -> bool:
    """
    flatpak install flathub <app-id> -y
    """
    cmd = ["flatpak", "install", "flathub", "-y", name]
    try:
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        logger.debug("Flatpak install failed %s → %s", cmd, e)
        return False

def remove(name: str) -> bool:
    """
    flatpak uninstall <app-id> -y
    """
    cmd = ["flatpak", "uninstall", "-y", name]
    try:
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        logger.debug("Flatpak uninstall failed %s → %s", cmd, e)
        return False

def info(name: str) -> dict:
    """
    flatpak info <app-id>, parsed for name, version, arch.
    """
    try:
        out = subprocess.check_output(
            ["flatpak", "info", name],
            stderr=subprocess.DEVNULL,
            timeout=20
        ).decode().splitlines()
    except Exception:
        return {}
    data = {}
    for l in out:
        if l.startswith("Name"):
            data["name"] = l.split(":",1)[1].strip()
        elif l.startswith("Branch"):
            data["version"] = l.split(":",1)[1].strip()
        elif l.startswith("Arch"):
            data["arch"] = l.split(":",1)[1].strip()
    # flatpak info has no summary field
    data.setdefault("summary", "")
    return data

def update() -> bool:
    """
    Runs `flatpak update -y` to update all installed apps.
    """
    try:
        subprocess.check_call(["flatpak", "update", "-y"])
        return True
    except Exception:
        return False

def upgrade() -> bool:
    """
    Alias for `update` in Flatpak context.
    """
    return update()

