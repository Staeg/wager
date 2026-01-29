# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

- **Install dependencies**: `pip install -r requirements.txt`
- **Install dev dependencies**: `pip install -r requirements-dev.txt`
- **Run all tests**: `pytest`
- **Run a single test**: `pytest tests/test_file.py::test_name`
- **Lint**: `ruff check .`
- **Format**: `ruff format .`

## Architecture

- `src/` — Application source code
- `tests/` — Pytest test files
- Python 3.12+, uses `ruff` for linting/formatting and `pytest` for testing
