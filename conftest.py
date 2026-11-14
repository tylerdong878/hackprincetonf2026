"""Repo-wide pytest setup.

Tests use scripted fake models. Never send their runs to LangSmith: it clutters the dashboard
and spends the free trace quota. Setting the env vars here, before any test module loads .env,
wins because python-dotenv does not override variables that are already set.
"""

import os

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
