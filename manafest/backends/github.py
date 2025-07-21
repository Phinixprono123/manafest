import asyncio
import aiohttp
import logging
import subprocess
from functools import lru_cache

GITHUB_SEARCH = "https://api.github.com/search/repositories?q="
GITHUB_API = "https://api.github.com/repos/"


@lru_cache(maxsize=128)
async def _fetch(url):
    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout) as sess:
        async with sess.get(url) as r:
            r.raise_for_status()
            return await r.json()


def search(query):
    try:
        data = asyncio.run(_fetch(GITHUB_SEARCH + query))
        return [item["full_name"] for item in data.get("items", [])[:10]]
    except Exception as e:
        logging.warning("GitHub search failed: %s", e)
        return []


async def info(name):
    try:
        data = await _fetch(GITHUB_API + name)
        return {
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "stars": data.get("stargazers_count"),
            "url": data.get("html_url"),
        }
    except Exception as e:
        logging.warning("GitHub info failed: %s", e)
        return {}


def install(name):
    try:
        subprocess.run(["git", "clone", f"https://github.com/{name}.git"], check=True)
        return {"repo": name}
    except Exception as e:
        logging.error("GitHub install failed: %s", e)
        return {}


def remove(name):
    try:
        subprocess.run(["rm", "-rf", name], check=True)
        return True
    except Exception as e:
        logging.error("GitHub remove failed: %s", e)
        return False
