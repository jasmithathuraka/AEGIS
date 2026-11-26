# AEGIS Bug Documentation

This directory documents AEGIS testing evidence, controlled fault injections, and failure reduction.

## Documentation

- [Mutation Cases](mutation-cases.md) — controlled faults introduced into the C++ exchange and how the test suite detects them.
- [Shrinker Demonstration](shrinker-demo.md) — how AEGIS reduces a failing event sequence while preserving the failure.

## Reporting a Newly Discovered Bug

Only add a bug report when an actual defect has been reproduced. Keep deliberately introduced mutation cases separate from naturally discovered bugs.

Use this template:

### Bug ID: [Short title]

- **Component:**
- **Seed:**
- **Original event sequence:**
- **Reduced event sequence:**
- **Expected behaviour:**
- **Actual behaviour:**
- **Root cause:**
- **Fix:**
- **Regression test:**

Include enough information for someone else to reproduce the issue.

## Evidence Principles

- Distinguish real defects from deliberately introduced mutations.
- Preserve the exact input needed to reproduce a failure.
- Do not claim a bug was fixed without a regression test.
- Document limitations and surviving mutations honestly.