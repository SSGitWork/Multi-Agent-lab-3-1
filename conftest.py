"""
conftest.py
===========
Pytest configuration for Lab 3.1.

Tests marked @pytest.mark.llm are skipped by default.
Pass --run-llm on the command line to include them.
"""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-llm",
        action="store_true",
        default=False,
        help="Run tests that make live LLM or network calls.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-llm"):
        return  # run everything

    skip_llm = pytest.mark.skip(reason="Live call — pass --run-llm to enable.")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip_llm)
