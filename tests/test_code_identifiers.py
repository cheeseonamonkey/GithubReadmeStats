import pytest
from collections import Counter

from api.code_identifiers import CodeIdentifiersCard


def make_card(extract=None):
    params = {}
    if extract is not None:
        params['extract'] = [extract]
    return CodeIdentifiersCard('user', params)


def test_default_extract_types_used_when_missing():
    assert make_card().extract_type == {'types', 'identifiers'}


def test_extract_types_trimmed_and_lowercased():
    card = make_card(' Identifiers , TYPES ')
    assert card.extract_type == {'types', 'identifiers'}


def test_extract_types_fall_back_on_invalid_values():
    card = make_card(' , ,,unknown')
    assert card.extract_type == {'types', 'identifiers'}


def test_extract_types_keep_valid_subset():
    card = make_card('identifiers,unknown')
    assert card.extract_type == {'identifiers'}


def test_extract_respects_selected_types():
    card = make_card('types')
    code = """
class Alpha:
    value = 1
"""
    assert card._extract(code, 'python') == ['Alpha']


def test_legacy_extract_aliases_are_supported():
    card = make_card('classes,variables')
    assert card.extract_type == {'types', 'identifiers'}


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


def test_list_repos_paginates_and_limits(monkeypatch):
    card = make_card()
    card.MAX_REPOS = 120

    pages = {
        1: [{'name': f'r{i}', 'fork': False} for i in range(100)],
        2: [{'name': 'forked', 'fork': True}] + [{'name': f'r{i+100}', 'fork': False} for i in range(30)],
    }

    def fake_make_request(url):
        page = int(url.rsplit('page=', 1)[1])
        return pages.get(page, [])

    monkeypatch.setattr(card, '_make_request', fake_make_request)

    repos = card._list_repos()

    assert repos[0] == 'r0'
    assert repos[-1] == 'r119'
    assert 'forked' not in repos


@pytest.mark.parametrize(
    'lang, code, expected',
    [
        (
            'java',
            """
public class Demo {
    private int count = 0;
}
""",
            {'Demo', 'count'},
        ),
        (
            'kotlin',
            """
class Rocket
val thrust = 10
""",
            {'Rocket', 'thrust'},
        ),
        (
            'go',
            """
type Runner struct{}
var speed = 3
""",
            {'Runner', 'speed'},
        ),
        (
            'ruby',
            """
class Car
end
value = 1
""",
            {'Car', 'value'},
        ),
        (
            'php',
            """
<?php class Person {} $name = 'a'; ?>
""",
            {'Person', 'name'},
        ),
        (
            'csharp',
            """
public class Game { private int score = 0; }
""",
            {'Game', 'score'},
        ),
        (
            'c',
            """
struct Person { int age; };
int total = 5;
""",
            {'Person', 'total'},
        ),
        (
            'cpp',
            """
class Engine { public: int power; };
auto torque = 42;
""",
            {'Engine', 'torque'},
        ),
    ],
)
def test_extract_additional_languages(lang, code, expected):
    card = make_card()
    extracted = set(card._extract(code, lang))
    assert expected.issubset(extracted)
