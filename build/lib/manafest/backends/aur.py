# manafest/backends/aur.py

import subprocess
import logging
import shutil

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def _helper() -> str|None:
    """
    Return the AUR helper binary available on PATH.
    """
    for h in ("yay","paru","pikaur"):
        if shutil.which(h):
            return h
    return None

def search(query: str) -> list[dict]:
    # your existing code…

def install(name: str) -> bool:
    helper = _helper()
    if not helper:
        return False
    try:
        subprocess.check_call([helper, "-S", "--noconfirm", name])
        return True
    except Exception as e:
        logger.debug("AUR install failed %s → %s", helper, e)
        return False

def remove(name: str) -> bool:
    helper = _helper()
    if not helper:
        return False
    try:
        subprocess.check_call([helper, "-Rns", "--noconfirm", name])
        return True
    except Exception as e:
        logger.debug("AUR remove failed %s → %s", helper, e)
        return False

def info(name: str) -> dict:
    # your existing code…

def update() -> bool:
    """
    Refresh AUR database.
    """
    helper = _helper()
    if not helper:
        return False
    try:
        subprocess.check_call([helper, "-Sy"])
        return True
    except Exception:
        return False

def upgrade() -> bool:
    """
    Upgrade all AUR & system packages via helper.
    """
    helper = _helper()
    if not helper:
        return False
    try:
        subprocess.check_call([helper, "-Syu", "--noconfirm"])
        return True
    except Exception:
        return False

