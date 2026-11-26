
import json
import random


CLIENTS = ["ALICE", "BOB", "CHARLIE", "DAVE"]
SIDES = ["BUY", "SELL"]


def generate_events(seed: int, event_count: int = 100) -> list[dict]:
    """
    Generate reproducible exchange events.

    The same seed and event count always produce the same events.
    """

    if event_count < 0:
        raise ValueError("event_count cannot be negative")

    rng = random.Random(seed)

    events = []
    submitted_orders = []

    next_order_id = 1

    for _ in range(event_count):

        # Occasionally cancel an order submitted earlier.
        if submitted_orders and rng.random() < 0.20:
            order_id, owner = rng.choice(submitted_orders)

            events.append({
                "type": "CANCEL",
                "id": order_id,
                "client": owner,
            })

            continue

        client = rng.choice(CLIENTS)
        side = rng.choice(SIDES)
        quantity = rng.randint(1, 20)

        order_id = next_order_id
        next_order_id += 1

        # Generate either a LIMIT or MARKET order.
        if rng.random() < 0.75:
            price = rng.randint(90, 110)

            event = {
                "type": "LIMIT",
                "id": order_id,
                "client": client,
                "side": side,
                "price": price,
                "qty": quantity,
            }

        else:
            event = {
                "type": "MARKET",
                "id": order_id,
                "client": client,
                "side": side,
                "qty": quantity,
            }

        events.append(event)
        submitted_orders.append((order_id, client))

    return events


def generate_jsonl(seed: int, event_count: int = 100) -> str:
    """Convert generated events into JSON Lines text."""

    events = generate_events(seed, event_count)

    return "\n".join(
        json.dumps(event, separators=(",", ":"))
        for event in events
    )


def save_jsonl(
    seed: int,
    event_count: int = 100,
    filename: str = "testdata/generated_events.jsonl",
) -> None:
    """Save a reproducible event sequence to a file."""

    content = generate_jsonl(seed, event_count)

    with open(filename, "w", encoding="utf-8") as file:
        file.write(content)

        if content:
            file.write("\n")
