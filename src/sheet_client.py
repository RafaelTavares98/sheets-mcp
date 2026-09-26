"""Talking to the spreadsheet.

One address, one shared word, one action per call. The spreadsheet's own
half is an Apps Script living inside it, so nothing here needs a Google
Cloud project, a consent screen or a key to rotate.

The address and the word come from the operating system keychain. An
environment variable would sit in plain text in the registry and in the
shell history, where anything running as that user can read it.
"""

import json
import urllib.error
import urllib.request
from typing import Dict, List

KEYCHAIN_SERVICE = "sheets-mcp"
ADDRESS = "web-app-url"
WORD = "shared-word"

#: A spreadsheet that takes longer than this is not going to answer.
PATIENCE = 60


class SheetRefused(RuntimeError):
    """The spreadsheet could not be reached, or would not do it."""


def tabs() -> List[str]:
    """The names of the tabs in the spreadsheet."""
    return ask({"action": "tabs"})["tabs"]


def read(tab: str, limit: int = 200) -> Dict:
    """Every row of one tab, newest last, up to a limit."""
    return ask({"action": "read", "tab": tab, "limit": limit})


def find(tab: str, column: str, value: str, exact: bool = False) -> Dict:
    """The rows whose column holds this value."""
    return ask({
        "action": "find", "tab": tab, "column": column,
        "value": value, "exact": exact,
    })


def append(tab: str, row: Dict) -> Dict:
    """Add one row at the bottom."""
    return ask({"action": "append", "tab": tab, "row": row})


def update(tab: str, column: str, value: str, changes: Dict) -> Dict:
    """Change cells of the one row where `column` holds `value`."""
    return ask({
        "action": "update", "tab": tab, "column": column,
        "value": value, "changes": changes,
    })


def remember(address: str, word: str) -> None:
    """Keep the address and the shared word for later runs."""
    import keyring

    keyring.set_password(KEYCHAIN_SERVICE, ADDRESS, address)
    keyring.set_password(KEYCHAIN_SERVICE, WORD, word)


def is_connected() -> bool:
    """Whether a spreadsheet has been connected on this machine."""
    import keyring

    return bool(keyring.get_password(KEYCHAIN_SERVICE, ADDRESS))


def ask(body: Dict) -> Dict:
    """Send one action and return what the spreadsheet said.

    A refusal from the spreadsheet is raised here rather than passed on
    as a result, so no caller can mistake "it would not" for "there was
    nothing".
    """
    address, word = _account()
    payload = json.dumps({**body, "word": word}).encode()
    request = urllib.request.Request(
        address, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=PATIENCE) as answer:
            said = json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        raise SheetRefused(
            f"the spreadsheet turned the request down ({refused.code})"
        )
    except urllib.error.URLError:
        raise SheetRefused("I could not reach the spreadsheet")
    except json.JSONDecodeError:
        raise SheetRefused("the spreadsheet answered with something odd")
    if not said.get("ok"):
        raise SheetRefused(said.get("why", "the spreadsheet said no"))
    return said


def _account():
    """The address and the shared word, or how to set them."""
    import keyring

    address = keyring.get_password(KEYCHAIN_SERVICE, ADDRESS)
    word = keyring.get_password(KEYCHAIN_SERVICE, WORD)
    if not address or not word:
        raise SheetRefused(
            "No spreadsheet connected. Deploy sheet/Codigo.gs from the "
            "spreadsheet, then run: python server.py connect <url> <word>"
        )
    return address, word
