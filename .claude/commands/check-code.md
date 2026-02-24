---
description:
---

Run the following commands and ensure the code is clean.

From project root:

# Python linting

ruff check .

# Type checking

mypy .

One-liner to run everything:
ruff check . && mypy .

Or if you want to see all failures at once (doesn't stop on first error):
ruff check .; mypy .
