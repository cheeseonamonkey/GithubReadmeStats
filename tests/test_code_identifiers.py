import os
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.code_identifiers import CodeIdentifiersCard


def make_card():
    return CodeIdentifiersCard('user', {})


def test_extract_filters_keywords_and_noise():
    card = make_card()
    code = """
for i in range(3):
    total = i + 1
    while total < 10:
        total += 1
"""

    names = card._extract(code, 'python')

    assert 'while' not in names
    assert names.count('total') >= 2


def test_extracts_identifiers_from_multiple_patterns():
    card = make_card()
    code = """
const startTime = Date.now();
function runner() {
  let message = 'ok';
  return message;
}
"""

    names = card._extract(code, 'javascript')

    assert 'date' not in [n.lower() for n in names]
    assert 'now' not in [n.lower() for n in names]
    assert names.count('message') >= 2
    assert {'startTime', 'runner'}.issubset(names)


def test_should_skip_generated_or_vendor_paths():
    card = make_card()
    assert card._should_skip('dist/bundle.js') is True
    assert card._should_skip('src/app.py') is False


def test_render_body_adds_legend_and_metadata():
    card = make_card()
    stats = {
        'items': [{'name': 'Alpha', 'count': 3, 'lang': 'python'}],
        'language_files': Counter({'python': 2, 'javascript': 1}),
        'repo_count': 2,
        'file_count': 3,
    }

    svg, height = card.render_body(stats)

    assert 'Legend' in svg
    assert 'Python (2)' in svg
    assert '2 repos • 3 files scanned' in svg
    assert height > 0


def test_process_without_username_errors():
    card = CodeIdentifiersCard('', {})
    svg = card.process()
    assert 'Missing ?username=' in svg
