
#ifndef AEGIS_EXCHANGE_HPP
#define AEGIS_EXCHANGE_HPP

#include <cstdint>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace aegis {

struct ExchangeTestAccess;

enum class Side { BUY, SELL };
enum class OrderType { LIMIT, MARKET };
enum class OrderStatus { ACTIVE, PARTIAL, FILLED, CANCELLED };

struct Order {
    std::uint32_t id;
    std::string client;
    Side side;
    OrderType type;
    std::optional<std::int32_t> price;
    std::int32_t original_qty;
    std::int32_t remaining_qty;
    std::int32_t executed_qty = 0;
    std::int32_t cancelled_qty = 0;
    std::uint64_t sequence;
    OrderStatus status = OrderStatus::ACTIVE;
};

struct Trade {
    std::uint64_t trade_seq;
    std::uint64_t event_seq;
    std::uint32_t buy_id;
    std::uint32_t sell_id;
    std::int32_t qty;
    std::int32_t price;
};

struct EventResult {
    std::uint64_t seq;
    std::string status;
    std::string reject_code;
    std::vector<Trade> trades;
    std::vector<Order> order_updates;
};

class Exchange {
    friend struct ExchangeTestAccess;

public:
    Exchange();

    EventResult submit_limit(
        std::uint64_t event_seq,
        std::uint32_t id,
        const std::string& client,
        Side side,
        std::int32_t price,
        std::int32_t qty
    );

    EventResult submit_market(
        std::uint64_t event_seq,
        std::uint32_t id,
        const std::string& client,
        Side side,
        std::int32_t qty
    );

    EventResult cancel(
        std::uint64_t event_seq,
        std::uint32_t id,
        const std::string& client
    );

    const std::map<std::uint32_t, Order>& orders() const;
    const std::vector<Trade>& trades() const;

private:
    using QueueEntry = std::pair<std::uint64_t, std::uint32_t>;

    using PriceLevels =
        std::map<std::int32_t, std::set<QueueEntry>>;

    std::map<std::uint32_t, Order> orders_;
    std::vector<Trade> trades_;
    std::set<std::uint32_t> used_ids_;

    PriceLevels bid_levels_;
    PriceLevels ask_levels_;

    std::uint64_t last_event_seq_;
    std::uint64_t next_trade_seq_;
    bool trade_sequence_exhausted_;

    EventResult rejected(
        std::uint64_t seq,
        const std::string& code
    ) const;

    static bool valid_client(const std::string& client);

    static std::int32_t checked_add(
        std::int32_t a,
        std::int32_t b
    );

    void add_to_book(const Order& order);
    void remove_from_book(const Order& order);

    std::vector<Trade> match(
        Order& incoming,
        bool market,
        std::uint64_t event_seq,
        std::map<std::uint32_t, Order>& rollback_orders
    );

    std::vector<Order> get_bids() const;
    std::vector<Order> get_asks() const;

    EventResult submit(
        std::uint64_t event_seq,
        std::uint32_t id,
        const std::string& client,
        Side side,
        OrderType type,
        std::optional<std::int32_t> price,
        std::int32_t qty
    );
};

}

#endif
