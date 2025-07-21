import os
import logging
import asyncio
import json
from pathlib import Path
from datetime import datetime

import psutil
import pygit2
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.table import Table

from manafest.utils.errors import handle_errors
from manafest.utils.cache import read_registry, write_registry
from manafest.backends import default, aur, github, gitlab, pypi, bitbucket

logging.getLogger("urllib3").setLevel(logging.WARNING)

console = Console()
REGISTRY = Path(__file__).parent / "registry.json"
BACKENDS = {
    "default": default,
    "aur": aur,
    "github": github,
    "gitlab": gitlab,
    "pypi": pypi,
    "bitbucket": bitbucket,
}


def _show_banner(message: str, style: str = "green"):
    console.rule(Text(message, style=style))


def _maybe_await(func, *args, **kwargs):
    """
    Call func(*args, **kwargs). If it returns a coroutine, run it to completion.
    """
    out = func(*args, **kwargs)
    if asyncio.iscoroutine(out):
        return asyncio.get_event_loop().run_until_complete(out)
    return out


@handle_errors
def install(name, source):
    if not name:
        raise ValueError("install requires a package name")

    # Try to get package metadata for panel
    info_data = {}
    if hasattr(BACKENDS[source], "info"):
        try:
            raw = _maybe_await(BACKENDS[source].info, name) or {}
            # Ensure dict
            info_data = raw if isinstance(raw, dict) else {}
        except Exception:
            info_data = {}

    lines = [
        f"[bold]Package[/bold]: {name}",
        f"[bold]Source[/bold]: {source.capitalize()}",
    ]
    for key in ("description", "version", "stars", "web_url"):
        if info_data.get(key):
            lines.append(f"[bold]{key.capitalize()}[/bold]: {info_data[key]}")

    panel = Panel(
        "\n".join(lines),
        title=Text("Ready to Install", style="cyan bold"),
        border_style="cyan",
    )
    console.print(panel)

    # Ask to confirm
    confirm = Prompt.ask(
        "[yellow]Proceed with installation?[/yellow]", choices=["y", "n"], default="n"
    )
    if confirm != "y":
        return console.print("[red]❌ Installation cancelled[/]")

    _show_banner(f"Installing {name}")
    try:
        raw_meta = _maybe_await(BACKENDS[source].install, name) or {}
        # normalize to dict
        meta = raw_meta if isinstance(raw_meta, dict) else {"raw": raw_meta}
    except Exception as e:
        return console.print(f"[red]❌ Error during install: {e}[/]")

    if not meta:
        return console.print(
            f"[red]❌ No metadata returned; install may have failed[/]"
        )

    # Write registry
    reg = read_registry(REGISTRY)
    reg[name] = {
        "source": source,
        "info": meta,
        "installed_at": datetime.utcnow().isoformat(),
    }
    write_registry(REGISTRY, reg)

    console.print(f"[bold green]✅ {name} installed successfully![/bold green]\n")


@handle_errors
def remove(name):
    if not name:
        raise ValueError("remove requires a package name")

    reg = read_registry(REGISTRY)
    if name not in reg:
        return console.print(f"[red]❌ '{name}' is not installed[/]")

    meta = reg[name]
    source = meta["source"]
    installed_at = meta.get("installed_at", "unknown")

    lines = [
        f"[bold]Package[/bold]: {name}",
        f"[bold]Source[/bold]: {source.capitalize()}",
        f"[bold]Installed at[/bold]: {installed_at}",
    ]
    panel = Panel(
        "\n".join(lines),
        title=Text("About to Remove", style="magenta bold"),
        border_style="magenta",
    )
    console.print(panel)

    confirm = Prompt.ask(
        "[yellow]Really remove this package?[/yellow]", choices=["y", "n"], default="n"
    )
    if confirm != "y":
        return console.print("[red]❌ Removal cancelled[/]")

    _show_banner(f"Removing {name}", style="magenta")
    try:
        success = _maybe_await(BACKENDS[source].remove, name)
    except Exception as e:
        return console.print(f"[red]❌ Error during removal: {e}[/]")

    if success:
        del reg[name]
        write_registry(REGISTRY, reg)
        console.print(f"[bold green]✔️ {name} removed successfully![/bold green]\n")
    else:
        console.print(f"[red]❌ Failed to remove {name}[/]")


@handle_errors
def list_installed(all_sources=False):
    reg = read_registry(REGISTRY)
    if not reg:
        return console.print("[bold]No packages installed[/]")

    console.print("[bold]Installed Packages[/bold]")
    table = Table()
    table.add_column("Package", style="cyan")
    table.add_column("Source", style="magenta")
    table.add_column("Installed At", style="green")

    for name, meta in reg.items():
        table.add_row(name, meta["source"].capitalize(), meta.get("installed_at", "-"))
    console.print(table)


