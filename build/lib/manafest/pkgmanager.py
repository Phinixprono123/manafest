import subprocess
import sys
import logging
import asyncio
import json

from pathlib import Path
from datetime import datetime

import psutil
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.table import Table

from manafest.utils.errors import handle_errors
from manafest.utils.cache import read_registry, write_registry
from manafest.backends import default, aur, flatpak, snap, pypi

logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()
REGISTRY = Path(__file__).parent.parent / "registry.json"
BACKENDS = {
    "default": default,
    "aur": aur,
    "flatpak": flatpak,
    "snap": snap,
    "pypi": pypi
}


def _maybe_await(fn, *args, **kwargs):
    out = fn(*args, **kwargs)
    if asyncio.iscoroutine(out):
        return asyncio.get_event_loop().run_until_complete(out)
    return out

def _select_cmd(source: str, action: str, name: str):
    """
    Delegate to the backend's _select_cmd for install/remove/search.
    """
    if source == "default":
        return default._select_cmd(action, name)
    return BACKENDS[source]._select_cmd(action, name)


@handle_errors
def remove(name: str):
    if not name:
        raise ValueError("remove requires a package name")

    reg = read_registry(REGISTRY)

    # Determine source & metadata
    if name in reg:
        src = reg[name]["source"]
        meta = default.info(name) if src == "default" else reg[name]["info"]
    elif default.installed(name):
        src = "default"
        meta = default.info(name)
    else:
        return console.print(f"[red]❌ '{name}' not found in Manafest or system[/red]")

    # Confirm panel
    panel = Panel.fit(
        "\n".join([
            f"[bold]Package[/bold]: {meta.get('name', name)}",
            f"[bold]Source[/bold]: {src.capitalize()}",
            f"[bold]Version[/bold]: {meta.get('version','-')}",
            f"[bold]Arch[/bold]: {meta.get('arch','-')}"
        ]),
        title="[magenta]Confirm Removal[/magenta]",
        border_style="magenta"
    )
    console.print(panel)
    if Prompt.ask("Remove this package?", choices=["y","n"], default="n") != "y":
        return console.print("[yellow]Aborted[/yellow]")

    # Run removal command
    cmd = _select_cmd(src, "remove", name)
    console.print(f"[magenta]Removing {name}...[/magenta]")

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=sys.stdin,
        text=True
    )
    logs = proc.stdout.splitlines()
    success = proc.returncode == 0

    # Final summary
    snippet = "\n".join(logs[-5:])  # last 5 lines
    if success:
        # clean up registry if it was a Manafest install
        if name in reg and reg[name]["source"] == src:
            reg.pop(name)
            write_registry(REGISTRY, reg)

        console.print(Panel.fit(
            f"[bold green]✔️ Removed {meta.get('name')} {meta.get('version')}[/bold green]\n\n{snippet}",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]❌ Failed to remove {meta.get('name')}[/bold red]\n\n{snippet}",
            border_style="red"
        ))


@handle_errors
def install(name: str, source: str):
    if not name:
        raise ValueError("install requires a package name")

    # Preview metadata
    if source == "default":
        info_data = default.info(name)
    elif hasattr(BACKENDS[source], "info"):
        info_data = _maybe_await(BACKENDS[source].info, name) or {}
    else:
        info_data = {}

    panel = Panel.fit(
        "\n".join([
            f"[bold]Package[/bold]: {info_data.get('name', name)}",
            f"[bold]Source[/bold]: {source.capitalize()}",
            f"[bold]Version[/bold]: {info_data.get('version','-')}",
            f"[bold]Arch[/bold]: {info_data.get('arch','-')}",
            f"[bold]Summary[/bold]: {info_data.get('summary','-')}"
        ]),
        title="[cyan]Ready to Install[/cyan]",
        border_style="cyan"
    )
    console.print(panel)
    if Prompt.ask("Proceed with installation?", choices=["y","n"], default="n") != "y":
        return console.print("[red]❌ Installation cancelled[/]")

    console.print(f"[cyan]Installing {name}...[/cyan]")
    success = _maybe_await(BACKENDS[source].install, name)

    if not success:
        return console.print(f"[red]❌ Failed to install {name}[/red]")

    # Fetch fresh metadata
    if source == "default":
        fresh = default.info(name)
    elif hasattr(BACKENDS[source], "info"):
        fresh = _maybe_await(BACKENDS[source].info, name) or {}
    else:
        fresh = {}

    meta = fresh if isinstance(fresh, dict) and fresh else {"name": name}

    # Record in registry
    reg = read_registry(REGISTRY)
    reg[name] = {
        "source": source,
        "info": meta,
        "installed_at": datetime.utcnow().isoformat()
    }
    write_registry(REGISTRY, reg)

    console.print(Panel.fit(
        f"[bold green]✔️ Installed {meta.get('name')} {meta.get('version','')} ({meta.get('arch','')})[/bold green]",
        border_style="green"
    ))


