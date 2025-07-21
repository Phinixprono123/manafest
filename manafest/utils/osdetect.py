import platform
import pathlib


def get_os():
    system = platform.system().lower()
    if system.startswith("darwin"):
        return "macos"
    if system.startswith("windows"):
        return "windows"
    return "linux"


def get_distro():
    data = {}
    path = pathlib.Path("/etc/os-release")
    if not path.exists():
        return "generic"
    for line in path.read_text().splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        k, v = line.split("=", 1)
        data[k] = v.strip().strip('"')
    id_ = data.get("ID", "").lower()
    like = data.get("ID_LIKE", "").lower()
    if id_ in ("arch", "manjaro") or "arch" in like:
        return "arch"
    if id_ in ("debian", "ubuntu") or "debian" in like:
        return "debian"
    if id_ in ("fedora",) or "fedora" in like:
        return "fedora"
    return "generic"
