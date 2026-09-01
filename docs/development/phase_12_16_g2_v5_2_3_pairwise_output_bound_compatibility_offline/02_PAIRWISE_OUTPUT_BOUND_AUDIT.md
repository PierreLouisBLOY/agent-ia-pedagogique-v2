# Pairwise output bound audit

## Root cause

The V5 contract defines the generic constant `MAX_OBSERVATION_CHARACTERS = 180`
in `tests/calibration/pedagogical/scorer_contract_v5.py`. The same constant is
used by absolute evidence, absolute defects, rubric text and pairwise difference
observations. The pairwise model, schema and V5.1 adapter therefore all enforced
the generic bound at three successive local layers.

No pairwise-specific historical justification for `180` is documented. The
value entered with the generic V5 evidence-first contract and was reused by the
pairwise surface. It is not a provider or pedagogical semantic threshold.

The Anthropic schema transformation preserves `minLength`/`maxLength` as a
description rather than as an enforced JSON-schema keyword. The local parser is
therefore the authoritative fail-closed bound. This explains how a structurally
valid provider response could reach the parser with 191 characters.

## Bounds

| Pairwise field | Current V5.2.2 bound | Risk observed or assessed | V5.2.3 recommendation |
|---|---:|---|---|
| `differences[*].observation` | `1..180` chars | Confirmed real response at `191`; generic limit is too tight for a concise comparative observation | Isolated `1..256`; covers 191 with bounded margin; never truncate |
| `differences[*].locator_a` | `1..64` chars | Low; locator is a compact section reference, not explanatory prose | Keep `64` |
| `differences[*].locator_b` | `1..64` chars | Low; same contract as locator A | Keep `64` |
| `rationale` | `1..240` chars | No observed failure; one bounded decision summary | Keep `240` |
| `differences` count | `1..8` items | No observed failure; prevents excessive output | Keep `8` |
| `significance` | closed enum | No free-text overflow | Keep closed enum |
| `favored_candidate` | closed enum | No free-text overflow | Keep closed enum |
| `decision` | closed enum | No free-text overflow | Keep closed enum and ambiguity rejection |
| `confidence` | closed enum | No free-text overflow | Keep closed enum |
| evidence text | absent | Pairwise output has no evidence array | No change |

Candidate A/B projections are input fields bounded separately at `2500`
characters. They are not pairwise output text and remain unchanged.

`OLD_PAIRWISE_DIFFERENCE_OBSERVATION_MAX = 180`

`NEW_PAIRWISE_DIFFERENCE_OBSERVATION_MAX = 256`
