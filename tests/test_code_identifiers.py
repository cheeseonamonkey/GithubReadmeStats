import os
import sys
import pytest
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.code_identifiers import CodeIdentifiersCard


def make_card(filter_value=None):
    params = {}
    if filter_value is not None:
        params['filter'] = [filter_value]
    return CodeIdentifiersCard('user', params)


def test_default_filters_used_when_missing():
    assert make_card().extract_filters == {'types', 'identifiers'}


def test_filters_trimmed_and_lowercased():
    card = make_card(' Identifiers , TYPES ')
    assert card.extract_filters == {'types', 'identifiers'}


def test_filters_fall_back_on_invalid_values():
    card = make_card(' , ,,unknown')
    assert card.extract_filters == {'types', 'identifiers'}


def test_filters_keep_valid_subset():
    card = make_card('types')
    assert card.extract_filters == {'types'}


def test_extract_respects_selected_types():
    card = make_card('types')
    code = """
class Alpha:
    value = 1
"""
    assert card._extract(code, 'python') == ['Alpha']


def test_extract_identifiers_includes_functions_and_variables():
    card = make_card('identifiers')
    code = """
def shout(value):
    total = value + 1
    return total
"""

    assert card._extract(code, 'python') == ['shout', 'total']


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
