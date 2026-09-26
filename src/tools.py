"""The five things an agent can do to the spreadsheet.

Each tool says what it takes and what it is for, in words the model
reads before choosing. A description that only makes sense to the person
who wrote it is a tool the model will misuse.

Nothing here talks to the spreadsheet itself. The client is passed in,
so every tool can be tested without an account.
"""

from typing import Callable, Dict, List

#: How many rows a read returns unless told otherwise. A model handed
#: ten thousand rows spends the client's money on tokens and answers no
#: better than it would with two hundred.
DEFAULT_LIMIT = 200


def catalogue() -> List[Dict]:
    """What the agent is told it can do, before it does anything."""
    return [
        {
            "name": "list_tabs",
            "description": (
                "List the tabs in the spreadsheet. Use this first when "
                "you do not know which tab holds what you need."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "read_tab",
            "description": (
                "Read the rows of one tab. The first row is the header, "
                "and every row comes back keyed by it. Use this when you "
                "need the whole table, and find_rows when you are after "
                "particular rows."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tab": {
                        "type": "string",
                        "description": "The name of the tab.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            f"How many rows at most. Default "
                            f"{DEFAULT_LIMIT}."
                        ),
                    },
                },
                "required": ["tab"],
            },
        },
        {
            "name": "find_rows",
            "description": (
                "Find the rows whose named column holds a value. The "
                "match ignores case and matches part of a cell unless "
                "exact is true."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tab": {"type": "string"},
                    "column": {
                        "type": "string",
                        "description": "A column name from the header.",
                    },
                    "value": {"type": "string"},
                    "exact": {
                        "type": "boolean",
                        "description": (
                            "True to match the whole cell. Default false."
                        ),
                    },
                },
                "required": ["tab", "column", "value"],
            },
        },
        {
            "name": "append_row",
            "description": (
                "Add one row at the bottom of a tab. Give the values "
                "keyed by column name; a column left out is written "
                "empty. Read the tab first if you do not know its "
                "columns."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tab": {"type": "string"},
                    "row": {
                        "type": "object",
                        "description": "Column name to value.",
                    },
                },
                "required": ["tab", "row"],
            },
        },
        {
            "name": "update_row",
            "description": (
                "Change cells of the one row where a column holds a "
                "value. It refuses when more than one row matches, so "
                "identify the row by something unique such as an order "
                "number."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tab": {"type": "string"},
                    "column": {
                        "type": "string",
                        "description": "The column that identifies the row.",
                    },
                    "value": {"type": "string"},
                    "changes": {
                        "type": "object",
                        "description": "Column name to its new value.",
                    },
                },
                "required": ["tab", "column", "value", "changes"],
            },
        },
    ]


def names() -> List[str]:
    """The names of every tool, for a quick check."""
    return [tool["name"] for tool in catalogue()]


def run(name: str, given: Dict, client) -> Dict:
    """Carry out one tool and return what it found.

    An unknown name is said plainly. Guessing which tool was meant is
    how an agent deletes the wrong row.
    """
    given = given or {}
    if name == "list_tabs":
        return {"tabs": client.tabs()}
    if name == "read_tab":
        return client.read(
            _needed(given, "tab"), given.get("limit") or DEFAULT_LIMIT
        )
    if name == "find_rows":
        return client.find(
            _needed(given, "tab"),
            _needed(given, "column"),
            _needed(given, "value"),
            bool(given.get("exact")),
        )
    if name == "append_row":
        return client.append(_needed(given, "tab"), _needed(given, "row"))
    if name == "update_row":
        return client.update(
            _needed(given, "tab"),
            _needed(given, "column"),
            _needed(given, "value"),
            _needed(given, "changes"),
        )
    raise ValueError(f"there is no tool called {name!r}")


def _needed(given: Dict, key: str):
    """One argument the tool cannot work without."""
    if key not in given or given[key] in (None, ""):
        raise ValueError(f"this needs a {key}")
    return given[key]
