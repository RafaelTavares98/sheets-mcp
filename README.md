# A Google Sheet your AI can actually use

Claude and ChatGPT cannot touch your spreadsheet. They read what you
paste into the chat and nothing else. This is a small program that hands
them five things they can do to it, so you can say

> how much did Costa Verde order this month?

and get an answer off the real sheet, then say

> mark order 4417 as paid

and watch the cell change.

## What it gives the agent

| Tool | What it does |
| --- | --- |
| `list_tabs` | The names of the tabs, for when the agent does not know where to look |
| `read_tab` | Every row of one tab, keyed by the header |
| `find_rows` | The rows whose named column holds a value |
| `append_row` | One new row at the bottom |
| `update_row` | Change cells of the one row a column identifies |

`update_row` refuses when more than one row matches. Changing several
rows on a loose match is how a spreadsheet gets quietly ruined.

## No Google Cloud project

The spreadsheet's half is a script that lives inside the spreadsheet
itself. There is no Cloud console, no consent screen for the client, and
no key file to lose.

1. Make or open a spreadsheet.
2. Extensions → Apps Script. Paste `sheet/Codigo.gs`. Set `SHEET_ID` to
   the long code in the sheet's address, and `SHARED_WORD` to something
   only you know.
3. Deploy → New deployment → Web app, running as yourself, access
   "Anyone with the link". Copy the URL.

```bash
pip install -r requirements.txt
python server.py connect "<the url>" "<your word>"
python server.py check
```

`check` prints the tabs and their columns, so a setup that is wrong says
so before an agent ever sees it.

## Point Claude Desktop at it

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sheets": {
      "command": "python",
      "args": ["C:/path/to/sheets-mcp/server.py", "serve"]
    }
  }
}
```

Restart the app, and the five tools appear.

## What was measured

Driven exactly as an agent drives it, against a real spreadsheet:

| | |
| --- | --- |
| Handshake and tool list | correct |
| Tabs listed | rows, questions |
| Rows found by customer | correct |
| Row appended | written at row 8 |
| Cell changed on that row | correct |
| A tab that does not exist | "no tab called nope" |

The last line is the point. A tool that fails has to say so in words the
model can read and act on, not with an error the client swallows.

## Decisions worth knowing

**No dependency for the protocol.** MCP is JSON-RPC over the program's
own input and output: one object per line in, one per line out. That is
written out here rather than pulled in, so a client can run this without
being asked to trust a package.

**A tool failure is a result, not a protocol error.** The model is meant
to read it, think again and try something else, which it cannot do with
an error the client swallows.

**Descriptions are written for the model.** It picks a tool by reading
what the tool is for. A description that only makes sense to the person
who wrote it is a tool the model will misuse.

**A read has a limit.** A model handed ten thousand rows spends the
client's money on tokens and answers no better than with two hundred.

**The address and the word live in the operating system keychain.** An
environment variable would sit in plain text in the registry and in the
shell history.

**The spreadsheet never returns a half answer.** A refusal is raised, so
no caller can mistake "it would not" for "there was nothing".

## Tests

```bash
python -m pytest
```

19 tests, none of which touch a spreadsheet or open a pipe. The whole
conversation is driven line by line, which is the only way to prove the
wire format without a client.

## Layout of the code

```
server.py             the command line
src/
  mcp_protocol.py     the wire format, and nothing about spreadsheets
  tools.py            the five tools and what they are for
  sheet_client.py     talking to the spreadsheet
sheet/Codigo.gs       the spreadsheet's own half
tests/
```
