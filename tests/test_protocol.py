"""The conversation an agent actually has with this server.

Nothing here opens a pipe or reaches a spreadsheet. The whole exchange
is driven line by line, which is the only way to prove the wire format
without a client.
"""

import io
import json

import mcp_protocol
import pytest
import tools
from mcp_protocol import METHOD_NOT_FOUND, PROTOCOL_VERSION, handle, serve


class FakeSheet:
    """A spreadsheet that remembers what it was asked to do."""

    def __init__(self):
        self.calls = []
        self.rows = [
            {"order": "4417", "customer": "Costa Verde", "paid": "no"},
            {"order": "5120", "customer": "Aurora Nordic", "paid": "no"},
        ]

    def tabs(self):
        self.calls.append(("tabs",))
        return ["orders", "questions"]

    def read(self, tab, limit=200):
        self.calls.append(("read", tab, limit))
        return {"columns": ["order", "customer", "paid"],
                "rows": self.rows[:limit], "total": len(self.rows)}

    def find(self, tab, column, value, exact=False):
        self.calls.append(("find", tab, column, value, exact))
        found = [r for r in self.rows if value.lower() in str(r[column]).lower()]
        return {"columns": ["order", "customer", "paid"],
                "rows": found, "total": len(found)}

    def append(self, tab, row):
        self.calls.append(("append", tab, row))
        self.rows.append(row)
        return {"at": len(self.rows) + 1, "written": 1}

    def update(self, tab, column, value, changes):
        self.calls.append(("update", tab, column, value, changes))
        return {"at": 2, "changed": list(changes)}


def talk(line, sheet=None):
    """One request in, the answer back as an object."""
    sheet = sheet or FakeSheet()
    return handle(
        json.dumps(line), tools.catalogue(),
        lambda name, given: tools.run(name, given, sheet),
    )


def call(name, arguments=None, sheet=None):
    """One tool call, and the text it answered with."""
    answer = talk({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }, sheet)
    return answer["result"]


def test_the_handshake_names_the_protocol():
    answer = talk({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    assert answer["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert answer["result"]["serverInfo"]["name"] == "sheets-mcp"


def test_the_handshake_offers_tools():
    answer = talk({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    assert "tools" in answer["result"]["capabilities"]


def test_every_tool_is_listed():
    answer = talk({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    listed = [t["name"] for t in answer["result"]["tools"]]

    assert listed == tools.names()


def test_every_tool_says_what_it_is_for():
    """A model picks a tool by its description, not its name."""
    for tool in tools.catalogue():
        assert len(tool["description"]) > 40
        assert "inputSchema" in tool


def test_a_notification_is_owed_no_answer():
    """A reply to something with no id makes a client complain."""
    assert talk({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_an_unknown_method_is_refused_by_name():
    answer = talk({"jsonrpc": "2.0", "id": 3, "method": "dance"})

    assert answer["error"]["code"] == METHOD_NOT_FOUND
    assert "dance" in answer["error"]["message"]


def test_rubbish_is_not_taken_for_a_request():
    assert handle("not json at all", [], None)["error"]


def test_listing_the_tabs_reaches_the_spreadsheet():
    sheet = FakeSheet()

    call("list_tabs", sheet=sheet)

    assert sheet.calls == [("tabs",)]


def test_reading_a_tab_comes_back_as_text():
    """Every client can show text, and the model reads it."""
    found = call("read_tab", {"tab": "orders"})

    assert found["content"][0]["type"] == "text"
    assert "Costa Verde" in found["content"][0]["text"]


def test_a_read_carries_its_limit():
    sheet = FakeSheet()

    call("read_tab", {"tab": "orders", "limit": 1}, sheet)

    assert sheet.calls == [("read", "orders", 1)]


def test_a_read_without_a_limit_gets_the_default():
    sheet = FakeSheet()

    call("read_tab", {"tab": "orders"}, sheet)

    assert sheet.calls[0][2] == tools.DEFAULT_LIMIT


def test_finding_rows_passes_the_match_on():
    sheet = FakeSheet()

    call("find_rows", {"tab": "orders", "column": "customer",
                       "value": "costa", "exact": True}, sheet)

    assert sheet.calls == [("find", "orders", "customer", "costa", True)]


def test_appending_a_row_reaches_the_spreadsheet():
    sheet = FakeSheet()
    row = {"order": "6001", "customer": "New Buyer", "paid": "no"}

    call("append_row", {"tab": "orders", "row": row}, sheet)

    assert sheet.calls == [("append", "orders", row)]


def test_updating_a_row_names_what_changed():
    sheet = FakeSheet()

    found = call("update_row", {
        "tab": "orders", "column": "order", "value": "4417",
        "changes": {"paid": "yes"},
    }, sheet)

    assert sheet.calls[0][4] == {"paid": "yes"}
    assert "paid" in found["content"][0]["text"]


def test_a_missing_argument_is_a_result_the_model_can_read():
    """An error the client swallows is one the model cannot recover from."""
    found = call("read_tab", {})

    assert found["isError"] is True
    assert "tab" in found["content"][0]["text"]


def test_a_tool_nobody_has_is_said_plainly():
    found = call("delete_everything", {})

    assert found["isError"] is True
    assert "delete_everything" in found["content"][0]["text"]


def test_a_spreadsheet_that_refuses_reaches_the_model():
    class Refusing(FakeSheet):
        def read(self, tab, limit=200):
            raise RuntimeError("no tab called orders")

    found = call("read_tab", {"tab": "orders"}, Refusing())

    assert found["isError"] is True
    assert "no tab called orders" in found["content"][0]["text"]


def test_a_whole_conversation_runs_line_by_line():
    sheet = FakeSheet()
    asked = "\n".join(json.dumps(one) for one in [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "list_tabs"}},
    ])
    said = io.StringIO()

    serve(tools.catalogue(),
          lambda name, given: tools.run(name, given, sheet),
          reader=io.StringIO(asked), writer=said)
    answers = [json.loads(line) for line in said.getvalue().splitlines()]

    assert [a["id"] for a in answers] == [1, 2, 3]


def test_a_blank_line_is_ignored():
    said = io.StringIO()

    serve([], lambda n, g: {}, reader=io.StringIO("\n\n"), writer=said)

    assert said.getvalue() == ""
