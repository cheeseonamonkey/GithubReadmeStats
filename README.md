# GitHub Stats Cards

SVG card generator for GitHub profiles. Deploy to Vercel, embed anywhere.

## Endpoints

### `GET /api/language_stats`

Top languages by bytes across user's non-fork repos.

| Param | Default | Description |
|-------|---------|-------------|
| `username` | required | GitHub username |
| `mode` | `percent` | `percent`, `bytes`, or `both` |
| `width` | `350` | Card width in pixels |

```
![Languages](https://your-app.vercel.app/api/language_stats?username=cheeseonamonkey&mode=both)
```

### `GET /api/code_identifiers`

Most frequent identifiers (class/variable names) from source files. Bars color-coded by dominant source language.

| Param | Default | Description |
|-------|---------|-------------|
| `username` | required | GitHub username |
| `extract` | `classes,variables` | What to extract (any comma-separated mix of `classes` and `variables`) |

```
![Identifiers](https://your-app.vercel.app/api/code_identifiers?username=cheeseonamonkey)
```

Example (classes only):

```
https://your-app.vercel.app/api/code_identifiers?username=cheeseonamonkey&extract=classes
```

## Architecture

```
api/
├── github_base.py      # Base class: auth, HTTP, SVG frame rendering
├── language_stats.py   # Language bytes aggregation
├── code_identifiers.py # Identifier extraction (regex-based)
└── index.py            # Root HTML index
```

**Design**: Each card extends `GitHubCardBase`, implements `fetch_data()` and `render_body()`. Base handles auth headers, error cards, and SVG frame wrapping.

**Performance**: ThreadPoolExecutor for parallel repo fetching. `code_identifiers` uses compiled regex (not AST) for speed. Caps file count/size to stay within Vercel's 30s timeout.

## Rate Limits

Without `GITHUB_TOKEN`: 60 req/hr (by IP).  
With token: 5000 req/hr.

## License

MIT
