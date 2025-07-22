# manafest/backends/aur.py

import subprocess
import logging
import shutil

logger = logging.getLogger("manafest.backends.aur")
logger.setLevel(logging.INFO)

def _helper() -> str | None:
    """
    Return the first available AUR helper binary.
    """
    for helper in ("yay", "paru", "pikaur"):
        if shutil.which(helper):
            return helper
    return None

def search(query: str) -> list[dict]:
    helper = _helper()
    if not helper:
        return []
    try:
        out = subprocess.check_output(
            [helper, "-Ss", query],
            stderr=subprocess.DEVNULL,
            timeout=60
        ).decode().splitlines()
    except Exception:
        return []

    results = []
    for line in out:
        # Format: pkgname optional_colon description
        if not line.strip() or not line.startswith(query):
            continue
        name, _, rest = line.partition(":")
        summary = rest.strip()
        results.append({
            "name": name.strip(),
            "version": "",
            "arch": "",
            "summary": summary
        })
    return results

def install(name: str) -> bool:
    helper = _helper()
    if not helper:
        return False
    cmd = [helper, "-S", "--noconfirm", name]
    try:
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        logger.debug("AUR install failed %s → %s", cmd, e)
        return False

def remove(name: str) -> bool:
    helper = _helper()
    if not helper:
        return False
    cmd = [helper, "-Rns", "--noconfirm", name]
    try:
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        logger.debug("AUR remove failed %s → %s", cmd, e)
        return False

def info(name: str) -> dict:
    helper = _helper()
    if not helper:
        return {}
    try:
        out = subprocess.check_output(
            [helper, "-Si", name],
            stderr=subprocess.DEVNULL,
            timeout=60
        ).decode().splitlines()
    except Exception:
        return {}

    data = {}
    for line in out:
        if line.startswith("Name"):
            data["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Version"):
            data["version"] = line.split(":", 1)[1].strip()
        elif line.startswith("Architecture"):
            data["arch"] = line.split(":", 1)[1].strip()
        elif line.startswith("Description"):
            data["summary"] = line.split(":", 1)[1].strip()
            break

    return {
        "name": data.get("name", name),
        "version": data.get("version", "-"),
        "arch": data.get("arch", "-"),
        "summary": data.get("summary", "-")
    }

def update() -> bool:
    helper = _helper()
    if not helper:
        return False
    try:
        subprocess.check_call([helper, "-Sy"])
        return True
    except Exception:
        return False

def upgrade() -> bool:
    helper = _helper()
    if not helper:
        return False
    try:
        subprocess.check_call([helper, "-Syu", "--noconfirm"])
        return True
    except Exception:
        return False

