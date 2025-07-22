# manafest/backends/default.py

import subprocess
import logging
import re
import json

from manafest.utils.osdetect import get_os, get_distro

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

RE_FEDORA = re.compile(r'^([^|]+)\|([^|]+)\|([^|]+)\|(.+)$')


def installed(name: str) -> bool:
    """
    Return True if 'name' is installed system-wide (or via Termux).
    """
    os_name = get_os()
    distro = get_distro() if os_name == "linux" else None

    if os_name == "android":
        cmd = ["pkg", "list-installed"]
    elif distro == "arch":
        cmd = ["pacman", "-Qi", name]
    elif distro in ("debian", "ubuntu"):
        cmd = ["dpkg", "-s", name]
    elif distro == "fedora":
        cmd = ["rpm", "-q", name]
    elif os_name == "macos":
        cmd = ["brew", "list", name]
    elif os_name == "windows":
        cmd = ["winget", "list", name]
    else:
        cmd = ["pip", "show", name]

    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def info(name: str) -> dict:
    """
    Return metadata dict for name: {name,version,arch,summary}.
    Supports Fedora, Arch, Debian/Ubuntu, Termux (apt), macOS, Windows, pip.
    """
    os_name = get_os()
    distro = get_distro() if os_name == "linux" else None

    # --- Termux / Android via apt ---
    if os_name == "android":
        try:
            lines = subprocess.check_output(
                ["pkg", "list-installed"], stderr=subprocess.DEVNULL, timeout=20
            ).decode().splitlines()
            for l in lines:
                if l.startswith(name + "/"):
                    parts = l.split()
                    pkg_name = parts[0].split("/")[0]
                    version  = parts[1] if len(parts) > 1 else "-"
                    return {
                        "name": pkg_name,
                        "version": version,
                        "arch": "-",
                        "summary": "Termux package"
                    }
        except Exception:
            pass

    # --- Fedora via repoquery ---
    if distro == "fedora":
        cmd = [
            "dnf", "repoquery",
            "--qf", "%{name}|%{version}-%{release}|%{arch}|%{summary}",
            name
        ]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=20)
            m = RE_FEDORA.match(out.decode().strip())
            if m:
                nm,ver,arch,summ = m.groups()
                return {"name":nm,"version":ver,"arch":arch,"summary":summ}
        except Exception:
            pass

    # --- Arch Linux ---
    if distro == "arch":
        try:
            lines = subprocess.check_output(
                ["pacman","-Qi",name], stderr=subprocess.DEVNULL, timeout=20
            ).decode().splitlines()
            data = {}
            for l in lines:
                if l.startswith("Name"):
                    data["name"] = l.split(":",1)[1].strip()
                elif l.startswith("Version"):
                    data["version"] = l.split(":",1)[1].strip()
                elif l.startswith("Architecture"):
                    data["arch"] = l.split(":",1)[1].strip()
                elif l.startswith("Description"):
                    data["summary"] = l.split(":",1)[1].strip()
            return {
                "name": data.get("name", name),
                "version": data.get("version","-"),
                "arch": data.get("arch","-"),
                "summary": data.get("summary","-")
            }
        except Exception:
            pass

    # --- Debian / Ubuntu ---
    if distro in ("debian","ubuntu"):
        try:
            lines = subprocess.check_output(
                ["apt-cache","show",name],
                stderr=subprocess.DEVNULL, timeout=20
            ).decode().splitlines()
            data = {}
            for l in lines:
                if l.startswith("Package:"):
                    data["name"] = l.split(":",1)[1].strip()
                elif l.startswith("Version:"):
                    data["version"] = l.split(":",1)[1].strip()
                elif l.startswith("Architecture:"):
                    data["arch"] = l.split(":",1)[1].strip()
                elif l.startswith("Description:"):
                    data["summary"] = l.split(":",1)[1].strip()
                    break
            return {
                "name": data.get("name", name),
                "version": data.get("version","-"),
                "arch": data.get("arch","-"),
                "summary": data.get("summary","-")
            }
        except Exception:
            pass

    # --- macOS (Homebrew) ---
    if os_name == "macos":
        try:
            out = subprocess.check_output(
                ["brew","info","--json=v1",name],
                stderr=subprocess.DEVNULL, timeout=20
            )
            arr = json.loads(out)[0]
            return {
                "name": arr.get("name",name),
                "version": arr.get("versions",{}).get("stable","-"),
                "arch": "-",
                "summary": arr.get("desc","-")
            }
        except Exception:
            pass

    # --- Windows (winget) ---
    if os_name == "windows":
        try:
            lines = subprocess.check_output(
                ["winget","show",name,"--id"],
                stderr=subprocess.DEVNULL, timeout=20
            ).decode().splitlines()
            data = {}
            for l in lines:
                if l.startswith("Id:"):
                    data["name"] = l.split(":",1)[1].strip()
                elif l.startswith("Version:"):
                    data["version"] = l.split(":",1)[1].strip()
                elif l.startswith("Name:"):
                    data["summary"] = l.split(":",1)[1].strip()
            return {
                "name": data.get("name",name),
                "version": data.get("version","-"),
                "arch": "-",
                "summary": data.get("summary","-")
            }
        except Exception:
            pass

    # --- pip fallback ---
    try:
        lines = subprocess.check_output(
            ["pip","show",name], stderr=subprocess.DEVNULL, timeout=20
        ).decode().splitlines()
        data = {}
        for l in lines:
            if l.startswith("Name:"):
                data["name"] = l.split(":",1)[1].strip()
            elif l.startswith("Version:"):
                data["version"] = l.split(":",1)[1].strip()
            elif l.startswith("Summary:"):
                data["summary"] = l.split(":",1)[1].strip()
        return {
            "name": data.get("name",name),
            "version": data.get("version","-"),
            "arch": "-",
            "summary": data.get("summary","-")
        }
    except Exception:
        pass

    # --- Last resort ---
    return {"name": name, "version": "-", "arch": "-", "summary": "-"}


