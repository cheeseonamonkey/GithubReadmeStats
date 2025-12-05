# code_identifiers/card.py

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from typing import Counter as CounterType
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler
import urllib.request

from ..github_base import GitHubCardBase, HEADERS, escape_xml
from .extractor import IdentifierExtractor
from .languages import EXTENSION_TO_LANG, LANGUAGE_COLORS, LANGUAGE_NAMES


@dataclass(frozen=True)
class FetchResult:
    identifiers: list["IdentifierMatch"]
    files_scanned: int
    language_counts: CounterType[str]


@dataclass(frozen=True)
class IdentifierMatch:
    normalized: str
    display: str
    lang: str


@lru_cache(maxsize=256)
def _cached_fetch_file(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


class CodeIdentifiersCard(GitHubCardBase):
    MAX_WORKERS = 8

    def __init__(self, username: str, query_params: dict, width: int = 400, header_height: int = 40):
        super().__init__(username, query_params)
        self.card_width = width
        self.header_height = header_height
        self.padding = 16
        self.file_timeout = 3
        self.extractor = IdentifierExtractor()
        self.filters = self._parse_filters(query_params)

    @staticmethod
    def _parse_filters(query_params: dict) -> list[str]:
        filters: list[str] = []
        for raw in query_params.get("filter", []):
            for term in raw.split(","):
                cleaned = term.strip().lstrip("@")
                if cleaned:
                    filters.append(cleaned.casefold())
        return filters

    def _extract(self, code: str, lang_key: str):
        return self.extractor.extract(code, lang_key)

    def _should_skip(self, path: str) -> bool:
        return self.extractor.should_skip(path)

    def _fetch_file(self, repo: str, path: str, ext: str):
        url = f"https://raw.githubusercontent.com/{self.user}/{repo}/HEAD/{path}"
        content = _cached_fetch_file(url, self.file_timeout)
        return EXTENSION_TO_LANG[ext], content

    def _should_include(self, match: IdentifierMatch) -> bool:
        if not self.filters:
            return True

        normalized = match.normalized.casefold()
        display = match.display.casefold()
        return not any(f in normalized or f in display for f in self.filters)

    def _fetch_repo(self, repo: str) -> FetchResult:
        results: list[IdentifierMatch] = []
        files_scanned, lang_counts = 0, CounterType()
        try:
            tree = self._make_request(
                f"https://api.github.com/repos/{self.user}/{repo}/git/trees/HEAD?recursive=1"
            )
            files = [
                (f["path"], ext)
                for f in tree.get("tree", [])
                if f.get("type") == "blob"
                and f.get("size", 0) < 100000
                and not self._should_skip(f.get("path", ""))
                for ext in [next((e for e in EXTENSION_TO_LANG if f["path"].endswith(e)), None)]
                if ext
            ]
            if not files:
                return FetchResult(results, files_scanned, lang_counts)

            with ThreadPoolExecutor(max_workers=min(6, len(files))) as file_ex:
                futures = {file_ex.submit(self._fetch_file, repo, path, ext): ext for path, ext in files}
                for future in as_completed(futures):
                    try:
                        lang_key, content = future.result()
                    except Exception:
                        continue
                    files_scanned += 1
                    lang_counts[lang_key] += 1
                    for name in self._extract(content, lang_key):
                        normalized = self.extractor.normalize_identifier(name)
                        candidate = IdentifierMatch(normalized, name, lang_key)
                        if self._should_include(candidate):
                            results.append(candidate)
        except Exception:
            pass
        return FetchResult(results, files_scanned, lang_counts)

    def fetch_data(self):
        repos = self._fetch_all_repos()
        repo_names = [r["name"] for r in repos if not r.get("fork")]

        id_langs: dict[str, CounterType[str]] = {}
        display_names: dict[str, str] = {}
        lang_file_counts: CounterType[str] = CounterType()
        total_files = 0

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as ex:
            for future in as_completed([ex.submit(self._fetch_repo, r) for r in repo_names]):
                result = future.result()
                total_files += result.files_scanned
                lang_file_counts.update(result.language_counts)
                for match in result.identifiers:
                    id_langs.setdefault(match.normalized, CounterType())[match.lang] += 1
                    display_names.setdefault(match.normalized, match.display)

        limit = 15
        try:
            limit = max(1, min(50, int(self.params.get("count", [limit])[0])))
        except (TypeError, ValueError):
            pass

        scored = [
            {
                "name": display_names.get(n, n),
                "count": sum(lc.values()),
                "langs": lc,
            }
            for n, lc in id_langs.items()
        ]
        scored.sort(key=lambda x: x["count"], reverse=True)
        return {
            "items": scored[:limit],
            "language_files": lang_file_counts,
            "repo_count": len(repo_names),
            "file_count": total_files,
        }

    def _fetch_all_repos(self):
        page, repos = 1, []
        while True:
            batch = self._make_request(
                f"https://api.github.com/users/{self.user}/repos?per_page=100&type=owner&sort=updated&page={page}"
            )
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    def process(self):
        if not self.user:
            return self._render_error("Missing ?username= parameter")
        try:
            data = self.fetch_data()
            body, height = self.render_body(data)
            return self._render_frame(f"{self.user}'s Top Identifiers", body, height)
        except Exception:
            import traceback
            return self._render_error(traceback.format_exc())

    def render_body(self, stats):
        items = stats.get("items", [])
        language_counts = stats.get("language_files", CounterType())
        repo_count = stats.get("repo_count", 0)
        file_count = stats.get("file_count", 0)

        bar_h, row_h, bar_w = 10, 16, 200
        svg = []

        if not items:
            svg.append(f'<text x="{self.padding}" y="20" class="stat-value">No identifiers found.</text>')
            body_height = 40
        else:
            max_count = max(s["count"] for s in items)
            for i, item in enumerate(items):
                y = 8 + i * row_h
                lang_counts = item.get("langs") or CounterType({item.get("lang", "other"): item["count"]})
                total_lang = sum(lang_counts.values()) or 1
                scaled_width = max((item["count"] / max_count) * bar_w, 2)
                tooltip = ", ".join(
                    f"{escape_xml(LANGUAGE_NAMES.get(lang, lang))}: {count}"
                    for lang, count in lang_counts.most_common()
                )

                segments = []
                x_offset = 110.0
                for lang_key, lang_count in lang_counts.most_common():
                    seg_w = max((lang_count / total_lang) * scaled_width, 2)
                    color = LANGUAGE_COLORS.get(lang_key, "#58a6ff")
                    segments.append(
                        f'<rect x="{x_offset:.2f}" y="0" width="{seg_w:.2f}" height="{bar_h}" fill="{color}" />'
                    )
                    x_offset += seg_w

                svg.append(
                    f"""
                    <g transform=\"translate({self.padding},{y})\">\n                        <text x=\"0\" y=\"{bar_h-2}\" class=\"stat-name\">{escape_xml(item['name'])}</text>\n                        <rect x=\"110\" y=\"0\" width=\"{bar_w}\" height=\"{bar_h}\" fill=\"#21262d\"/>\n                        {''.join(segments)}\n                        <text x=\"{110+bar_w+10}\" y=\"{bar_h-2}\" class=\"stat-value\">{item['count']}</text>\n                        <title>{tooltip}</title>\n                    </g>"""
                )
            body_height = len(items) * row_h + 8

        legend_svg, legend_height = self._render_legend(language_counts, y_offset=body_height + 10)
        svg.append(legend_svg)

        meta_y = body_height + legend_height + 25
        svg.append(f'<text x="{self.padding}" y="{meta_y}" class="stat-value">{repo_count} repos • {file_count} files scanned</text>')
        return "\n".join(svg), meta_y + 10

    def _render_legend(self, language_counts: CounterType[str], y_offset: int):
        if not language_counts:
            return "", 0
        items = language_counts.most_common()
        col_width, items_per_row = 130, max(1, (self.card_width - 2 * self.padding) // 130)
        rows = (len(items) + items_per_row - 1) // items_per_row
        svg_parts = [f'<text x="{self.padding}" y="{y_offset}" class="stat-name">Legend</text>']

        for idx, (lang_key, count) in enumerate(items):
            x = self.padding + (idx % items_per_row) * col_width
            y = y_offset + 10 + (idx // items_per_row) * 16
            color = LANGUAGE_COLORS.get(lang_key, "#58a6ff")
            svg_parts.append(
                f"""
                 <g transform=\"translate({x},{y})\">\n                    <rect x=\"0\" y=\"-10\" width=\"12\" height=\"12\" fill=\"{color}\"/>\n                    <text x=\"18\" y=\"0\" class=\"stat-value\">{escape_xml(LANGUAGE_NAMES.get(lang_key, lang_key))} ({count})</text>\n                </g>"""
             )
        return "\n".join(svg_parts), rows * 16 + 16


def _respond_with_card(handler: BaseHTTPRequestHandler):
    query = parse_qs(urlparse(handler.path).query) if "?" in handler.path else {}
    card = CodeIdentifiersCard(query.get("username", [""])[0], query)
    svg = card.process()
    handler.send_response(200)
    handler.send_header("Content-Type", "image/svg+xml; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache, max-age=0")
    handler.end_headers()
    handler.wfile.write(svg.encode())


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _respond_with_card(self)
