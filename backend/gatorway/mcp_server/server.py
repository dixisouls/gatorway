"""Builds the FastMCP server. Adding a tool = adding a module to tools/ with a `register(mcp, deps)` function (spec D15)."""
from __future__ import annotations

import importlib
import pkgutil

from fastmcp import FastMCP

from . import tools as tools_pkg
from .deps import Deps


def create_server(deps: Deps) -> FastMCP:
    mcp = FastMCP("gatorway")
    for mod in pkgutil.iter_modules(tools_pkg.__path__):
        importlib.import_module(f"{tools_pkg.__name__}.{mod.name}").register(mcp, deps)
    return mcp