@handle_errors
def search(query: str, sources: list[str]):
    console.print(f"[bold cyan]🔍 Searching for [green]{query}[/green]…[/]\n")

    for src in sources:
        try:
            pkgs = BACKENDS[src].search(query) or []
        except Exception as e:
            logger.debug(f"{src}.search failed: {e}")
            pkgs = []

        table = Table(title=f"[magenta]{src.capitalize()} Results[/magenta]", show_lines=True)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Version", style="green")
        table.add_column("Arch", style="yellow")
        table.add_column("Summary", style="white")

        if not pkgs:
            table.add_row("-", "-", "-", "No results")
        else:
            for p in pkgs:
                if isinstance(p, dict):
                    name    = p.get("name", "-")
                    version = p.get("version", "-")
                    arch    = p.get("arch", "-")
                    summary = p.get("summary", "-")
                else:
                    # fallback for plain strings
                    name, version, arch, summary = p, "-", "-", "-"
                table.add_row(name, version, arch, summary)

        console.print(table)
        console.print()

@handle_errors
def list_installed():
    reg = read_registry(REGISTRY)
    if not reg:
        return console.print("[bold]No packages installed by Manafest[/]")

    table = Table(title="Installed by Manafest")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Arch", style="yellow")
    table.add_column("Source", style="magenta")
    table.add_column("When", style="white")
    for pkg, data in reg.items():
        info = data["info"]
        table.add_row(
            info.get("name", pkg),
            info.get("version","-"),
            info.get("arch","-"),
            data["source"].capitalize(),
            data.get("installed_at","-")
        )
    console.print(table)


@handle_errors
def info(name: str):
    if not name:
        raise ValueError("info requires a package name")

    reg = read_registry(REGISTRY)
    if name in reg:
        console.print(Panel.fit(json.dumps(reg[name]["info"], indent=2),
                                title=f"[cyan]Local info: {name}[/cyan]"))
        return

    console.print(f"[cyan]Fetching info for [green]{name}[/green]…[/]")
    results = {}
    for src, mod in BACKENDS.items():
        if hasattr(mod, "info"):
            try:
                results[src] = _maybe_await(mod.info, name) or {}
            except Exception:
                results[src] = {}
    for src, data in results.items():
        if not data:
            console.print(f"[magenta]{src.capitalize()}[/magenta] [red]No info[/red]")
        else:
            console.print(Panel.fit(json.dumps(data, indent=2),
                                    title=f"[magenta]{src.capitalize()}[/magenta]"))

@handle_errors
def update(sources: list[str]):
    console.print(f"[yellow]🔄 Updating backends: {', '.join(sources)}[/yellow]")
    for src in sources:
        backend = BACKENDS[src]
        if hasattr(backend, "update"):
            ok = _maybe_await(backend.update)
            if ok:
                console.print(f"[green]✔️ {src.capitalize()} updated[/green]")
            else:
                console.print(f"[red]❌ {src.capitalize()} update failed[/red]")
        else:
            console.print(f"[red]⚠️ {src.capitalize()} cannot update[/red]")


@handle_errors
def upgrade(sources: list[str]):
    console.print(f"[yellow]⬆️ Upgrading backends: {', '.join(sources)}[/yellow]")
    for src in sources:
        backend = BACKENDS[src]
        if hasattr(backend, "upgrade"):
            ok = _maybe_await(backend.upgrade)
            if ok:
                console.print(f"[green]✔️ {src.capitalize()} upgraded[/green]")
            else:
                console.print(f"[red]❌ {src.capitalize()} upgrade failed[/red]")
        else:
            console.print(f"[red]⚠️ {src.capitalize()} cannot upgrade[/red]")

