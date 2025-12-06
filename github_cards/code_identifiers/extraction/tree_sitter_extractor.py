"""Tree-sitter based extractors for multiple languages."""

from __future__ import annotations

from typing import List, Dict, Set, Optional

from .base import BaseExtractor

# Tree-sitter imports (optional dependency)
try:
    from tree_sitter import Language, Parser
    import tree_sitter_javascript as ts_javascript
    import tree_sitter_typescript as ts_typescript
    import tree_sitter_java as ts_java
    import tree_sitter_go as ts_go
    TS_AVAILABLE = True
except ImportError:
    TS_AVAILABLE = False


class TreeSitterExtractor(BaseExtractor):
    """
    Extract identifiers using tree-sitter for accurate parsing.

    Supports JavaScript, TypeScript, Java, and Go with proper AST understanding.
    Falls back gracefully if tree-sitter is not installed.
    """

    # Node types to extract per language (focused on recall)
    EXTRACT_NODES: Dict[str, Set[str]] = {
        "javascript": {
            "identifier",
            "property_identifier",
            "shorthand_property_identifier",
            "shorthand_property_identifier_pattern",
        },
        "typescript": {
            "identifier",
            "property_identifier",
            "shorthand_property_identifier",
            "shorthand_property_identifier_pattern",
            "type_identifier",
        },
        "java": {
            "identifier",
            "type_identifier",
        },
        "go": {
            "identifier",
            "type_identifier",
            "field_identifier",
        },
    }

    # Node types that indicate a definition (for prioritization)
    DEFINITION_NODES: Dict[str, Set[str]] = {
        "javascript": {
            "function_declaration",
            "class_declaration",
            "method_definition",
            "variable_declarator",
            "arrow_function",
            "formal_parameters",
        },
        "typescript": {
            "function_declaration",
            "class_declaration",
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
            "method_definition",
            "variable_declarator",
            "arrow_function",
            "formal_parameters",
        },
        "java": {
            "class_declaration",
            "interface_declaration",
            "method_declaration",
            "field_declaration",
            "enum_declaration",
            "formal_parameter",
            "local_variable_declaration",
        },
        "go": {
            "function_declaration",
            "method_declaration",
            "type_spec",
            "const_spec",
            "var_spec",
            "field_declaration",
            "parameter_declaration",
        },
    }

    def __init__(self):
        self._parsers: Dict[str, Parser] = {}
        self._languages: Dict[str, Language] = {}
        if TS_AVAILABLE:
            self._init_parsers()

    def _init_parsers(self) -> None:
        """Initialize tree-sitter parsers for supported languages."""
        lang_modules = {
            "javascript": ts_javascript,
            "typescript": ts_typescript,
            "java": ts_java,
            "go": ts_go,
        }
        for lang_key, module in lang_modules.items():
            try:
                lang = Language(module.language())
                self._languages[lang_key] = lang
                parser = Parser(lang)
                self._parsers[lang_key] = parser
            except Exception:
                # Skip languages that fail to initialize
                pass

    def supports_language(self, lang_key: str) -> bool:
        """Check if tree-sitter supports this language."""
        return TS_AVAILABLE and lang_key in self._parsers

    def extract(self, code: str, lang_key: str) -> List[str]:
        """
        Extract identifiers from source code using tree-sitter AST.

        Args:
            code: Source code to parse
            lang_key: Language key (javascript, typescript, java, go)

        Returns:
            List of extracted identifier names
        """
        if not self.supports_language(lang_key):
            return []

        try:
            tree = self._parsers[lang_key].parse(code.encode("utf-8"))
            identifiers: List[str] = []
            self._walk_tree(tree.root_node, lang_key, identifiers)
            return identifiers
        except Exception:
            return []

    def _walk_tree(self, node, lang_key: str, identifiers: List[str]) -> None:
        """
        Walk the AST and collect identifiers.

        Recursively traverses all nodes, extracting text from identifier nodes.
        """
        extract_types = self.EXTRACT_NODES.get(lang_key, set())

        # Extract identifier text if this is an identifier node
        if node.type in extract_types:
            text = self._get_node_text(node)
            if text and len(text) > 2 and len(text) < 30:
                identifiers.append(text)

        # Recurse into children
        for child in node.children:
            self._walk_tree(child, lang_key, identifiers)

    def _get_node_text(self, node) -> Optional[str]:
        """Extract text content from a tree-sitter node."""
        try:
            if node.text:
                return node.text.decode("utf-8")
        except Exception:
            pass
        return None


__all__ = ["TreeSitterExtractor", "TS_AVAILABLE"]
