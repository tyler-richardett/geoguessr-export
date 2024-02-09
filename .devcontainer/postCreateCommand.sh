#! /usr/bin/env bash

# Install dependencies
poetry install --no-root

# Install Databricks CLI
brew tap databricks/tap
brew install databricks

# Mark the workspace folder as safe
git config --global --add safe.directory ${WORKSPACE}

# Install pre-commit hooks
poetry run pre-commit install --install-hooks
