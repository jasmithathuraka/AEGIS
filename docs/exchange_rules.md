# AEGIS — Exchange Rules

Version: 1.1

## 1. Overview

AEGIS is a deterministic, single-threaded electronic exchange simulator.

It accepts orders, matches compatible buy and sell orders, records trades,
and maintains an order book.

## 2. Basic Rules

- Prices are positive integers representing ticks.
- Quantities are positive integers.
- Every order has a unique ID.
- Every order belongs to a client.
- Supported sides are BUY and SELL.
- Supported event types are LIMIT, MARKET and CANCEL.

## 3. Order Priority

- BUY orders: highest price first.
- SELL orders: lowest price first.
- At equal prices, the oldest order has priority.
- Partially filled orders retain their original priority.

## 4. Matching

- Incoming orders match eligible orders on the opposite side.
- Execution price is the resting order's price.
- Execution quantity is the smaller remaining quantity.
- LIMIT orders rest in the book if not completely filled.
- MARKET orders never rest in the book.
- Unfilled MARKET quantity is cancelled.

## 5. Self-Trade Prevention

If an incoming order encounters an eligible resting order
from the same client:

- Stop matching immediately.
- Cancel the incoming order's remaining quantity.
- Preserve trades already executed.
- Do not skip the same-client order to match another order.

## 6. Cancellation

- Only the owning client can cancel an order.
- Unknown IDs are rejected.
- Orders that are already filled or cancelled cannot be cancelled again.
- Rejected cancellations do not change the order book.

## 7. Determinism

- Events are processed one at a time.
- Every physical input line receives a unique sequence number.
- The same input must always produce the same output.

## 8. Quantity Conservation

For every accepted order:

Original quantity = Executed quantity + Cancelled quantity + Remaining quantity.

## 9. Testing

AEGIS will use:

- A Python reference engine.
- An independent C++ matching engine.
- Differential testing.
- Independent invariant checking.
- Failure shrinking.
- Mutation testing.
- Performance benchmarking.