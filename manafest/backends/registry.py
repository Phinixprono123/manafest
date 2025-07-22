import pkgutil, importlib
from manafest.utils.osdetect import get_os

BACKENDS = {}
for _, modname, _ in pkgutil.iter_modules(__path__):
    mod = importlib.import_module(f"manafest.backends.{modname}")
    BACKENDS[mod.name] = mod

def get_available_backends(force=False):
    osname = get_os()
    for name,mod in BACKENDS.items():
        if osname in mod.supported_os or force:
            yield name, mod

