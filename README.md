# Data Explorer — MCP Server

A `FastMCP` server that lets an agent explore the open, no-key
**[mledoze/countries](https://github.com/mledoze/countries)** dataset (the data REST Countries
was built on). It speaks MCP over **STDIO** and exposes two tools: `search_countries` and
`get_country_details`.

The dataset is downloaded from GitHub on the first tool call and cached in memory. A failed
download is never cached, so the next call retries.

## Install

Requires **Python 3.10+** (the `mcp` package does not support 3.9).

```bash
python3.12 -m venv .venv          # or: uv venv --python 3.12 .venv
.venv/bin/pip install -r requirements.txt
```

## Run (STDIO)

```bash
.venv/bin/python server.py
```

It prints nothing and waits for a client on stdin/stdout; that is normal. Stop it with `Ctrl+C`.
Never add `print()` to the server: stdout is the MCP channel, and stray output breaks the protocol.

## Register in Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) and add
`mcpServers` with **absolute** paths to the venv's Python and to `server.py`:

```json
{
  "mcpServers": {
    "data-explorer": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

Fully quit Claude Desktop (`Cmd+Q`) and reopen it. The tools appear under the
search-and-tools menu in a new chat. Using the venv's Python matters: a bare `python`
may resolve to an interpreter without `mcp` installed.

Other clients take the same command, e.g. Claude Code:
`claude mcp add data-explorer -- /absolute/path/to/.venv/bin/python /absolute/path/to/server.py`

## Test

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest      # offline: the dataset and HTTP failures are faked
```

## Tool reference

### `search_countries(query: str, limit: int = 5) -> list[dict]`

Case-insensitive substring search over common and official names.

| Parameter | Type | Rules |
|-----------|------|-------|
| `query` | string | Required, not blank |
| `limit` | int | 1–50, default 5 |

Example: `search_countries(query="united", limit=3)`

```json
[
  {"name": "United Arab Emirates", "capital": "Abu Dhabi", "region": "Asia", "subregion": "Western Asia"},
  {"name": "United Kingdom", "capital": "London", "region": "Europe", "subregion": "Northern Europe"},
  {"name": "Mexico", "capital": "Mexico City", "region": "Americas", "subregion": "North America"}
]
```

(Mexico matches because its official name is "United Mexican States".)

### `get_country_details(name: str) -> dict`

Currencies, languages, neighbours, and flag for one country. `name` may be a common name,
official name, alternative spelling ("UK", "USA", "Turkey"), or ISO code ("DE", "DEU"),
case-insensitive. An exact match wins; otherwise a substring that matches exactly one country.

Example: `get_country_details(name="turkey")`

```json
{
  "name": "Türkiye",
  "official_name": "Republic of Türkiye",
  "code": "TUR",
  "capital": "Ankara",
  "region": "Asia",
  "currencies": [{"code": "TRY", "name": "Turkish lira", "symbol": "₺"}],
  "languages": ["Turkish"],
  "borders": ["Armenia", "Azerbaijan", "Bulgaria", "Georgia", "Greece", "Iran", "Iraq", "Syria"],
  "flag_url": "https://raw.githubusercontent.com/mledoze/countries/master/data/tur.svg"
}
```

### Errors

Tools never raise. Problems come back as data the model can read and act on:

| Situation | `search_countries` | `get_country_details` |
|-----------|--------------------|-----------------------|
| Blank input | `[{"error": "query must not be empty"}]` | `{"error": "name must not be empty"}` |
| `limit` out of range | `[{"error": "limit must be between 1 and 50, got -1"}]` | — |
| No match | `[{"message": "no countries matched 'atlantis'"}]` | `{"error": "no country named 'atlantis'; try search_countries first"}` |
| Ambiguous name | — | `{"error": "'nige' matches several countries; pick one", "candidates": ["Niger", "Nigeria"]}` |
| Timeout | `[{"error": "country data source timed out after 10s; try again shortly"}]` | same message as `{"error": ...}` |
| HTTP error | `[{"error": "country data source returned HTTP 503; try again later"}]` | same message as `{"error": ...}` |
| Network down | `[{"error": "could not reach country data source (ConnectError); check the network"}]` | same message as `{"error": ...}` |
| Malformed data | `[{"error": "country data source returned malformed data"}]` | same message as `{"error": ...}` |
