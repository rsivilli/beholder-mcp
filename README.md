# beholder-mcp

An MCP server for the [Beholder](https://beholder-gov.com/about) government contracting API, built with [FastMCP](https://github.com/jlowin/fastmcp) and Python.

Beholder aggregates and enriches data from [SAM.gov](https://sam.gov) and [USASpending.gov](https://usaspending.gov), providing higher rate limits and richer analysis than either public API — including risk indicators, contract vehicles, competition metrics, and subaward tracking.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- A Beholder API key — get one at [api.beholder-gov.com/docs](https://api.beholder-gov.com/docs)

## Setup

```bash
git clone https://github.com/rsivilli/beholder-mcp
cd beholder-mcp
```

Create a `.env` file and set your API key:

```env
BEHOLDER_API_KEY=your_api_key_here
```

## Running the server

**stdio** (for MCP clients that spawn the process, e.g. Claude Desktop):

```bash
uv run beholder-mcp
```

**HTTP** (for connecting remotely):

```bash
uv run beholder-mcp-http
```

## Claude Desktop configuration

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "beholder": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/beholder-mcp", "beholder-mcp"],
      "env": {
        "BEHOLDER_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## Available tools

### Contractors

| Tool | Description |
|---|---|
| `search_contractors` | Search contractors by name, UEI, state, or agency — returns paginated list with obligation totals and review priority scores |
| `get_contractor` | Get a contractor record by UEI or name — returns full profile with top agencies, PSC codes, vehicle summaries, and risk indicators |
| `resolve_contractor` | Resolve a company name or UEI to its Beholder UUID and key fields — returns the single best match |
| `get_contractor_profile` | Full contractor profile in one call: registration details, recent contracts, risk indicators, and contract vehicles |
| `find_competitors` | Find contractors competing in the same PSC code categories as a given company |

### Opportunities

| Tool | Description |
|---|---|
| `search_opportunities` | Search contract opportunities and award notices by keyword, NAICS code, set-aside, agency, active status, and date filters |

### Contracts & subawards

| Tool | Description |
|---|---|
| `search_contracts` | Search awarded contracts by PIID prefix, recipient, PSC code, fiscal year, obligation range, date range, status, and award type |
| `get_related_contracts` | Given a contract PIID, find related contracts — parent, siblings, same vehicle, or same awardee |
| `search_subawards` | Get subaward reports filed under a specific prime contract PIID |

## Development

Install dev dependencies and set up pre-commit hooks:

```bash
uv sync
uv run pre-commit install
```

Run linting and formatting checks:

```bash
uv run pre-commit run --all-files
```
