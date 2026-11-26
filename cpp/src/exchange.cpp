
#include "exchange.hpp"

#include <algorithm>
#include <limits>
#include <utility>

namespace aegis {

Exchange::Exchange()
    : last_event_seq_(0),
      next_trade_seq_(1),
      trade_sequence_exhausted_(false) {}

EventResult Exchange::rejected(
    std::uint64_t seq,
    const std::string& code
) const {
    return {seq, "REJECTED", code, {}, {}};
}

bool Exchange::valid_client(const std::string& client) {
    if (client.empty() || client.size() > 64) {
        return false;
    }

    for (unsigned char c : client) {
        const bool valid =
            (c >= 'A' && c <= 'Z') ||
            (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') ||
            c == '_' || c == '-';

        if (!valid) {
            return false;
        }
    }

    return true;
}

std::int32_t Exchange::checked_add(
    std::int32_t a,
    std::int32_t b
) {
    const std::int64_t result =
        static_cast<std::int64_t>(a) +
        static_cast<std::int64_t>(b);

    if (
        result > std::numeric_limits<std::int32_t>::max() ||
        result < std::numeric_limits<std::int32_t>::min()
    ) {
        throw std::overflow_error("ARITHMETIC_OVERFLOW");
    }

    return static_cast<std::int32_t>(result);
}

const std::map<std::uint32_t, Order>& Exchange::orders() const {
    return orders_;
}

const std::vector<Trade>& Exchange::trades() const {
    return trades_;
}

void Exchange::add_to_book(const Order& order) {
    if (
        !order.price ||
        order.remaining_qty <= 0 ||
        (order.status != OrderStatus::ACTIVE &&
         order.status != OrderStatus::PARTIAL)
    ) {
        return;
    }

    const QueueEntry entry{order.sequence, order.id};

    if (order.side == Side::BUY) {
        bid_levels_[*order.price].insert(entry);
    } else {
        ask_levels_[*order.price].insert(entry);
    }
}

void Exchange::remove_from_book(const Order& order) {
    if (!order.price) {
        return;
    }

    const QueueEntry entry{order.sequence, order.id};

    PriceLevels& levels =
        order.side == Side::BUY ? bid_levels_ : ask_levels_;

    auto level_it = levels.find(*order.price);

    if (level_it == levels.end()) {
        return;
    }

    level_it->second.erase(entry);

    if (level_it->second.empty()) {
        levels.erase(level_it);
    }
}

std::vector<Order> Exchange::get_bids() const {
    std::vector<Order> result;

    for (auto level_it = bid_levels_.rbegin();
         level_it != bid_levels_.rend();
         ++level_it) {

        for (const auto& entry : level_it->second) {
            auto order_it = orders_.find(entry.second);

            if (order_it != orders_.end()) {
                result.push_back(order_it->second);
            }
        }
    }

    return result;
}

std::vector<Order> Exchange::get_asks() const {
    std::vector<Order> result;

    for (const auto& [price, queue] : ask_levels_) {
        (void)price;

        for (const auto& entry : queue) {
            auto order_it = orders_.find(entry.second);

            if (order_it != orders_.end()) {
                result.push_back(order_it->second);
            }
        }
    }

    return result;
}

std::vector<Trade> Exchange::match(
    Order& incoming,
    bool market,
    std::uint64_t event_seq,
    std::map<std::uint32_t, Order>& rollback_orders
) {
    std::vector<Trade> event_trades;

    while (incoming.remaining_qty > 0) {
        std::uint32_t resting_id = 0;
        std::int32_t resting_price = 0;

        if (incoming.side == Side::BUY) {
            if (ask_levels_.empty()) {
                break;
            }

            auto level_it = ask_levels_.begin();

            resting_price = level_it->first;
            resting_id = level_it->second.begin()->second;
        } else {
            if (bid_levels_.empty()) {
                break;
            }

            auto level_it = bid_levels_.rbegin();

            resting_price = level_it->first;
            resting_id = level_it->second.begin()->second;
        }

        if (!market) {
            if (
                incoming.side == Side::BUY &&
                *incoming.price < resting_price
            ) {
                break;
            }

            if (
                incoming.side == Side::SELL &&
                *incoming.price > resting_price
            ) {
                break;
            }
        }

        auto resting_it = orders_.find(resting_id);

        if (resting_it == orders_.end()) {
            throw std::logic_error(
                "Order-book index references a missing order"
            );
        }

        Order& resting = resting_it->second;

        if (
            resting.status != OrderStatus::ACTIVE &&
            resting.status != OrderStatus::PARTIAL
        ) {
            throw std::logic_error(
                "Inactive order found in order-book index"
            );
        }

        if (resting.remaining_qty <= 0) {
            throw std::logic_error(
                "Empty order found in order-book index"
            );
        }

        // Save each existing resting order only once.
        rollback_orders.try_emplace(resting_id, resting);

        // Self-trade prevention.
        if (resting.client == incoming.client) {
            incoming.cancelled_qty = checked_add(
                incoming.cancelled_qty,
                incoming.remaining_qty
            );

            incoming.remaining_qty = 0;
            incoming.status = OrderStatus::CANCELLED;
            break;
        }

        if (trade_sequence_exhausted_) {
            throw std::overflow_error("ARITHMETIC_OVERFLOW");
        }

        const std::int32_t quantity =
            std::min(
                incoming.remaining_qty,
                resting.remaining_qty
            );

        if (quantity <= 0) {
            throw std::logic_error("Invalid matching quantity");
        }

        const std::int32_t new_incoming_executed =
            checked_add(incoming.executed_qty, quantity);

        const std::int32_t new_resting_executed =
            checked_add(resting.executed_qty, quantity);

        const std::int32_t new_incoming_remaining =
            incoming.remaining_qty - quantity;

        const std::int32_t new_resting_remaining =
            resting.remaining_qty - quantity;

        Trade trade{
            next_trade_seq_,
            event_seq,
            incoming.side == Side::BUY
                ? incoming.id
                : resting.id,
            incoming.side == Side::SELL
                ? incoming.id
                : resting.id,
            quantity,
            resting_price
        };

        if (
            next_trade_seq_ ==
            std::numeric_limits<std::uint64_t>::max()
        ) {
            trade_sequence_exhausted_ = true;
        } else {
            ++next_trade_seq_;
        }

        incoming.executed_qty = new_incoming_executed;
        incoming.remaining_qty = new_incoming_remaining;

        incoming.status =
            incoming.remaining_qty == 0
                ? OrderStatus::FILLED
                : OrderStatus::PARTIAL;

        resting.executed_qty = new_resting_executed;
        resting.remaining_qty = new_resting_remaining;

        if (resting.remaining_qty == 0) {
            resting.status = OrderStatus::FILLED;
            remove_from_book(resting);
        } else {
            resting.status = OrderStatus::PARTIAL;
        }

        trades_.push_back(trade);
        event_trades.push_back(trade);
    }

    return event_trades;
}

EventResult Exchange::submit_limit(
    std::uint64_t event_seq,
    std::uint32_t id,
    const std::string& client,
    Side side,
    std::int32_t price,
    std::int32_t qty
) {
    return submit(
        event_seq,
        id,
        client,
        side,
        OrderType::LIMIT,
        price,
        qty
    );
}

EventResult Exchange::submit_market(
    std::uint64_t event_seq,
    std::uint32_t id,
    const std::string& client,
    Side side,
    std::int32_t qty
) {
    return submit(
        event_seq,
        id,
        client,
        side,
        OrderType::MARKET,
        std::nullopt,
        qty
    );
}

EventResult Exchange::submit(
    std::uint64_t event_seq,
    std::uint32_t id,
    const std::string& client,
    Side side,
    OrderType type,
    std::optional<std::int32_t> price,
    std::int32_t qty
) {
    if (event_seq <= last_event_seq_) {
        return rejected(event_seq, "MALFORMED_EVENT");
    }

    const std::uint64_t old_last_event_seq = last_event_seq_;
    last_event_seq_ = event_seq;

    // Validation rejections only advance the event sequence.
    if (!valid_client(client)) {
        return rejected(event_seq, "INVALID_CLIENT");
    }

    if (id == 0) {
        return rejected(event_seq, "INVALID_ID");
    }

    if (used_ids_.count(id) != 0) {
        return rejected(event_seq, "DUPLICATE_ID");
    }

    if (qty <= 0) {
        return rejected(event_seq, "INVALID_QUANTITY");
    }

    if (type == OrderType::LIMIT && (!price || *price <= 0)) {
        return rejected(event_seq, "INVALID_PRICE");
    }

    const std::size_t old_trade_count = trades_.size();
    const std::uint64_t old_next_trade_seq = next_trade_seq_;
    const bool old_trade_sequence_exhausted =
        trade_sequence_exhausted_;

    std::map<std::uint32_t, Order> rollback_orders;

    auto rollback = [&]() {
        auto incoming_it = orders_.find(id);

        if (incoming_it != orders_.end()) {
            remove_from_book(incoming_it->second);
            orders_.erase(incoming_it);
        }

        used_ids_.erase(id);

        for (const auto& [saved_id, saved_order] : rollback_orders) {
            auto current_it = orders_.find(saved_id);

            if (current_it == orders_.end()) {
                throw std::logic_error(
                    "Cannot restore missing pre-existing order"
                );
            }

            remove_from_book(current_it->second);
            current_it->second = saved_order;
            add_to_book(current_it->second);
        }

        trades_.resize(old_trade_count);
        next_trade_seq_ = old_next_trade_seq;
        trade_sequence_exhausted_ = old_trade_sequence_exhausted;
        last_event_seq_ = old_last_event_seq;
    };

    try {
        Order incoming{
            id,
            client,
            side,
            type,
            price,
            qty,
            qty,
            0,
            0,
            event_seq,
            OrderStatus::ACTIVE
        };

        used_ids_.insert(id);
        orders_.emplace(id, incoming);

        Order& stored_incoming = orders_.at(id);

        std::vector<Trade> event_trades =
            match(
                stored_incoming,
                type == OrderType::MARKET,
                event_seq,
                rollback_orders
            );

        if (
            type == OrderType::MARKET &&
            stored_incoming.remaining_qty > 0
        ) {
            stored_incoming.cancelled_qty = checked_add(
                stored_incoming.cancelled_qty,
                stored_incoming.remaining_qty
            );

            stored_incoming.remaining_qty = 0;
            stored_incoming.status = OrderStatus::CANCELLED;
        }

        if (
            type == OrderType::LIMIT &&
            stored_incoming.remaining_qty > 0 &&
            stored_incoming.status != OrderStatus::CANCELLED
        ) {
            stored_incoming.status =
                stored_incoming.executed_qty > 0
                    ? OrderStatus::PARTIAL
                    : OrderStatus::ACTIVE;

            add_to_book(stored_incoming);
        }

        std::vector<Order> updates;
        updates.push_back(stored_incoming);

        for (const Trade& trade : event_trades) {
            const std::uint32_t resting_id =
                trade.buy_id == id
                    ? trade.sell_id
                    : trade.buy_id;

            updates.push_back(orders_.at(resting_id));
        }

        std::sort(
            updates.begin(),
            updates.end(),
            [](const Order& a, const Order& b) {
                return a.id < b.id;
            }
        );

        updates.erase(
            std::unique(
                updates.begin(),
                updates.end(),
                [](const Order& a, const Order& b) {
                    return a.id == b.id;
                }
            ),
            updates.end()
        );

        return {
            event_seq,
            "ACCEPTED",
            "",
            std::move(event_trades),
            std::move(updates)
        };
    } catch (...) {
        // Best-effort restoration. Re-inserting into std::map/std::set
        // can allocate; allocation failure during restoration is a limit.
        rollback();
        throw;
    }
}

EventResult Exchange::cancel(
    std::uint64_t event_seq,
    std::uint32_t id,
    const std::string& client
) {
    if (event_seq <= last_event_seq_) {
        return rejected(event_seq, "MALFORMED_EVENT");
    }

    const std::uint64_t old_last_event_seq = last_event_seq_;
    last_event_seq_ = event_seq;

    if (!valid_client(client)) {
        return rejected(event_seq, "INVALID_CLIENT");
    }

    if (id == 0) {
        return rejected(event_seq, "INVALID_ID");
    }

    auto it = orders_.find(id);

    if (it == orders_.end()) {
        return rejected(event_seq, "UNKNOWN_ID");
    }

    if (it->second.client != client) {
        return rejected(event_seq, "WRONG_CLIENT");
    }

    if (
        it->second.status != OrderStatus::ACTIVE &&
        it->second.status != OrderStatus::PARTIAL
    ) {
        return rejected(event_seq, "NOT_ACTIVE");
    }

    const Order old_order = it->second;

    try {
        remove_from_book(it->second);

        it->second.cancelled_qty = checked_add(
            it->second.cancelled_qty,
            it->second.remaining_qty
        );

        it->second.remaining_qty = 0;
        it->second.status = OrderStatus::CANCELLED;

        Order update = it->second;

        return {
            event_seq,
            "ACCEPTED",
            "",
            {},
            {std::move(update)}
        };
    } catch (...) {
        auto current_it = orders_.find(id);

        if (current_it != orders_.end()) {
            remove_from_book(current_it->second);
            current_it->second = old_order;
            add_to_book(current_it->second);
        }

        last_event_seq_ = old_last_event_seq;
        throw;
    }
}

}
