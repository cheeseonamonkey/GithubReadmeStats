# GitHub Stats Cards

SVG card generator for GitHub profiles.

## Endpoints

Visit `/api/` in a browser for a quick HTML reference of the available endpoints (the site root `/` redirects there).

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

Most frequent identifiers across multiple languages (Python, JS/TS, Java, Kotlin, C#, Go, C/C++, PHP, Ruby, Swift). Bars color-coded by dominant source language.

| Param | Default | Description |
|-------|---------|-------------|
| `username` | required | GitHub username |

```
![Identifiers](https://your-app.vercel.app/api/code_identifiers?username=cheeseonamonkey)
```

### `GET /api/code_identifiers/identifiers`

Alias endpoint that matches the primary identifiers card.

```
https://your-app.vercel.app/api/code_identifiers/identifiers?username=cheeseonamonkey
```

## Architecture

```
api/
├── github_base.py      # Base class: auth, HTTP, SVG frame rendering
├── language_stats.py   # Language bytes aggregation
├── code_identifiers/   # Identifier extraction (regex-based)
│   ├── card.py
│   ├── identifiers.py
│   ├── index.py
└── index.py            # Root HTML index
```

**Design**: Each card extends `GitHubCardBase`, implements `fetch_data()` and `render_body()`. Base handles auth headers, error cards, and SVG frame wrapping.

**Performance**: ThreadPoolExecutor for parallel repo fetching. `code_identifiers` uses compiled regex (not AST) for speed. Caps file count/size to stay within Vercel's 30s timeout.

## Rate Limits

Without `GITHUB_TOKEN`: 60 req/hr (by IP).  
With token: 5000 req/hr.

## License

MIT
