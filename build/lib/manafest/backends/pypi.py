import xmlrpc.client
import logging

PYPI_RPC = "https://pypi.org/pypi"


def search(query):
    """
    Use the PyPI XML-RPC interface to search on package name.
    Returns a list of package names (max 10).
    """
    try:
        client = xmlrpc.client.ServerProxy(PYPI_RPC)
        hits = client.search({"name": query}, "or")
        return [hit["name"] for hit in hits[:10]]
    except Exception as e:
        logging.debug(f"PyPI search failed for {query!r}: {e}")
        return []


def info(name):
    """
    Fetch metadata for a single package.
    """
    try:
        client = xmlrpc.client.ServerProxy(PYPI_RPC)
        data = client.release_data(name, client.package_releases(name)[0])
        return data
    except Exception:
        return {}


def install(name):
    try:
        import subprocess

        subprocess.run(["pip", "install", name], check=True)
        return {"module": name}
    except Exception as e:
        logging.debug(f"PyPI install failed: {e}")
        return {}


def remove(name):
    try:
        import subprocess

        subprocess.run(["pip", "uninstall", "-y", name], check=True)
        return True
    except Exception as e:
        logging.debug(f"PyPI remove failed: {e}")
        return False
