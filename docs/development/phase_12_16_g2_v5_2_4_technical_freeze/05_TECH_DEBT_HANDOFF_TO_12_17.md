# Technical debt handoff to Phase 12.17

The V5.2.4 scope passes strict mypy when dependency traversal is skipped. A
broader dependency-following mypy invocation reaches the existing calibration
test debt documented in the offline hardening package: 33 errors across 15
pre-existing files.

Representative debt remains in:

- calibration catalog and anchor corpus typing;
- optional budget comparisons in call plans;
- protocol observation typing;
- redundant casts in historical calibration helpers;
- optional Anthropic test-factory configuration.

None of these errors originates in the two V5.2.4 Python files. The debt is not
expanded or remediated in this minimal freeze and remains assigned to Phase
12.17.

`V5_2_4_NEW_MYPY_DEBT = FALSE`
