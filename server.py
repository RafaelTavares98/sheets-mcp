"""The one command.

    python server.py connect <url> <word>
    python server.py check
    python server.py serve

`serve` is what an agent runs. It speaks MCP on its own input and
output, so it prints nothing else there: a stray line of chatter breaks
the conversation.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import mcp_protocol  # noqa: E402
import sheet_client  # noqa: E402
import tools  # noqa: E402


def main(argv=None) -> int:
    """Read the arguments and do the one thing."""
    arguments = build_parser().parse_args(argv)
    if arguments.command == "connect":
        return connect(arguments)
    if arguments.command == "check":
        return check()
    return serve()


def build_parser() -> argparse.ArgumentParser:
    """Every way the command can be called."""
    parser = argparse.ArgumentParser(prog="sheets mcp")
    commands = parser.add_subparsers(dest="command", required=True)

    joining = commands.add_parser(
        "connect", help="remember a deployed Apps Script address"
    )
    joining.add_argument("url")
    joining.add_argument("word")

    commands.add_parser("check", help="prove the spreadsheet answers")
    commands.add_parser("serve", help="speak MCP to an agent")
    return parser


def connect(arguments) -> int:
    """Keep the address and the shared word."""
    sheet_client.remember(arguments.url, arguments.word)
    print("connected. Run: python server.py check")
    return 0


def check() -> int:
    """Prove the spreadsheet answers, and say what is in it."""
    try:
        found = sheet_client.tabs()
    except sheet_client.SheetRefused as refused:
        print(refused)
        return 1
    print(f"tabs: {', '.join(found)}")
    for name in found:
        table = sheet_client.read(name, limit=1)
        print(f"  {name}: {table['total']} rows, "
              f"columns {', '.join(table['columns'])}")
    return 0


def serve() -> int:
    """Answer an agent for as long as it keeps asking."""
    mcp_protocol.serve(
        catalogue=tools.catalogue(),
        run=lambda name, given: tools.run(name, given, sheet_client),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
