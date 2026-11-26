# AEGIS — Mutation Case Studies

This document records deliberate faults introduced into the C++ exchange engine to evaluate whether the AEGIS verification suite detects incorrect exchange behaviour.

These are controlled fault-injection experiments, not reports of naturally discovered production bugs.

## Test methodology

For each mutation:

1. Start with the original C++ exchange implementation.
2. Introduce one deliberate source-code change.
3. Compile the mutated implementation separately.
4. Run the same test input through the original and mutated executables.
5. Compare their outputs.
6. Record whether the mutation is detected.

The original source implementation remains unchanged by the mutation-testing script.

## Mutation 1 — Reversed FIFO Priority

**Component:** Order matching

**Injected fault:** Replace selection of the earliest order at a price level with selection of the latest order.

**Expected behaviour:** Orders at the same price must execute in arrival order.

**Incorrect behaviour:** A later order may execute before an earlier resting order.

**Detection:** Output mismatch between the original and mutated executables.

**Why it matters:** FIFO priority is a fundamental part of price-time order matching.

## Mutation 2 — Incorrect Execution Price

**Component:** Trade execution

**Injected fault:** Use the incoming order's price instead of the resting order's price when recording the execution price.

**Expected behaviour:** A trade executes at the resting order's price.

**Incorrect behaviour:** The recorded trade price may differ from the exchange's specified execution-price rule.

**Detection:** Output mismatch between the original and mutated executables.

**Why it matters:** Incorrect execution prices produce incorrect trade records and can affect downstream accounting.

## Mutation 3 — Incorrect Execution Quantity

**Component:** Trade execution

**Injected fault:** Replace the minimum of the two executable quantities with their maximum.

**Expected behaviour:** The executed quantity must not exceed either order's remaining quantity.

**Incorrect behaviour:** The exchange may record an execution larger than the quantity available on one side.

**Detection:** Output mismatch between the original and mutated executables.

**Why it matters:** Incorrect quantities can violate quantity conservation and corrupt order state.

## Mutation 4 — Cancellation Leaves a Stale Book Entry

**Component:** Order cancellation and order-book maintenance

**Injected fault:** Skip removal of the cancelled order from the price-level index.

**Expected behaviour:** A cancelled order must no longer participate in matching.

**Incorrect behaviour:** The order may remain represented in the indexed book after cancellation.

**Detection:** Output mismatch between the original and mutated executables.

**Why it matters:** Stale book entries can cause incorrect matching and inconsistent exchange state.

## Mutation 5 — Self-Trade Prevention Disabled

**Component:** Matching rules

**Injected fault:** Disable the self-trade prevention condition.

**Expected behaviour:** An incoming order must not execute against an order belonging to the same client when self-trade prevention applies.

**Incorrect behaviour:** The engine may execute a trade between orders from the same client.

**Detection:** Output mismatch between the original and mutated executables.

**Why it matters:** Matching must respect the exchange's client-level trading restrictions.

## Results

| Metric | Result |
|---|---:|
| Deliberate mutations introduced | 5 |
| Mutations detected | 5 |
| Mutations surviving | 0 |
| Detection score | 100% |

The score applies only to these five implemented mutations and their corresponding test inputs. It does not establish complete correctness or comprehensive mutation coverage.

## Limitations

- The mutation set is small and manually selected.
- Mutations are introduced through source-text replacements.
- The original executable acts as the output oracle.
- Output mismatches demonstrate detection for these scenarios, not correctness across every possible event sequence.
- Additional mutation operators and independent expected-output checks would strengthen the framework.

## Conclusion

These experiments demonstrate that the AEGIS C++ verification setup can detect five deliberately introduced exchange faults involving FIFO priority, execution price, execution quantity, cancellation and self-trade prevention.