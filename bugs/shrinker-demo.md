
# AEGIS — Failure Shrinker

## Overview

AEGIS includes a failure-shrinking component that attempts to reduce a failing event sequence into a smaller reproduction.

A long sequence of exchange events can make a defect difficult to isolate. The shrinker reduces the input while checking whether the original failure continues to reproduce.

The goal is to make failures easier to inspect, understand, and debug.

## How It Works

The shrinker uses two reduction stages.

### 1. Event-count reduction

The event reducer uses a chunk-based reduction strategy.

It:

1. Starts with the original failing event sequence.
2. Divides the sequence into chunks.
3. Attempts to remove individual chunks.
4. Checks whether the remaining sequence still reproduces the failure.
5. Keeps successful reductions.
6. Adjusts the chunk granularity and repeats.

The process stops when no further chunk removal is accepted by the failure predicate.

### 2. Numeric-value reduction

After reducing the event count, the shrinker attempts to simplify numeric values.

Currently, it targets:

- `price`
- `qty`

For each eligible integer, it tries smaller candidates:

- `1`
- Half the original value
- One less than the original value

A candidate is retained only if the supplied failure predicate still returns true.

## Failure Preservation

The shrinker accepts a callback named `still_fails`.

This callback determines whether a candidate event sequence still reproduces the failure being investigated.

The original sequence must reproduce a failure before shrinking begins. Otherwise, `shrink_events()` raises a `ValueError`.

Candidate sequences are deep-copied before being passed to the predicate, helping prevent accidental modifications to the original input.

If the predicate raises an exception, the candidate is treated as not reproducing the failure.

**Important:** The caller is responsible for ensuring that the predicate checks for the same failure, rather than merely detecting any unrelated error.

## Reporting

AEGIS provides a `ShrinkReport` containing:

- Original event sequence
- Reduced event sequence
- Original event count
- Reduced event count
- Optional original failure description
- Optional reduced failure description
- Percentage reduction

The reduction percentage is calculated as:

`((original_count - reduced_count) / original_count) * 100`

The report printer displays the original and reduced event counts, reduction percentage, failure descriptions when supplied, and the reduced reproduction.

## Current Limitations

- The shrinker is greedy and does not guarantee a globally minimal sequence.
- Numeric reduction currently targets only `price` and `qty`.
- Numeric candidates must be positive integers greater than one.
- The shrinker relies on the caller's failure predicate to identify the original failure correctly.
- It does not automatically identify the root cause of a failure.
- It does not currently minimise every possible event field or event dependency.

## Testing

The shrinker test suite was executed locally:

`PYTHONPATH=src pytest tests/test_shrinker.py -v`

**Observed result: 8 passed, 0 failed.**

This confirms that the current shrinker behaviour passes its eight implemented tests. It does not establish that every possible failing event sequence can be minimised.

## Conclusion

The AEGIS shrinker adds a debugging capability to the adversarial testing workflow.

Instead of stopping at detecting a failing sequence, it attempts to produce a smaller input that preserves the failure, making subsequent investigation more manageable.
