---
name: code_review
description: Review code for bugs, style issues, and improvement opportunities
---
# Code Review Skill

When asked to review code, follow this checklist:

1. **Correctness** - Identify bugs, edge cases, off-by-one errors.
2. **Security** - Check for injection, auth issues, secret exposure.
3. **Performance** - Flag unnecessary allocations, N+1 queries, missing indexes.
4. **Readability** - Suggest clearer naming, simpler control flow.

## Companion files

See `review_checklist.md` in this directory for the full checklist.

## Output format

For each issue found:
- **Severity**: critical / warning / suggestion
- **Location**: file and line
- **Description**: what's wrong and why
- **Fix**: suggested change
