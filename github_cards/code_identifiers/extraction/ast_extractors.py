"""AST-based identifier extractors."""

from __future__ import annotations
import ast
from typing import List

from .base import BaseExtractor


class PythonASTExtractor(BaseExtractor):
    """
    Extract identifiers from Python code using AST parsing.

    More accurate than regex-based extraction as it understands Python syntax.
    """

    def supports_language(self, lang_key: str) -> bool:
        """Only supports Python."""
        return lang_key == "python"

    def extract(self, code: str, lang_key: str) -> List[str]:
        """
        Extract identifiers from Python code using AST.

        Args:
            code: Python source code
            lang_key: Language key (must be 'python')

        Returns:
            List of extracted identifiers
        """
        if not self.supports_language(lang_key):
            return []

        tree = ast.parse(code)
        visitor = IdentifierVisitor()
        visitor.visit(tree)
        return visitor.identifiers


class IdentifierVisitor(ast.NodeVisitor):
    """
    AST visitor that collects all meaningful identifiers.

    Extracts:
    - Function and method names
    - Class names
    - Parameter names (including typed parameters)
    - Variable names from assignments
    - Type annotations (custom types)
    - Decorator names
    - Attribute names (for frequently accessed attributes)
    - Base class names
    """

    def __init__(self):
        self.identifiers: List[str] = []
        self.seen: set[str] = set()

    def _add(self, name: str) -> None:
        """Add identifier if not already seen."""
        if name and name not in self.seen:
            self.identifiers.append(name)
            self.seen.add(name)

    def _extract_type_annotation(self, annotation) -> None:
        """Extract type names from type annotations."""
        if isinstance(annotation, ast.Name):
            self._add(annotation.id)
        elif isinstance(annotation, ast.Subscript):
            # Handle generics like List[User], Optional[Response]
            self._extract_type_annotation(annotation.value)
            self._extract_type_annotation(annotation.slice)
        elif isinstance(annotation, ast.Tuple):
            # Handle Union[A, B] style annotations
            for elt in annotation.elts:
                self._extract_type_annotation(elt)
        elif isinstance(annotation, ast.Attribute):
            # Handle module.Type style annotations
            self._extract_type_annotation(annotation.value)
            self._add(annotation.attr)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract from function definitions."""
        # Function name
        self._add(node.name)

        # Parameters
        for arg in node.args.args:
            self._add(arg.arg)
            if arg.annotation:
                self._extract_type_annotation(arg.annotation)

        # Keyword-only arguments
        for arg in node.args.kwonlyargs:
            self._add(arg.arg)
            if arg.annotation:
                self._extract_type_annotation(arg.annotation)

        # Return type annotation
        if node.returns:
            self._extract_type_annotation(node.returns)

        # Decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                self._add(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                self._add(decorator.attr)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Extract from async function definitions."""
        # Same as FunctionDef
        self.visit_FunctionDef(node)  # type: ignore

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract from class definitions."""
        # Class name
        self._add(node.name)

        # Base classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                self._add(base.id)
            elif isinstance(base, ast.Attribute):
                self._add(base.attr)

        # Decorators
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                self._add(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                self._add(decorator.attr)

        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Extract from annotated assignments (e.g., var: Type = value)."""
        # Variable name
        if isinstance(node.target, ast.Name):
            self._add(node.target.id)

        # Type annotation
        if node.annotation:
            self._extract_type_annotation(node.annotation)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Extract from regular assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._add(target.id)
            elif isinstance(target, ast.Tuple):
                # Handle tuple unpacking: a, b = ...
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self._add(elt.id)

        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Extract loop variables."""
        if isinstance(node.target, ast.Name):
            self._add(node.target.id)
        elif isinstance(node.target, ast.Tuple):
            # Handle: for a, b in items:
            for elt in node.target.elts:
                if isinstance(elt, ast.Name):
                    self._add(elt.id)

        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Extract exception variable names and types."""
        if node.name:
            self._add(node.name)
        if node.type:
            if isinstance(node.type, ast.Name):
                self._add(node.type.id)

        self.generic_visit(node)


__all__ = ["PythonASTExtractor", "IdentifierVisitor"]
