"""Data Explorer — MCP server skeleton for Week 5.

Wraps an open country dataset and exposes it to an agent as MCP tools over STDIO.
One tool is implemented as a worked example; finish the second (and improve error
handling) to complete the assignment.

Data source: the open `mledoze/countries` dataset (the data REST Countries was built
on), served as one JSON file from GitHub. No API key. It is fetched over HTTPS on the
first call and cached in memory, so HTTP errors and timeouts are still real failure
modes your tools must handle.

Setup:
    pip install -r requirements.txt
Run (STDIO) — register this command in your MCP client (e.g. Claude Desktop / an IDE):
    python server.py
"""
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

DATA_URL = "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"
# Each country has a 3-letter `cca3` code; its flag lives at this URL.
# The files are lowercase (deu.svg), so pass cca3.lower().
FLAG_URL = "https://raw.githubusercontent.com/mledoze/countries/master/data/{cca3}.svg"
TIMEOUT_SECONDS = 10
MAX_LIMIT = 50

mcp = FastMCP("data-explorer")

_countries: Optional[list[dict]] = None  # in-memory cache of the dataset


def load_countries() -> list[dict]:
    """Download the dataset once and cache it.

    Raises httpx.HTTPError on network/HTTP failure and ValueError on a body that
    is not a JSON list. A failed fetch is never cached, so the next call retries.
    """
    global _countries
    if _countries is None:
        resp = httpx.get(DATA_URL, timeout=TIMEOUT_SECONDS, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError("dataset is not a JSON list")
        _countries = data
    return _countries


def fetch_error() -> Optional[str]:
    """Load the dataset; return a model-readable error message, or None on success."""
    try:
        load_countries()
    except httpx.TimeoutException:
        return f"country data source timed out after {TIMEOUT_SECONDS}s; try again shortly"
    except httpx.HTTPStatusError as exc:
        return f"country data source returned HTTP {exc.response.status_code}; try again later"
    except httpx.HTTPError as exc:
        return f"could not reach country data source ({type(exc).__name__}); check the network"
    except ValueError:
        return "country data source returned malformed data"
    return None


@mcp.tool()
def search_countries(query: str, limit: int = 5) -> list[dict]:
    """Search countries by common or official name (case-insensitive substring).

    Returns up to `limit` (1-50) items shaped {name, capital, region, subregion}.
    On bad input or an upstream failure, returns [{"error": "..."}]; when nothing
    matches, returns [{"message": "..."}]. Use get_country_details for more fields.
    """
    if not query.strip():
        return [{"error": "query must not be empty"}]
    if not 1 <= limit <= MAX_LIMIT:
        return [{"error": f"limit must be between 1 and {MAX_LIMIT}, got {limit}"}]
    if error := fetch_error():
        return [{"error": error}]

    q = query.strip().lower()
    matches = [
        c for c in load_countries()
        if q in c["name"]["common"].lower() or q in c["name"]["official"].lower()
    ]
    if not matches:
        return [{"message": f"no countries matched {query.strip()!r}"}]
    results = []
    for c in matches[:limit]:
        results.append(
            {
                "name": c["name"]["common"],
                "capital": (c.get("capital") or [None])[0],
                "region": c.get("region"),
                "subregion": c.get("subregion"),
            }
        )
    return results


def country_names(c: dict) -> list[str]:
    """All lowercase names a country is known by: common, official, ISO codes, altSpellings.

    altSpellings covers names people actually type ("UK", "USA", "Republic of Turkey")
    that differ from the dataset's common name ("United Kingdom", "Türkiye").
    """
    names = [c["name"]["common"], c["name"]["official"], c.get("cca2", ""), c.get("cca3", "")]
    names += c.get("altSpellings") or []
    return [n.lower() for n in names if n]


def find_country(countries: list[dict], name: str) -> tuple[Optional[dict], list[str]]:
    """Resolve `name` to one country: exact name/code match first, then a unique substring.

    Returns (country, []) on success, or (None, candidate_names) when the name is
    unknown (no candidates) or ambiguous (several candidates).
    """
    q = name.strip().lower()
    for c in countries:
        if q in country_names(c):
            return c, []
    partial = [c for c in countries if any(q in n for n in country_names(c))]
    if len(partial) == 1:
        return partial[0], []
    return None, sorted(c["name"]["common"] for c in partial)


@mcp.tool()
def get_country_details(name: str) -> dict:
    """Get currencies, languages, neighbouring countries, and the flag URL for one country.

    `name` may be a common name ("Germany"), official name, or ISO code ("DE"/"DEU"),
    case-insensitive. Returns {name, official_name, code, capital, region, currencies:
    [{code, name, symbol}], languages: [str], borders: [country names], flag_url}.
    On failure returns {"error": "..."}; if the name is ambiguous the error also
    includes "candidates" — call again with one of them.
    """
    if not name.strip():
        return {"error": "name must not be empty"}
    if error := fetch_error():
        return {"error": error}

    countries = load_countries()
    country, candidates = find_country(countries, name)
    if country is None:
        if candidates:
            return {
                "error": f"{name.strip()!r} matches several countries; pick one",
                "candidates": candidates[:10],
            }
        return {"error": f"no country named {name.strip()!r}; try search_countries first"}

    names_by_code = {c["cca3"]: c["name"]["common"] for c in countries}
    return {
        "name": country["name"]["common"],
        "official_name": country["name"]["official"],
        "code": country["cca3"],
        "capital": (country.get("capital") or [None])[0],
        "region": country.get("region"),
        "currencies": [
            {"code": code, "name": cur.get("name"), "symbol": cur.get("symbol")}
            for code, cur in (country.get("currencies") or {}).items()
        ],
        "languages": list((country.get("languages") or {}).values()),
        "borders": [names_by_code.get(code, code) for code in country.get("borders") or []],
        "flag_url": FLAG_URL.format(cca3=country["cca3"].lower()),
    }


if __name__ == "__main__":
    mcp.run()
