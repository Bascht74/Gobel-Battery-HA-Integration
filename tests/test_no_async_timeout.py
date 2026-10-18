"""Home Assistant 2026.10 no longer installs async_timeout, and hassfest rejects it.

The integration must use asyncio.timeout from the standard library instead.
"""

import ast
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "gobel_battery"


def imported_modules(path):
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_module_imports_async_timeout():
    users = [path.name for path in sorted(COMPONENT.glob("*.py")) if "async_timeout" in imported_modules(path)]
    assert users == []
