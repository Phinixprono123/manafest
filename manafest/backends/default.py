# backends/default.py

import subprocess
import logging
from manafest.utils.osdetect import get_os, get_distro

# Create a logger just for this module and bump its level to INFO
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def search(query):
    cmd = _select_cmd("search", query)
    return _run_cmd(cmd)


def install(name):
    cmd = _select_cmd("install", name)
    return _run_cmd(cmd)


def remove(name):
    cmd = _select_cmd("remove", name)
    return bool(_run_cmd(cmd))


def _select_cmd(action, arg):
    os_name = get_os()
    if os_name == "linux":
        distro = get_distro()
        if distro == "arch":
            mapping = {
                "search": ["pacman", "-Ss", arg],
                "install": ["sudo", "pacman", "-S", "--noconfirm", arg],
                "remove": ["sudo", "pacman", "-Rsn", "--noconfirm", arg],
            }
        elif distro == "debian":
            mapping = {
                "search": ["apt-cache", "search", arg],
                "install": ["sudo", "apt-get", "install", "-y", arg],
                "remove": ["sudo", "apt-get", "remove", "-y", arg],
            }
        elif distro == "fedora":
            mapping = {
                "search": ["dnf", "search", arg],
                "install": ["sudo", "dnf", "install", "-y", arg],
                "remove": ["sudo", "dnf", "remove", "-y", arg],
            }
        else:
            mapping = {  # fallback to apt
                "search": ["apt-cache", "search", arg],
                "install": ["sudo", "apt-get", "install", "-y", arg],
                "remove": ["sudo", "apt-get", "remove", "-y", arg],
            }

    elif os_name == "macos":
        mapping = {
            "search": ["brew", "search", arg],
            "install": ["brew", "install", arg],
            "remove": ["brew", "uninstall", arg],
        }

    elif os_name == "windows":
        mapping = {
            "search": ["winget", "search", arg],
            "install": [
                "winget",
                "install",
                "--accept-source-agreements",
                "--accept-package-agreements",
                arg,
            ],
            "remove": ["winget", "uninstall", arg],
        }

    else:  # generic → pip
        mapping = {
            "search": ["pip", "search", arg],
            "install": ["pip", "install", arg],
            "remove": ["pip", "uninstall", "-y", arg],
        }

    return mapping[action]


def _run_cmd(cmd):
    """
    Run a subprocess command, return stdout lines or [] on failure.
    All failures are logged at DEBUG so they won't show up normally.
    """
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=20)
        return out.decode().splitlines()
    except subprocess.TimeoutExpired:
        logger.debug("Command timed out: %s", cmd)
        return []
    except FileNotFoundError:
        logger.debug("Tool not installed: %s", cmd[0])
        return []
    except subprocess.CalledProcessError as e:
        logger.debug(
            "Command '%s' failed with exit %d: %s",
            cmd[0],
            e.returncode,
            e.output.decode(errors="ignore"),
        )
        return []
