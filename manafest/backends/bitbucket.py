# backends/bitbucket.py
import requests
import subprocess
import shutil

BB_SEARCH = 'https://api.bitbucket.org/2.0/repositories?search=name~"'


def search(query):
    try:
        r = requests.get(BB_SEARCH + query + '"', timeout=5)
        r.raise_for_status()
        vals = r.json().get("values", [])
        return [v["full_name"] for v in vals]
    except Exception:
        return []


def info(name):
    """Fetch repository info from Bitbucket."""
    try:
        url = f"https://api.bitbucket.org/2.0/repositories/{name}"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        d = r.json()
        return {
            "name": d.get("full_name"),
            "description": d.get("description"),
            "links": d.get("links", {}).get("html", {}).get("href"),
        }
    except Exception:
        return {}


def install(name):
    """Just `git clone` the Bitbucket repo."""
    url = f"https://bitbucket.org/{name}.git"
    try:
        subprocess.run(["git", "clone", url], check=True)
        return {"repo": name}
    except Exception:
        return {}


def remove(name):
    """Delete the cloned directory."""
    try:
        shutil.rmtree(name, ignore_errors=True)
        return True
    except Exception:
        return False
