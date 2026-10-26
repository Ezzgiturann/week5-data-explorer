# Week 5 Writeup — Data Explorer MCP Server

**MCP client:** Claude Desktop

## 1. Transcript: an agent calling both tools

Server registered in Claude Desktop (`claude_desktop_config.json` → `mcpServers.data-explorer`,
STDIO, venv Python). One chat, three questions; Claude made **5 tool calls**
(Desktop's MCP log shows five `CallToolRequest`s). Screenshots are in [`screenshots/`](screenshots/).

**User:** İçinde "united" geçen ülkeleri ara · Türkiye'nin para birimi, dilleri ve komşuları
neler? · nige ülkesinin detaylarını getir

**Call 1 — `search_countries`** · request: `query="united"` ([04](screenshots/04-search-countries-response-1.png), [05](screenshots/05-search-countries-response-2.png))

```json
[
  {"name": "United Arab Emirates", "capital": "Abu Dhabi", "region": "Asia", "subregion": "Western Asia"},
  {"name": "United Kingdom", "capital": "London", "region": "Europe", "subregion": "Northern Europe"},
  {"name": "Mexico", "capital": "Mexico City", "region": "Americas", "subregion": "North America"},
  {"name": "Tanzania", "capital": "Dodoma", "region": "Africa", "subregion": "Eastern Africa"},
  {"name": "United States Minor Outlying Islands", "capital": null, "region": "Americas", "subregion": "North America"},
  {"name": "United States", "capital": "Washington D.C.", "region": "Americas", "subregion": "North America"},
  {"name": "United States Virgin Islands", "capital": "Charlotte Amalie", "region": "Americas", "subregion": "Caribbean"}
]
```

Seven results, so Claude raised `limit` above the default of 5 on its own.

**Call 2 — `get_country_details`** · request: `name="Turkey"` ([06](screenshots/06-get-country-details-turkey.png))

```json
{
  "name": "Türkiye", "official_name": "Republic of Türkiye", "code": "TUR",
  "capital": "Ankara", "region": "Asia",
  "currencies": [{"code": "TRY", "name": "Turkish lira", "symbol": "₺"}],
  "languages": ["Turkish"],
  "borders": ["Armenia", "Azerbaijan", "Bulgaria", "Georgia", "Greece", "Iran", "Iraq", "Syria"],
  "flag_url": "https://raw.githubusercontent.com/mledoze/countries/master/data/tur.svg"
}
```

Claude sent "Turkey", not the dataset's common name "Türkiye"; it resolves via `altSpellings`.

**Calls 3–5 — `get_country_details`** ([03](screenshots/03-tool-calls-list.png), [02](screenshots/02-desktop-answer-turkey-nige.png))

The third call (for "nige") was ambiguous, so the tool returned an error with candidates
instead of guessing. The call's panel was not expanded, so this is the response the server
gives for that input:

```json
{"error": "'nige' matches several countries; pick one", "candidates": ["Niger", "Nigeria"]}
```

Claude's reasoning step ("Matching country names to their official full forms.") follows,
then two more `get_country_details` calls, one per candidate.

**Claude (final answer, abridged):** lists the seven "united" countries and notes that
Mexico and Tanzania match through their official names; gives Türkiye's currency (Turkish
lira, TRY, ₺), language (Turkish) and eight neighbours; for "nige": *"Bu arama iki ülkeyle
eşleşti. Hangisini kastettiğinizi bilmediğim için ikisini de getirdim"*, followed by a
Niger vs. Nigeria comparison table (capitals Niamey/Abuja, XOF/NGN, French/English).

## 2. How I handled errors

To make the integration resilient, the server was designed never to crash or bubble unhandled exceptions; instead, every failure is converted into an explicit, structured error response that the LLM can interpret. For input validation, the server catches empty inputs and bounds the limit parameter, fixing a bug in the starter code where limit=-1 silently returned misleading data. Network issues are segmented into actionable feedback—such as distinct messages for 10-second timeouts, HTTP 404/503 errors, and connection drops—while failed downloads are strictly excluded from the cache to allow immediate retries. Crucially, error payloads act as guides rather than dead ends by suggesting the next logical action (e.g., advising the agent to use search_countries first, or returning a candidates array when queries like "nige" are ambiguous). In our transcripts, Claude demonstrated this self-correction by parsing the returned candidate list to query "Niger" and "Nigeria" independently, and our search layer was expanded to include altSpellings so queries like "Turkey" resolve seamlessly to "Türkiye". We validated this behavior through a test suite of 29 automated test cases alongside live network tests simulating real-world 404 and timeout conditions.

## 3. What I learned about controlling what context an agent can reach

Controlling what context an agent can reach demonstrated that the developer, rather than the LLM, fundamentally defines the model's operational reality. By designing dedicated MCP tools instead of dumping the entire 250-country dataset into the prompt, I learned that selective exposure drastically minimizes token waste and keeps the model focused on task-relevant attributes. Furthermore, the format of our tool outputs directly shaped agent reasoning: structured feedback—such as actionable error messages and candidate suggestions for ambiguous queries like "nige"—steered the agent toward effective self-correction. Finally, handling edge cases like "Turkey" vs. "Türkiye" highlighted that tool boundaries must account for real-world user intent and messy external data rather than assuming strict schema matches.
