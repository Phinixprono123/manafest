# main.py
#!/usr/bin/env python3
import sys
from rich.console import Console
import argparse
from manafest.pkgmanager import (
    install,
    search,
    remove,
    list_installed,
    info,
    list_processes,
    clone,
    update,
    upgrade,
)

console = Console()


class RichParser(argparse.ArgumentParser):
    def error(self, message):
        console.print(f"[bold red]Error:[/] {message}\n")
        self.print_help()
        sys.exit(2)


def parse_args():
    parser = RichParser(
        prog="manafest",
        description="Manafest: multi-OS, multi-backend package manager",
        allow_abbrev=False,
    )

    parser.add_argument(
        "action",
        choices=[
            "install",
            "search",
            "remove",
            "list",
            "info",
            "ps",
            "clone",
            "update",
            "upgrade",
        ],
        help="Action to perform",
    )
    parser.add_argument(
        "target", nargs="?", help="Package name, search query, or repo identifier/URL"
    )

    parser.add_argument("--aur", action="store_true", help="Use AUR backend")
    parser.add_argument("--github", action="store_true", help="Use GitHub backend")
    parser.add_argument("--gitlab", action="store_true", help="Use GitLab backend")
    parser.add_argument("--pypi", action="store_true", help="Use PyPI backend")
    parser.add_argument(
        "--bitbucket", action="store_true", help="Use Bitbucket backend"
    )
    parser.add_argument(
        "--url", action="store_true", help="Treat target as raw Git URL"
    )
    parser.add_argument(
        "--all", action="store_true", help="Use all backends for search/update"
    )

    parser.add_argument("--depth", type=int, default=None, help="Shallow clone depth")
    parser.add_argument("--branch", type=str, default=None, help="Branch or tag")
    parser.add_argument(
        "--out", type=str, default=None, help="Destination directory for clone"
    )

    return parser.parse_args()


def main():
    args = parse_args()
    chosen = []
    if args.aur:
        chosen.append("aur")
    if args.github:
        chosen.append("github")
    if args.gitlab:
        chosen.append("gitlab")
    if args.pypi:
        chosen.append("pypi")
    if args.bitbucket:
        chosen.append("bitbucket")
    if not chosen:
        chosen = ["default"]

    all_backends = ["default", "aur", "github", "gitlab", "pypi", "bitbucket"]
    if args.all and args.action in ("search", "update"):
        sources = all_backends
    else:
        sources = chosen

    act = args.action
    tgt = args.target

    if act == "install":
        install(tgt, sources[0])
    elif act == "search":
        search(tgt, sources)
    elif act == "remove":
        remove(tgt)
    elif act == "list":
        list_installed(all_sources=args.all)
    elif act == "info":
        info(tgt)
    elif act == "ps":
        list_processes()
    elif act == "clone":
        clone(
            repo=tgt,
            source="github" if args.github and not args.url else "url",
            depth=args.depth,
            branch=args.branch,
            outdir=args.out,
        )
    elif act == "update":
        update(sources)
    elif act == "upgrade":
        upgrade()
    else:
        console.print(f"[bold red]Unknown action:[/] {act}")
        sys.exit(1)


if __name__ == "__main__":
    main()
