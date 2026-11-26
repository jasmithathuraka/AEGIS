
# AEGIS Exchange Rules

Version: 1.2

## 1. Overview

AEGIS is a deterministic, single-threaded electronic exchange simulator.

It accepts order events, matches compatible buy and sell orders, records executed trades, and maintains an order book.

The exchange is governed by the rules in this document. All implementations must follow these rules independently.

## 2. Basic Order Rules

- Prices are positive integer ticks.
- Quantities are positive integers.
- Every order has a unique order ID.
- Every order belongs to a client.
- An order has one side: BUY or SELL.
- An order has one type: LIMIT or MARKET.
- An accepted order ID cannot be reused, even after the order is filled or cancelled.
- A rejected submission does not reserve its order ID.

## 3. Input Events

The exchange accepts three event types:

- LIMIT
- MARKET
- CANCEL

### 3.1 LIMIT

A LIMIT event contains:

- `type`
- `id`
- `client`
- `side`
- `price`
- `qty`

### 3.2 MARKET

A MARKET event contains:

- `type`
- `id`
- `client`
- `side`
- `qty`

### 3.3 CANCEL

A CANCEL event contains:

- `type`
- `id`
- `client`

## 4. Input Validation

Validation happens before an event reaches the matching engine.

- JSON input must be valid.
- Duplicate JSON object keys are rejected.
- The top-level JSON value must be an object.
- Missing or unexpected fields are rejected.
- IDs must be integers from 1 to 4,294,967,295.
- Quantities must be integers from 1 to 2,147,483,647.
- LIMIT prices must be integers from 1 to 2,147,483,647.
- Booleans are not accepted as integers.
- Client identifiers must contain 1–64 ASCII characters.
- Allowed client characters are letters, digits, underscores and hyphens.
- Side must be BUY or SELL.
- Event type must be LIMIT, MARKET or CANCEL.

Parser rejection codes:

- `MALFORMED_EVENT`
- `INVALID_TYPE`
- `INVALID_CLIENT`
- `INVALID_ID`
- `INVALID_SIDE`
- `INVALID_PRICE`
- `INVALID_QUANTITY`

Parser rejections must not modify exchange state.

## 5. Price-Time Priority

### 5.1 BUY Orders

Higher-priced BUY orders have priority.

### 5.2 SELL Orders

Lower-priced SELL orders have priority.

### 5.3 Equal Prices

When prices are equal, the older order has priority.

### 5.4 Partial Fills

A partially filled resting order retains its original time priority.

## 6. Matching Rules

- An incoming order matches against eligible orders on the opposite side.
- BUY orders match against the lowest eligible SELL price.
- SELL orders match against the highest eligible BUY price.
- Matching follows price-time priority.
- The execution price is the resting order's price.
- Execution quantity is the smaller of the incoming and resting remaining quantities.
- A LIMIT order with remaining quantity after matching rests in the order book.
- A MARKET order never rests in the order book.
- Any unfilled MARKET quantity is cancelled immediately.

## 7. Self-Trade Prevention

If an incoming order encounters an eligible resting order belonging to the same client:

- Matching stops immediately.
- The incoming order's remaining quantity is cancelled.
- The matching engine must not skip the same-client resting order.
- Trades executed before encountering that order remain valid.

## 8. Cancellation

- Only the owning client may cancel an order.
- Unknown order IDs are rejected.
- Orders with no remaining quantity cannot be cancelled again.
- Rejected cancellations do not change exchange state.
- A successful cancellation moves all remaining quantity into cancelled quantity.
- A cancelled order cannot return to the active order book.

## 9. Order Status

An order may have one of these statuses:

- `ACTIVE`
- `PARTIAL`
- `FILLED`
- `CANCELLED`

Status rules:

- ACTIVE: accepted and not yet executed.
- PARTIAL: some quantity has executed and quantity remains.
- FILLED: all original quantity has executed.
- CANCELLED: remaining quantity has been cancelled.

## 10. Quantity Conservation

Every order must satisfy:

Original Quantity = Executed Quantity + Cancelled Quantity + Remaining Quantity

This invariant must hold after every accepted event and in the final exchange state.

## 11. Sequence Numbers and Determinism

- Every physical input line receives a unique, increasing sequence number.
- This includes lines rejected by the parser.
- Sequence numbers begin at 1.
- Sequence numbers are assigned in input order.
- Valid events retain their assigned sequence number when passed to the exchange engine.
- Parser-rejected lines do not reach the matching engine.
- An event that reaches the exchange consumes its assigned sequence number, even if the exchange rejects it.
- The same input sequence must produce the same results.
- The sequence number of an accepted order determines its time priority.

## 12. Rejected Events

- Rejected events must not modify orders, trades or the order book.
- Parser-rejected events consume their physical input line sequence number but do not reach the exchange.
- Rejected order submissions do not reserve order IDs.
- Rejected cancellations leave the existing order state unchanged.

## 13. Order History

- Accepted orders remain in order history after filling or cancellation.
- Filled orders cannot be matched again.
- Cancelled orders cannot be matched again.
- Historical orders must not appear as active liquidity in the order book.

## 14. Verification Requirements

AEGIS uses independent implementations and verification techniques:

- Python exchange engine.
- Independent C++ matching engine.
- Independent reference matcher.
- Differential testing.
- Independent invariant checking.
- Deterministic event generation.
- Failure shrinking.
- Mutation testing.
- Performance benchmarking.

The reference matcher must be implemented directly from this specification. It must not copy the matching algorithm or internal data structures of the Python or C++ engines.
