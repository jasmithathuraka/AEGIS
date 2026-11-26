
#include "exchange.hpp"

#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>

using json = nlohmann::json;
using Clock = std::chrono::steady_clock;

struct Event {
    std::string type;
    std::uint64_t seq;
    std::uint32_t id;
    std::string client;
    std::string side;
    std::int32_t price = 0;
    std::int32_t qty = 0;
};

static std::string side_name(aegis::Side side) {
    return side == aegis::Side::BUY ? "BUY" : "SELL";
}

static std::string type_name(aegis::OrderType type) {
    return type == aegis::OrderType::LIMIT ? "LIMIT" : "MARKET";
}

static std::string status_name(aegis::OrderStatus status) {
    switch (status) {
        case aegis::OrderStatus::ACTIVE: return "ACTIVE";
        case aegis::OrderStatus::PARTIAL: return "PARTIAL";
        case aegis::OrderStatus::FILLED: return "FILLED";
        case aegis::OrderStatus::CANCELLED: return "CANCELLED";
    }
    return "UNKNOWN";
}

int main(int argc, char* argv[]) {
    if (argc != 2) {
        std::cerr << "Usage: aegis_cpp_benchmark events.jsonl\n";
        return 1;
    }

    std::ifstream input(argv[1]);

    if (!input) {
        std::cerr << "Cannot open event file\n";
        return 1;
    }

    // Parse input before starting the engine timer.
    std::vector<Event> events;
    std::string line;
    std::uint64_t seq = 0;

    try {
        while (std::getline(input, line)) {
            if (line.empty()) continue;

            const json j = json::parse(line);

            Event e;
            e.type = j.at("type").get<std::string>();
            e.seq = ++seq;
            e.id = j.at("id").get<std::uint32_t>();
            e.client = j.at("client").get<std::string>();

            if (e.type != "CANCEL") {
                e.side = j.at("side").get<std::string>();
                e.qty = j.at("qty").get<std::int32_t>();

                if (e.type == "LIMIT") {
                    e.price = j.at("price").get<std::int32_t>();
                }
            }

            events.push_back(std::move(e));
        }
    } catch (const std::exception& e) {
        std::cerr << "Input error: " << e.what() << '\n';
        return 1;
    }

    aegis::Exchange exchange;

    const auto start = Clock::now();

    try {
        for (const Event& e : events) {
            if (e.type == "CANCEL") {
                (void)exchange.cancel(e.seq, e.id, e.client);
                continue;
            }

            const aegis::Side side =
                e.side == "BUY"
                    ? aegis::Side::BUY
                    : aegis::Side::SELL;

            if (e.type == "LIMIT") {
                (void)exchange.submit_limit(
                    e.seq, e.id, e.client,
                    side, e.price, e.qty
                );
            } else if (e.type == "MARKET") {
                (void)exchange.submit_market(
                    e.seq, e.id, e.client,
                    side, e.qty
                );
            } else {
                throw std::runtime_error("Unknown event type");
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Engine error: " << e.what() << '\n';
        return 1;
    }

    const auto finish = Clock::now();

    const double seconds =
        std::chrono::duration<double>(finish - start).count();

    // Construct output after timing has stopped.
    json output;
    output["elapsed_seconds"] = seconds;
    output["orders"] = json::array();
    output["trades"] = json::array();

    for (const auto& [id, order] : exchange.orders()) {
        output["orders"].push_back({
            {"id", id},
            {"client", order.client},
            {"side", side_name(order.side)},
            {"type", type_name(order.type)},
            {"price", order.price ? json(*order.price) : json(nullptr)},
            {"original_qty", order.original_qty},
            {"remaining_qty", order.remaining_qty},
            {"executed_qty", order.executed_qty},
            {"cancelled_qty", order.cancelled_qty},
            {"sequence", order.sequence},
            {"status", status_name(order.status)}
        });
    }

    for (const auto& trade : exchange.trades()) {
        output["trades"].push_back({
            {"trade_seq", trade.trade_seq},
            {"event_seq", trade.event_seq},
            {"buy_id", trade.buy_id},
            {"sell_id", trade.sell_id},
            {"qty", trade.qty},
            {"price", trade.price}
        });
    }

    std::cout << output.dump() << '\n';

    return 0;
}
