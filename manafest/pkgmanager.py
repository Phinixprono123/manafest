# manafest/pkgmanager.py

import subprocess
import sys
import asyncio
import json
import shutil
import logging

from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from manafest.utils.errors import handle_errors
from manafest.utils.cache import read_registry, write_registry
from manafest.backends import default, aur, flatpak, snap, pypi
from manafest.utils.osdetect import get_os, get_distro

logger = logging.getLogger("manafest")
console = Console()

REGISTRY = Path(__file__).parent.parent / "registry.json"
BACKENDS = {
    "default": default,
    "aur": aur,
    "flatpak": flatpak,
    "snap": snap,
    "pypi": pypi
}

HAS_FLATPAK = shutil.which("flatpak") is not None
HAS_SNAP    = shutil.which("snap")    is not None


def _maybe_await(fn, *args, **kwargs):
    out = fn(*args, **kwargs)
    if asyncio.iscoroutine(out):
        return asyncio.get_event_loop().run_until_complete(out)
    return out


@handle_errors
def install(name: str, source: str, force: bool = False):
    if not name:
        raise ValueError("install requires a package name")

    # block missing runtimes
    if source == "flatpak" and not HAS_FLATPAK:
        return console.print("[red]Flatpak not installed[/red]")
    if source == "snap"    and not HAS_SNAP:
        return console.print("[red]Snap not installed[/red]")

    # block AUR off-Arch
    if source == "aur":
        distro = get_distro() if get_os()=="linux" else None
        if distro != "arch" and not force:
            return console.print(
                "[red]❌ AUR only on Arch-based systems. Use --force to override.[/red]"
            )

    # preview metadata
    if source == "default":
        meta = default.info(name)
    elif hasattr(BACKENDS[source], "info"):
        meta = _maybe_await(BACKENDS[source].info, name) or {}
    else:
        meta = {}

    console.print(Panel.fit(
        "\n".join([
            f"[bold]Package[/bold]: {meta.get('name', name)}",
            f"[bold]Source[/bold]: {source.capitalize()}",
            f"[bold]Version[/bold]: {meta.get('version','-')}",
            f"[bold]Arch[/bold]: {meta.get('arch','-')}",
            f"[bold]Summary[/bold]: {meta.get('summary','-')}"
        ]),
        title="[cyan]Ready to Install[/cyan]",
        border_style="cyan"
    ))
    if Prompt.ask("Proceed?", choices=["y","n"], default="n") != "y":
        return console.print("[yellow]Cancelled[/yellow]")

    console.print(f"[cyan]Installing {name}...[/cyan]")
    ok = _maybe_await(BACKENDS[source].install, name)
    if not ok:
        return console.print(f"[red]❌ install failed[/red]")

    # record registry
    fresh = (default.info(name) if source=="default"
             else _maybe_await(BACKENDS[source].info, name) or {})
    entry = fresh if isinstance(fresh, dict) and fresh else {"name":name}

    reg = read_registry(REGISTRY)
    reg[name] = {
        "source": source,
        "info": entry,
        "installed_at": datetime.utcnow().isoformat()
    }
    write_registry(REGISTRY, reg)

    console.print(Panel.fit(
        f"[bold green]✔️ Installed {entry.get('name')} {entry.get('version','')}[/bold green]",
        border_style="green"
    ))


@handle_errors
def remove(name: str):
    if not name:
        raise ValueError("remove requires a package name")

    reg = read_registry(REGISTRY)
    if name in reg:
        src = reg[name]["source"]
        meta = (default.info(name) if src=="default" else reg[name]["info"])
    elif default.installed(name):
        src = "default"
        meta = default.info(name)
    else:
        return console.print(f"[red]❌ '{name}' not found[/red]")

    console.print(Panel.fit(
        "\n".join([
            f"[bold]Package[/bold]: {meta.get('name', name)}",
            f"[bold]Source[/bold]: {src.capitalize()}",
            f"[bold]Version[/bold]: {meta.get('version','-')}",
            f"[bold]Arch[/bold]: {meta.get('arch','-')}"
        ]),
        title="[magenta]Confirm Removal[/magenta]",
        border_style="magenta"
    ))
    if Prompt.ask("Remove?", choices=["y","n"], default="n") != "y":
        return console.print("[yellow]Aborted[/yellow]")

    console.print(f"[magenta]Removing {name}...[/magenta]")
    if src == "default":
        cmd = default._select_cmd("remove", name)
    else:
        cmd = BACKENDS[src]._select_cmd("remove", name)

    proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, stdin=sys.stdin, text=True)
    logs = proc.stdout.splitlines()
    success = proc.returncode == 0
    snippet = "\n".join(logs[-5:])

    if success:
        if name in reg and reg[name]["source"]==src:
            reg.pop(name)
            write_registry(REGISTRY, reg)
        console.print(Panel.fit(
            f"[bold green]✔️ Removed {meta.get('name')} {meta.get('version')}[/bold green]\n\n{snippet}",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]❌ Removal failed[/bold red]\n\n{snippet}",
            border_style="red"
        ))