@handle_errors
def info(name):
    if not name:
        raise ValueError("info requires a package name")

    reg = read_registry(REGISTRY)
    if name in reg:
        console.print(f"[bold cyan]ℹ️ Local info for {name}[/]")
        console.print_json(json.dumps(reg[name]["info"], indent=2))
        return

    console.print(f"[cyan]Fetching remote info for [green]{name}[/green]…[/]")
    loop = asyncio.get_event_loop()
    tasks = [
        loop.create_task(BACKENDS[src].info(name))
        for src in BACKENDS
        if hasattr(BACKENDS[src], "info")
    ]
    results = loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

    console.print(f"[bold]Info for [green]{name}[/green][/bold]")
    for src, res in zip(BACKENDS.keys(), results):
        label = f"[magenta]{src.capitalize()}[/magenta]"
        if isinstance(res, Exception) or not res:
            console.print(label, "[red]No info[/red]")
        else:
            console.print(label)
            console.print_json(json.dumps(res, indent=2))


@handle_errors
def search(query, sources):
    if not query:
        raise ValueError("search requires a query")

    console.print(f"[bold cyan]🔍 Searching for [green]{query}[/green]…[/]")

    all_results = []
    total = 0
    for src in sources:
        try:
            pkgs = BACKENDS[src].search(query) or []
        except Exception as e:
            logging.debug(f"{src}.search() failed: {e}")
            pkgs = []
        total += len(pkgs)
        all_results.append((src, pkgs))

    if total > 20:
        confirm = Prompt.ask(
            f"[yellow]⚠️ Found {total} results across {len(sources)} sources. Show all?[/yellow]",
            choices=["y", "n"],
            default="n",
        )
        if confirm != "y":
            return console.print("[red]📋 Display aborted[/]")

    for src, pkgs in all_results:
        console.print(f"\n[bold magenta]{src.capitalize()}[/bold magenta]")
        if not pkgs:
            console.print("  [red]No results[/red]")
        else:
            for pkg in pkgs:
                console.print(f"  • [green]{pkg}[/green]")


@handle_errors
def list_processes():
    console.print("[bold]Active package-related processes:[/]")
    for proc in psutil.process_iter(["pid", "cmdline"]):
        cmd = proc.info["cmdline"] or []
        if cmd and any(tool in cmd[0] for tool in BACKENDS):
            console.print(f"• PID {proc.pid}: {' '.join(cmd)}")


def _silent_clone(url, path, checkout_branch=None, depth=0):
    devnull = os.open(os.devnull, os.O_RDWR)
    orig_out, orig_err = os.dup(1), os.dup(2)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        return pygit2.clone_repository(
            url, path, checkout_branch=checkout_branch, depth=depth
        )
    finally:
        os.dup2(orig_out, 1)
        os.dup2(orig_err, 2)
        os.close(orig_out)
        os.close(orig_err)


@handle_errors
def clone(repo, source, depth=None, branch=None, outdir=None):
    if not repo:
        raise ValueError("clone requires a repo")

    url = (
        f"https://github.com/{repo}.git"
        if source == "github" and not repo.startswith(("http://", "https://", "git@"))
        else repo
    )
    path = outdir or os.path.splitext(os.path.basename(url))[0] or "repo"

    console.print(f"[cyan]🔧 Cloning {url} → {path}[/]")
    repo_obj = _silent_clone(url, path, checkout_branch=branch, depth=depth or 0)
    console.print(f"[green]✅ Cloned into {path}[/]")

    head = repo_obj.revparse_single("HEAD")
    cid = str(head.id)
    console.print(f"    HEAD at {cid[:7]}: {head.message.strip()}")


@handle_errors
def update(sources):
    console.print(f"[yellow]🔄 Updating metadata for {sources}…[/]")
    for src in sources:
        if hasattr(BACKENDS[src], "update"):
            try:
                BACKENDS[src].update()
                console.print(f"[green]✔️ {src.capitalize()} updated[/]")
            except Exception as e:
                console.print(f"[red]⚠️ {src}.update() failed: {e}[/]")
        else:
            console.print(f"[red]⚠️ {src.capitalize()} has no update command[/]")


@handle_errors
def upgrade():
    reg = read_registry(REGISTRY)
    if not reg:
        return console.print("[bold]No packages to upgrade[/]")
    console.print("[green]⬆️ Upgrading installed packages…[/]")
    for name, meta in reg.items():
        src = meta["source"]
        console.print(
            f" • Upgrading [cyan]{name}[/cyan] via [magenta]{src.capitalize()}[/magenta]"
        )
        try:
            _maybe_await(BACKENDS[src].install, name)
        except Exception as e:
            console.print(f"[red]✖️ Upgrade failed for {name}: {e}[/]")
    console.print("[bold green]✅ Upgrade complete[/]")
