"""Offline tests for the Data Explorer tools.

The dataset is replaced with a tiny fixture and httpx.get is patched, so these
tests never touch the network and can simulate HTTP errors and timeouts.
"""
import httpx
import pytest

import server

FAKE_COUNTRIES = [
    {
        "name": {"common": "Germany", "official": "Federal Republic of Germany"},
        "altSpellings": ["DE", "Deutschland"],
        "cca2": "DE",
        "cca3": "DEU",
        "capital": ["Berlin"],
        "region": "Europe",
        "subregion": "Western Europe",
        "currencies": {"EUR": {"name": "Euro", "symbol": "€"}},
        "languages": {"deu": "German"},
        "borders": ["AUT"],
    },
    {
        "name": {"common": "Austria", "official": "Republic of Austria"},
        "cca2": "AT",
        "cca3": "AUT",
        "capital": ["Vienna"],
        "region": "Europe",
        "subregion": "Central Europe",
        "currencies": {"EUR": {"name": "Euro", "symbol": "€"}},
        "languages": {"bar": "Austro-Bavarian German", "deu": "German"},
        "borders": ["DEU"],
    },
    {
        "name": {"common": "Niger", "official": "Republic of Niger"},
        "cca2": "NE",
        "cca3": "NER",
        "capital": ["Niamey"],
        "region": "Africa",
        "subregion": "Western Africa",
        "currencies": {"XOF": {"name": "West African CFA franc", "symbol": "Fr"}},
        "languages": {"fra": "French"},
        "borders": ["NGA"],
    },
    {
        "name": {"common": "Nigeria", "official": "Federal Republic of Nigeria"},
        "cca2": "NG",
        "cca3": "NGA",
        "capital": ["Abuja"],
        "region": "Africa",
        "subregion": "Western Africa",
        "currencies": {"NGN": {"name": "Nigerian naira", "symbol": "₦"}},
        "languages": {"eng": "English"},
        "borders": ["NER"],
    },
    {
        "name": {"common": "Antarctica", "official": "Antarctica"},
        "cca2": "AQ",
        "cca3": "ATA",
        "capital": [],
        "region": "Antarctic",
        "subregion": "",
        "currencies": {},
        "languages": {},
        "borders": [],
    },
]


@pytest.fixture(autouse=True)
def fake_dataset(monkeypatch):
    """Serve FAKE_COUNTRIES and reset the in-memory cache for every test."""
    monkeypatch.setattr(server, "_countries", None)

    def fake_get(url, **kwargs):
        return httpx.Response(200, json=FAKE_COUNTRIES, request=httpx.Request("GET", url))

    monkeypatch.setattr(server.httpx, "get", fake_get)


def fail_with(monkeypatch, exc):
    def raising_get(url, **kwargs):
        raise exc

    monkeypatch.setattr(server.httpx, "get", raising_get)


def respond_with(monkeypatch, status, **kwargs):
    def get(url, **_):
        return httpx.Response(status, request=httpx.Request("GET", url), **kwargs)

    monkeypatch.setattr(server.httpx, "get", get)


# --- search_countries -------------------------------------------------------


def test_search_returns_matches():
    result = server.search_countries("germ")
    assert result == [
        {"name": "Germany", "capital": "Berlin", "region": "Europe", "subregion": "Western Europe"}
    ]


@pytest.mark.parametrize("query", ["", "   "])
def test_search_rejects_empty_query(query):
    assert "error" in server.search_countries(query)[0]


@pytest.mark.parametrize("limit", [0, -1, 51])
def test_search_rejects_out_of_range_limit(limit):
    assert "error" in server.search_countries("a", limit)[0]


def test_search_no_match_returns_message():
    result = server.search_countries("atlantis")
    assert len(result) == 1
    assert "atlantis" in result[0]["message"]


def test_search_timeout_returns_error(monkeypatch):
    fail_with(monkeypatch, httpx.ConnectTimeout("timed out"))
    assert "timed out" in server.search_countries("germ")[0]["error"]


# --- get_country_details ----------------------------------------------------


def test_details_returns_full_shape():
    assert server.get_country_details("Germany") == {
        "name": "Germany",
        "official_name": "Federal Republic of Germany",
        "code": "DEU",
        "capital": "Berlin",
        "region": "Europe",
        "currencies": [{"code": "EUR", "name": "Euro", "symbol": "€"}],
        "languages": ["German"],
        "borders": ["Austria"],
        "flag_url": "https://raw.githubusercontent.com/mledoze/countries/master/data/deu.svg",
    }


@pytest.mark.parametrize("name", ["germany", "  GERMANY ", "Federal Republic of Germany", "DE", "deu"])
def test_details_matches_names_and_codes_case_insensitively(name):
    assert server.get_country_details(name)["code"] == "DEU"


def test_details_prefers_exact_match_over_substring():
    assert server.get_country_details("Niger")["code"] == "NER"


def test_details_matches_alt_spelling():
    assert server.get_country_details("deutschland")["code"] == "DEU"


def test_details_unique_partial_match():
    assert server.get_country_details("austr")["code"] == "AUT"


def test_details_ambiguous_partial_match_lists_candidates():
    result = server.get_country_details("nige")
    assert "error" in result
    assert result["candidates"] == ["Niger", "Nigeria"]


def test_details_handles_empty_fields():
    result = server.get_country_details("Antarctica")
    assert result["capital"] is None
    assert result["currencies"] == []
    assert result["languages"] == []
    assert result["borders"] == []


@pytest.mark.parametrize("name", ["", "   "])
def test_details_rejects_empty_name(name):
    assert "error" in server.get_country_details(name)


def test_details_unknown_country():
    assert "atlantis" in server.get_country_details("Atlantis")["error"].lower()


# --- upstream failures (both tools) -----------------------------------------


@pytest.mark.parametrize("tool", [server.search_countries, server.get_country_details])
def test_http_status_error_is_reported(monkeypatch, tool):
    respond_with(monkeypatch, 503)
    result = tool("germany")
    error = (result[0] if isinstance(result, list) else result)["error"]
    assert "503" in error


@pytest.mark.parametrize("tool", [server.search_countries, server.get_country_details])
def test_network_error_is_reported(monkeypatch, tool):
    fail_with(monkeypatch, httpx.ConnectError("no route to host"))
    result = tool("germany")
    assert "error" in (result[0] if isinstance(result, list) else result)


@pytest.mark.parametrize("tool", [server.search_countries, server.get_country_details])
def test_invalid_json_is_reported(monkeypatch, tool):
    respond_with(monkeypatch, 200, text="<html>not json</html>")
    result = tool("germany")
    assert "error" in (result[0] if isinstance(result, list) else result)


def test_failed_fetch_is_not_cached(monkeypatch):
    fail_with(monkeypatch, httpx.ConnectTimeout("timed out"))
    assert "error" in server.get_country_details("Germany")
    monkeypatch.setattr(
        server.httpx,
        "get",
        lambda url, **kw: httpx.Response(200, json=FAKE_COUNTRIES, request=httpx.Request("GET", url)),
    )
    assert server.get_country_details("Germany")["code"] == "DEU"
