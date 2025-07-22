#!/usr/bin/env python3
import sys
import argparse
from rich.console import Console
from manafest.pkgmanager import (
    install, search, remove,
    list_installed, info,
    update, upgrade
)

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(
        prog="manafest",
        description="Manafest: unified multi-source package manager",
        allow_abbrev=False
    )

    parser.add_argument("action", choices=[
        "install", "search", "remove",
        "list", "info", "ps",
        "update", "upgrade"
    ], help="Action to perform")

    parser.add_argument("target", nargs="?", help="Package name or search query")

    # backend selectors
    parser.add_argument("--default", action="store_true", help="Use system (apt/dnf/pacman/brew/pip)")
    parser.add_argument("--aur",     action="store_true", help="Use AUR backend")
    parser.add_argument("--flatpak", action="store_true", help="Use Flatpak backend")
    parser.add_argument("--snap",    action="store_true", help="Use Snap backend")
    parser.add_argument("--pypi",    action="store_true", help="Use PyPI backend")

    parser.add_argument(
        "--all",
        action="store_true",
        help="For search/update/upgrade: operate on ALL backends"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore unsupported-OS warnings"
    )

    return parser.parse_args()

def main():
    args = parse_args()

    # gather the chosen backends
    chosen = []
    if args.default: chosen.append("default")
    if args.aur:     chosen.append("aur")
    if args.flatpak: chosen.append("flatpak")
    if args.snap:    chosen.append("snap")
    if args.pypi:    chosen.append("pypi")

    all_backends = ["default","aur","flatpak","snap","pypi"]
    if args.all and args.action in ("search","update","upgrade"):
        sources = all_backends
    else:
        # default to system if nothing selected
        sources = chosen or ["default"]

    try:
        if args.action == "install":
            install(args.target, sources[0])
        elif args.action == "search":
            search(args.target, sources)
        elif args.action == "remove":
            remove(args.target)
        elif args.action == "list":
            list_installed()
        elif args.action == "info":
            info(args.target)
        elif args.action == "ps":
            list_processes()
        elif args.action == "update":
            update(sources)
        elif args.action == "upgrade":
            upgrade(sources)
    except Exception as e:
        console.print(f"[bold red]Fatal error:[/] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

