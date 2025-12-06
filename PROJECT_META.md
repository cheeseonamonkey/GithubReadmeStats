# Project Metadata

## Identity
| Key | Value |
|-----|-------|
| name | GithubReadmeStats |
| version | unversioned |
| language | Python |
| runtime | Python (unspecified) |
| manifest | requirements.txt |
| entry | index.py |

## Repository
| Key | Value |
|-----|-------|
| remote | https://github.com/cheeseonamonkey/GithubReadmeStats |
| branch | main |
| last_commit | 09e00bc8c2a6c5c8abb6cbdcb07b5fe80ab2e9c0 |
| last_updated | 2025-12-06 00:37:10 +0000 |
| total_commits | 74 |
| latest_tag | none |

## Structure
| Directory | Exists | Purpose |
|-----------|--------|---------|
| api/ | ✓ | main source code |
| github_cards/ | ✓ | shared card logic used by api endpoints |
| tests/ | ✓ | test suite |
| .claude/ | ✓ | claude code commands & settings |
| docs/ | ✗ | documentation |
| config/ | ✗ | configuration |
| .github/ | ✗ | CI/CD workflows |

## Stats
| Metric | Value |
|--------|-------|
| total_files | 15 (git-tracked) |
| total_loc | 1,972 |
| total_directories | 10 |

## Files by Type
| Extension | Count |
|-----------|-------|
| .py | 12 |
| .txt | 1 |
| .md | 1 |
| .json | 1 |

## File Tree
```
.
├── api/
│   ├── code_identifiers/
│   │   ├── identifiers.py
│   │   ├── index.py
│   ├── index.py
│   └── language_stats.py
├── github_cards/
│   ├── code_identifiers/
│   │   ├── extraction/
│   │   │   ├── ast_extractors.py
│   │   │   ├── base.py
│   │   │   └── __init__.py
│   │   ├── filtering/
│   │   │   ├── deduplicator.py
│   │   │   ├── __init__.py
│   │   │   ├── normalizer.py
│   │   │   ├── quality_scorer.py
│   │   │   └── stopwords.py
│   │   ├── card.py
│   │   ├── extractor.py
│   │   ├── languages.py
│   │   └── __init__.py
│   ├── github_base.py
│   └── __init__.py
├── tests/
│   ├── test_code_identifiers.py
│   └── test_integration_identifiers.py
├── .claude/
│   └── commands/
│       ├── cleanproject.md
│       ├── meta.md
│       ├── predictissues.md
│       ├── prime.md
│       └── understand.md
├── index.py
├── README.md
├── requirements.txt
└── vercel.json
```

## Key Insights

**Project Type**: GitHub SVG card generator (Vercel serverless)

**Purpose**: Generates on-demand SVG cards showing:
- Language statistics from user's GitHub repos
- Most frequent code identifiers across multiple languages

**Architecture**:
- Base class pattern (`GitHubCardBase`) for card implementations
- Parallel repo fetching using ThreadPoolExecutor
- Regex-based identifier extraction (not AST-based for performance)
- Vercel deployment with 30s timeout constraint

**Dependencies**: Minimal (Pygments >= 2.17.0)

**Test Coverage**: Unit and integration tests present
