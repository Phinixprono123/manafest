# backends/gitlab.py
import requests
import subprocess
import shutil

GITLAB_SEARCH = "https://gitlab.com/api/v4/projects?search="


def search(query):
    try:
        r = requests.get(GITLAB_SEARCH + query, timeout=5)
        r.raise_for_status()
        return [p["path_with_namespace"] for p in r.json()]
    except Exception:
        return []


def info(name):
    """Fetch single‐project info by URL‐encoded path."""
    try:
        url = f"https://gitlab.com/api/v4/projects/{requests.utils.requote_uri(name)}"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        d = r.json()
        return {
            "name": d["path_with_namespace"],
            "description": d.get("description"),
            "stars": d.get("star_count", 0),
            "web_url": d.get("web_url"),
        }
    except Exception:
        return {}


def install(name):
    """Just `git clone` the GitLab repo."""
    url = f"https://gitlab.com/{name}.git"
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
