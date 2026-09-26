"""Speaking the protocol an agent expects.

MCP is JSON-RPC over the program's own input and output. One JSON object
per line in, one per line out. That is the whole wire format, so it is
written out here rather than pulled in as a dependency: a server that
installs nothing is a server a client can run without being asked to
trust a package.

Nothing in this module knows what a spreadsheet is. It is handed a list
of tools and a way to run one.
"""

import json
import sys
import traceback
from typing import Callable, Dict, List

PROTOCOL_VERSION = "2024-11-05"

SERVER_NAME = "sheets-mcp"
SERVER_VERSION = "1.0.0"

#: JSON-RPC says what these mean. They are named so a reader does not
#: have to look them up.
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def serve(catalogue: List[Dict], run: Callable, reader=None, writer=None):
    """Answer requests until the input ends.

    `reader` and `writer` are passed in so a test can drive the whole
    conversation without a pipe.
    """
    reader = reader or sys.stdin
    writer = writer or sys.stdout
    for line in reader:
        line = line.strip()
        if not line:
            continue
        answer = handle(line, catalogue, run)
        if answer is None:
            continue
        writer.write(json.dumps(answer) + "\n")
        writer.flush()


def handle(line: str, catalogue: List[Dict], run: Callable):
    """One request in, one answer out, or None when none is owed.

    A notification carries no id and is owed no answer. Sending one
    anyway makes a client complain about a reply to nothing.
    """
    try:
        asked = json.loads(line)
    except json.JSONDecodeError:
        return _failure(None, INVALID_PARAMS, "that was not JSON")
    identifier = asked.get("id")
    method = asked.get("method", "")
    if identifier is None:
        return None
    try:
        return _answer(identifier, method, asked.get("params") or {},
                       catalogue, run)
    except ValueError as wrong:
        return _tool_failure(identifier, str(wrong))
    except Exception as failure:
        return _tool_failure(identifier, _plain(failure))


def _answer(identifier, method, params, catalogue, run):
    """What one method returns."""
    if method == "initialize":
        return _result(identifier, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": SERVER_NAME, "version": SERVER_VERSION
            },
        })
    if method == "tools/list":
        return _result(identifier, {"tools": catalogue})
    if method == "tools/call":
        found = run(params.get("name"), params.get("arguments") or {})
        return _result(identifier, _as_content(found))
    if method == "ping":
        return _result(identifier, {})
    return _failure(identifier, METHOD_NOT_FOUND, f"no method {method!r}")


def _as_content(found):
    """What a tool found, in the shape a client reads.

    The result goes back as text, because that is what every client can
    show and what the model actually reads.
    """
    return {
        "content": [
            {"type": "text", "text": json.dumps(found, indent=2,
                                                default=str)}
        ]
    }


def _tool_failure(identifier, why: str):
    """A tool that would not run.

    This is a result, not a protocol error. The model is meant to read
    it, think again and try something else, which it cannot do with an
    error the client swallows.
    """
    return _result(identifier, {
        "content": [{"type": "text", "text": why}],
        "isError": True,
    })


def _result(identifier, body):
    return {"jsonrpc": "2.0", "id": identifier, "result": body}


def _failure(identifier, code, message):
    return {
        "jsonrpc": "2.0", "id": identifier,
        "error": {"code": code, "message": message},
    }


def _plain(failure: Exception) -> str:
    """A failure as one sentence, with the stack kept off the wire."""
    return f"{failure}" or failure.__class__.__name__