@handle_errors
def search(query: str, sources: list[str]):
    if not query:
        raise ValueError("search requires a query")

    console.print(f"[bold cyan]🔍 Searching for [green]{query}[/green]…[/]\n")
    for src in sources:
        if src=="flatpak" and not HAS_FLATPAK: continue
        if src=="snap"    and not HAS_SNAP:    continue

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
                    n=p.get("name","-"); v=p.get("version","-")
                    a=p.get("arch","-");   s=p.get("summary","-")
                else:
                    n,v,a,s = p,"-","-","-"
                table.add_row(n,v,a,s)

        console.print(table); console.print()


@handle_errors
def list_installed():
    reg = read_registry(REGISTRY)
    if not reg:
        return console.print("[bold]No packages installed[/]")

    table = Table(title="Installed by Manafest")
    table.add_column("Name", style="cyan"); table.add_column("Version", style="green")
    table.add_column("Arch", style="yellow"); table.add_column("Source", style="magenta")
    table.add_column("When", style="white")
    for pkg,data in reg.items():
        info = data["info"]
        table.add_row(
            info.get("name",pkg),
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
        console.print(Panel.fit(
            json.dumps(reg[name]["info"], indent=2),
            title=f"[cyan]Local info: {name}[/cyan]"
        ))
        return

    console.print(f"[cyan]Fetching info for [green]{name}[/green]…[/]")
    for src,mod in BACKENDS.items():
        if src=="flatpak" and not HAS_FLATPAK: continue
        if src=="snap"    and not HAS_SNAP:    continue
        if hasattr(mod,"info"):
            try:
                data = _maybe_await(mod.info, name) or {}
            except:
                data = {}
            if not data:
                console.print(f"[magenta]{src.capitalize()}[/magenta] [red]No info[/red]")
            else:
                console.print(Panel.fit(
                    json.dumps(data, indent=2),
                    title=f"[magenta]{src.capitalize()}[/magenta]"
                ))


@handle_errors
def update(sources: list[str], force: bool = False):
    console.print(f"[yellow]🔄 Updating backends: {', '.join(sources)}[/yellow]")
    for src in sources:
        if src=="aur":
            distro = get_distro() if get_os()=="linux" else None
            if distro!="arch" and not force:
                console.print("[red]❌ Skipping AUR (Arch only). --force to override[/red]")
                continue
        if src=="flatpak" and not HAS_FLATPAK: continue
        if src=="snap"    and not HAS_SNAP:    continue

        backend = BACKENDS[src]
        if src=="pypi":
            # pip-based update = list & upgrade outdated
            try:
                out = subprocess.check_output(
                    ["pip","list","--outdated","--format=json"],
                    text=True, stderr=subprocess.DEVNULL
                )
                data = json.loads(out)
                if not data:
                    console.print("[green]All pip packages up-to-date[/green]")
                else:
                    console.print(f"[cyan]Upgrading {len(data)} pip packages...[/cyan]")
                    for p in data:
                        subprocess.check_call(["pip","install","--upgrade",p["name"]])
                    console.print("[green]✔️ pip packages upgraded[/green]")
                continue
            except Exception:
                console.print("[red]❌ pip update failed[/red]")
                continue

        if hasattr(backend, "update"):
            ok = _maybe_await(backend.update)
            label = src.capitalize()
            console.print(f"[green]✔️ {label} updated[/green]" if ok
                          else f"[red]❌ {label} update failed[/red]")
        else:
            console.print(f"[red]⚠️ {src.capitalize()} cannot update[/red]")


@handle_errors
def upgrade(sources: list[str], force: bool = False):
    console.print(f"[yellow]⬆️ Upgrading backends: {', '.join(sources)}[/yellow]")
    for src in sources:
        if src=="aur":
            distro = get_distro() if get_os()=="linux" else None
            if distro!="arch" and not force:
                console.print("[red]❌ Skipping AUR (Arch only). --force to override[/red]")
                continue
        if src=="flatpak" and not HAS_FLATPAK: continue
        if src=="snap"    and not HAS_SNAP:    continue

        backend = BACKENDS[src]
        if src=="pypi":
            # pip upgrade is same as update above
            # already done in update()
            continue

        if hasattr(backend, "upgrade"):
            ok = _maybe_await(backend.upgrade)
            label = src.capitalize()
            console.print(f"[green]✔️ {label} upgraded[/green]" if ok
                          else f"[red]❌ {label} upgrade failed[/red]")
        else:
            console.print(f"[red]⚠️ {src.capitalize()} cannot upgrade[/red]")
