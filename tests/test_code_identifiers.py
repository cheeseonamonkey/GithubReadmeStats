import os
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from github_cards.code_identifiers import card as card_module
from github_cards.code_identifiers import CodeIdentifiersCard
from github_cards.code_identifiers.card import IdentifierMatch
from github_cards.code_identifiers.filtering.quality_scorer import score_and_rank_identifiers


def make_card():
    return CodeIdentifiersCard('user', {})


def test_extract_filters_keywords():
    card = make_card()
    code = """
def my_function():
    total = 0
    for i in range(3):
        total = i + 1
    return total
"""
    names = card._extract(code, 'python')
    assert 'for' not in names
    assert 'return' not in names
    assert 'my_function' in names
    assert 'total' in names


def test_extract_strips_comments_and_strings():
    card = make_card()
    code = '''
# this is a comment with fake_var
def real_func():
    msg = "string with fake_name inside"
    return msg
'''
    names = card._extract(code, 'python')
    assert 'fake_var' not in names
    assert 'fake_name' not in names
    assert 'real_func' in names
    assert 'msg' in names


def test_extract_strips_imports():
    card = make_card()
    code = """
import os
from collections import Counter
import some_module as alias_name

def actual_function():
    data = 123
"""
    names = card._extract(code, 'python')
    # import statements stripped, so these shouldn't appear
    assert 'Counter' not in names
    assert 'some_module' not in names
    assert 'alias_name' not in names
    assert 'actual_function' in names
    assert 'data' in names


def test_extracts_js_identifiers():
    card = make_card()
    code = """
const startTime = Date.now();
function runner() {
  let message = 'ok';
  return message;
}
"""
    names = card._extract(code, 'javascript')
    assert 'startTime' in names
    assert 'runner' in names
    assert 'message' in names


def test_extracts_typescript_structures_and_methods():
    card = make_card()
    code = """
export interface Widget { id: string }
type Alias = { ok: boolean };
enum Status { Ready, Done }
class Control {
  start() {}
}
"""
    names = card._extract(code, 'typescript')
    assert {'Widget', 'Alias', 'Status', 'Control', 'start'}.issubset(set(names))


def test_extracts_typescript_properties_and_exports():
    card = make_card()
    code = """
export default class Runner {
  public title: string;
  private count = 0;
  run = () => count;
  execute(task: string): void {}
}
"""
    names = card._extract(code, 'typescript')
    assert {'Runner', 'title', 'count', 'run', 'execute'}.issubset(set(names))


def test_extracts_python_classes_and_attributes():
    card = make_card()
    code = """
class MyService:
    def __init__(self):
        self.counter = 0

    async def run_task(self):
        pass
"""
    names = card._extract(code, 'python')
    assert {'MyService', 'counter', 'run_task'}.issubset(set(names))


def test_extracts_java_classes_and_members():
    card = make_card()
    code = """
import java.util.List;
@Deprecated
public class Sample {
    private List<String> entries;
    String formatValue(String input) { return input; }
}
"""
    names = card._extract(code, 'java')
    assert {'Sample', 'entries', 'formatValue'}.issubset(set(names))


def test_extracts_annotations_and_generics():
    card = make_card()
    code = """
@Override
public class Sample<T> {
    private Map<String, List<Item>> table;

    public Sample() {
        new Builder();
    }
}
"""
    names = set(card._extract(code, 'java'))
    assert {'Sample', 'Map', 'List', 'Item', 'table', 'Builder'}.issubset(names)
    assert 'Override' not in names


def test_should_skip_generated_or_vendor_paths():
    card = make_card()
    assert card._should_skip('dist/bundle.js') is True
    assert card._should_skip('node_modules/pkg/index.js') is True
    assert card._should_skip('src/app.py') is False


def test_render_body_adds_legend_and_metadata():
    card = make_card()
    stats = {
        'items': [{'name': 'alpha', 'count': 3, 'lang': 'python'}],
        'language_files': Counter({'python': 2, 'javascript': 1}),
        'repo_count': 2,
        'file_count': 3,
    }
    svg, height = card.render_body(stats)
    assert 'Legend' in svg
    assert 'Python (2)' in svg
    assert '2 repos' in svg
    assert height > 0


def test_process_without_username_errors():
    card = CodeIdentifiersCard('', {})
    svg = card.process()
    assert 'Missing ?username=' in svg


def test_csharp_strips_using_statements():
    card = make_card()
    code = """
using System;
using System.Collections.Generic;

public class Test {
    void myMethod() {
        var count = 0;
    }
}
"""
    names = card._extract(code, 'csharp')
    assert 'System' not in names
    assert 'Generic' not in names
    assert 'myMethod' in names
    assert 'count' in names