def search(query: str) -> list[dict]:
    """
    Return list of dicts: {name,version,arch,summary}.
    Falls back on pkg/apt/pacman/apt-cache/pip/winget as needed.
    """
    os_name = get_os()
    distro = get_distro() if os_name == "linux" else None

    # Fedora structured repoquery
    if distro == "fedora":
        cmd = [
            "dnf","repoquery",
            "--qf","%{name}|%{version}-%{release}|%{arch}|%{summary}",
            query
        ]
        try:
            lines = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=20
            ).decode().splitlines()
            results = []
            for l in lines:
                m = RE_FEDORA.match(l)
                if m:
                    nm,ver,arch,summ = m.groups()
                    results.append({
                        "name": nm,"version": ver,"arch": arch,"summary": summ
                    })
            return results
        except Exception:
            return []

    # Choose fallback command
    if os_name == "android":
        cmd = ["pkg","search",query]
    elif distro == "arch":
        cmd = ["pacman","-Ss",query]
    elif distro in ("debian","ubuntu"):
        cmd = ["apt-cache","search",query]
    elif os_name == "macos":
        cmd = ["brew","search",query]
    elif os_name == "windows":
        cmd = ["winget","search",query]
    else:
        cmd = ["pip","search",query]

    try:
        lines = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=20
        ).decode().splitlines()
    except Exception:
        return []

    results = []
    for l in lines:
        if ":" not in l: 
            continue
        nm, summ = l.split(":",1)
        results.append({
            "name":    nm.strip(),
            "version": "",
            "arch":    "",
            "summary": summ.strip()
        })
    return results


def install(name: str) -> bool:
    """
    Install via native tool (pkg/pacman/apt-get/dnf/brew/winget/pip).
    """
    cmd = _select_cmd("install", name)
    try:
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        logger.debug("Install failed %s → %s", cmd, e)
        return False


def remove(name: str) -> bool:
    """
    Remove via native tool.
    """
    cmd = _select_cmd("remove", name)
    try:
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        logger.debug("Remove failed %s → %s", cmd, e)
        return False


def update() -> bool:
    """
    Refresh package database. On Fedora, exitcode 100 means updates available.
    """
    os_name = get_os()
    distro = get_distro() if os_name == "linux" else None

    try:
        if os_name == "android":
            cmd = ["pkg","update"]
        elif distro == "arch":
            cmd = ["sudo","pacman","-Sy"]
        elif distro in ("debian","ubuntu"):
            cmd = ["sudo","apt-get","update"]
        elif distro == "fedora":
            cmd = ["sudo","dnf","check-update"]
        else:
            return False

        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode in (0,100)
    except Exception:
        return False


def upgrade() -> bool:
    """
    Upgrade all packages.
    """
    os_name = get_os()
    distro = get_distro() if os_name == "linux" else None

    try:
        if os_name == "android":
            cmd = ["pkg","upgrade","-y"]
        elif distro == "arch":
            cmd = ["sudo","pacman","-Syu","--noconfirm"]
        elif distro in ("debian","ubuntu"):
            cmd = ["sudo","apt-get","upgrade","-y"]
        elif distro == "fedora":
            cmd = ["sudo","dnf","upgrade","-y"]
        else:
            return False

        subprocess.check_call(cmd)
        return True
    except Exception:
        return False


def _select_cmd(action: str, arg: str) -> list[str]:
    """
    Returns the subprocess argv list for `search`/`install`/`remove`.
    """
    os_name = get_os()
    distro = get_distro() if os_name == "linux" else None

    # Termux / Android
    if os_name == "android":
        return {
            "search": ["pkg","search",arg],
            "install": ["pkg","install",arg],
            "remove": ["pkg","uninstall",arg]
        }.get(action, [])

    # Linux distributions
    if os_name == "linux":
        if action == "search":
            if distro == "arch":
                return ["pacman","-Ss",arg]
            if distro in ("debian","ubuntu"):
                return ["apt-cache","search",arg]
            if distro == "fedora":
                return ["dnf","search",arg]
        if action == "install":
            if distro == "arch":
                return ["sudo","pacman","-S","--noconfirm",arg]
            if distro in ("debian","ubuntu"):
                return ["sudo","apt-get","install","-y",arg]
            if distro == "fedora":
                return ["sudo","dnf","install","-y",arg]
        if action == "remove":
            if distro == "arch":
                return ["sudo","pacman","-Rsn","--noconfirm",arg]
            if distro in ("debian","ubuntu"):
                return ["sudo","apt-get","remove","-y",arg]
            if distro == "fedora":
                return ["sudo","dnf","remove","-y",arg]

    # macOS Homebrew
    if os_name == "macos":
        return {
            "search":  ["brew","search",arg],
            "install": ["brew","install",arg],
            "remove":  ["brew","uninstall",arg]
        }.get(action, [])

    # Windows Winget
    if os_name == "windows":
        return {
            "search":  ["winget","search",arg],
            "install": ["winget","install",
                        "--accept-source-agreements",
                        "--accept-package-agreements",arg],
            "remove":  ["winget","uninstall",arg]
        }.get(action, [])

    # pip fallback
    return {
        "search":  ["pip","search",arg],
        "install": ["pip","install",arg],
        "remove":  ["pip","uninstall","-y",arg]
    }.get(action, [])
