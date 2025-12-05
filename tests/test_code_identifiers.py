import pytest
from collections import Counter

from api.code_identifiers import CodeIdentifiersCard


def make_card(extract=None):
    params = {}
    if extract is not None:
        params['extract'] = [extract]
    return CodeIdentifiersCard('user', params)


def test_default_extract_types_used_when_missing():
    assert make_card().extract_type == {'classes', 'variables'}


def test_extract_types_trimmed_and_lowercased():
    card = make_card(' Variables , CLASSES ')
    assert card.extract_type == {'classes', 'variables'}


def test_extract_types_fall_back_on_invalid_values():
    card = make_card(' , ,,unknown')
    assert card.extract_type == {'classes', 'variables'}


def test_extract_types_keep_valid_subset():
    card = make_card('variables,unknown')
    assert card.extract_type == {'variables'}


def test_extract_respects_selected_types():
    card = make_card('classes')
    code = """
class Alpha:
    value = 1
"""
    assert card._extract(code, 'python') == ['Alpha']


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
