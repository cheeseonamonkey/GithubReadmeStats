import os
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.code_identifiers import CodeIdentifiersCard


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