def test_filters_system_and_override_substrings():
    card = make_card()
    code = """
class SystemManager:
    def __init__(self):
        self.override_mode = False

def active_task():
    pass
"""
    names = set(card._extract(code, 'python'))
    assert 'SystemManager' not in names
    assert 'override_mode' not in names
    assert 'active_task' in names


def test_extracts_python_generic_wrappers():
    card = make_card()
    code = """
from typing import Optional, Dict

item: Optional[Response]
items: Dict[str, Response]
"""
    names = set(card._extract(code, 'python'))
    assert {'Optional', 'Dict', 'Response', 'item', 'items'}.issubset(names)


def test_csharp_properties_and_async_methods():
    card = make_card()
    code = """
[ApiController]
public class DemoController {
    public string Name { get; set; }
    private async Task RunAsync() { }
}
"""
    names = card._extract(code, 'csharp')
    assert {'DemoController', 'Name', 'RunAsync'}.issubset(set(names))


def test_attributes_and_base_classes_are_captured():
    card = make_card()
    code = """
[Authorize]
public class OrdersController : Controller { }

class AdvancedController extends BaseController { }
"""
    names = set(card._extract(code, 'csharp'))
    assert {'Authorize', 'Controller', 'AdvancedController', 'BaseController'}.issubset(names)


def test_python_lambdas_params_and_loops():
    card = make_card()
    code = """
@cached
def process(item: ItemType, row_id: int) -> ResultType:
    config_name = "value"
    helper = lambda value: value + 1
    for view, element in enumerate(items):
        pass
"""
    names = set(card._extract(code, 'python'))
    assert {'process', 'item', 'row_id', 'ItemType', 'ResultType', 'config_name', 'helper', 'view', 'element', 'cached'}.issubset(names)


def test_normalizes_identifier_casing():
    extractor = make_card().extractor
    assert extractor.normalize_identifier('myFunc') == extractor.normalize_identifier('my_func') == 'my_func'


def test_render_body_supports_multiple_languages_per_bar():
    card = make_card()
    stats = {
        'items': [
            {
                'name': 'alpha',
                'count': 4,
                'langs': Counter({'python': 2, 'javascript': 2}),
            }
        ],
        'language_files': Counter({'python': 2, 'javascript': 2}),
        'repo_count': 1,
        'file_count': 4,
    }
    svg, _ = card.render_body(stats)
    assert '#3572A5' in svg and '#f1e05a' in svg
    assert 'rx=' not in svg


def test_filters_exclude_unwanted_identifiers():
    params = {'filter': ['System', '@Override, List']}
    card = CodeIdentifiersCard('user', params)
    candidates = [
        IdentifierMatch('system_collections_generic', 'System.Collections.Generic', 'csharp'),
        IdentifierMatch('override', 'Override', 'java'),
        IdentifierMatch('list', 'List', 'csharp'),
        IdentifierMatch('runner', 'runner', 'javascript'),
    ]
    filtered = [match.display for match in candidates if card._should_include(match)]
    assert filtered == ['runner']


def test_fetch_file_uses_lru_cache(monkeypatch):
    card_module._cached_fetch_file.cache_clear()

    call_count = 0

    def fake_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1

        class DummyResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"cached-content"

        return DummyResponse()

    monkeypatch.setattr(card_module.urllib.request, 'urlopen', fake_urlopen)
    card = CodeIdentifiersCard('user', {})
    lang_one, content_one = card._fetch_file('repo', 'path.cs', '.cs')
    lang_two, content_two = card._fetch_file('repo', 'path.cs', '.cs')

    assert lang_one == lang_two == card_module.EXTENSION_TO_LANG['.cs']
    assert content_one == content_two == 'cached-content'
    assert call_count == 1


def test_fun_identifiers_get_small_boost_but_count_wins():
    items = [
        {'name': 'data', 'count': 40, 'langs': Counter({'python': 40})},
        {'name': 'RainbowUnicorn', 'count': 10, 'langs': Counter({'python': 10})},
        {'name': 'launchRocket', 'count': 10, 'langs': Counter({'javascript': 6, 'typescript': 4})},
        {'name': 'default_manager', 'count': 10, 'langs': Counter({'python': 10})},
    ]

    ranked = score_and_rank_identifiers(items.copy())
    ordered_names = [item['name'] for item in ranked]

    # Count stays dominant
    assert ordered_names[0] == 'data'
    # Style nudges tie-breakers for equal counts
    assert ordered_names.index('RainbowUnicorn') < ordered_names.index('default_manager')
    assert ordered_names.index('launchRocket') < ordered_names.index('default_manager')
