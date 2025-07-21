import asyncio
import aiohttp
import logging
import subprocess
from functools import lru_cache
from pathlib import Path

AUR_SEARCH = "https://aur.archlinux.org/rpc/?v=5&type=search&arg="
AUR_INFO = "https://aur.archlinux.org/rpc/?v=5&type=info&arg="


@lru_cache(maxsize=128)
async def _fetch(url):
    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout) as sess:
        async with sess.get(url) as r:
            r.raise_for_status()
            return await r.json()


def search(query):
    try:
        data = asyncio.run(_fetch(AUR_SEARCH + query))
        return [p["Name"] for p in data.get("results", [])]
    except Exception as e:
        logging.warning("AUR search failed: %s", e)
        return []


async def info(name):
    try:
        data = await _fetch(AUR_INFO + name)
        return data.get("results", {})
    except Exception as e:
        logging.warning("AUR info failed: %s", e)
        return {}


def install(name):
    try:
        clone_dir = Path("/tmp") / f"aur_{name}"
        if clone_dir.exists():
            subprocess.run(["rm", "-rf", str(clone_dir)])
        subprocess.run(
            ["git", "clone", f"https://aur.archlinux.org/{name}.git", str(clone_dir)],
            check=True,
        )
        subprocess.run(["makepkg", "-si", "--noconfirm"], cwd=clone_dir, check=True)
        return {"path": str(clone_dir)}
    except Exception as e:
        logging.error("AUR install failed: %s", e)
        return {}


def remove(name):
    try:
        subprocess.run(["sudo", "pacman", "-Rsn", "--noconfirm", name], check=True)
        return True
    except Exception as e:
        logging.error("AUR remove failed: %s", e)
        return False
