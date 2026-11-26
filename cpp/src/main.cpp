
#include "exchange.hpp"

#include <cstdint>
#include <exception>
#include <iostream>
#include <limits>
#include <set>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

using json = nlohmann::json;

namespace {

bool valid_client(const std::string& client) {
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

bool get_integer(const json& value, std::int64_t& output) {
    if (value.is_number_unsigned()) {
        const auto number = value.get<std::uint64_t>();

        if (number > static_cast<std::uint64_t>(
                std::numeric_limits<std::int64_t>::max())) {
            return false;
        }

        output = static_cast<std::int64_t>(number);
        return true;
    }

    if (value.is_number_integer()) {
        output = value.get<std::int64_t>();
        return true;
    }

    return false;
}

bool has_exact_fields(
    const json& event,
    std::initializer_list<const char*> fields
) {
    if (!event.is_object() || event.size() != fields.size()) {
        return false;
    }

    for (const char* field : fields) {
        if (!event.contains(field)) {
            return false;
        }
    }

    return true;
}

json order_json(const aegis::Order& order) {
    return {
        {"id", order.id},
        {"remaining_qty", order.remaining_qty},
        {"executed_qty", order.executed_qty},
        {"cancelled_qty", order.cancelled_qty},
        {"status",
            order.status == aegis::OrderStatus::ACTIVE ? "ACTIVE" :
            order.status == aegis::OrderStatus::PARTIAL ? "PARTIAL" :
            order.status == aegis::OrderStatus::FILLED ? "FILLED" :
            "CANCELLED"}
    };
}

json result_json(const aegis::EventResult& result) {
    json trades = json::array();
    json updates = json::array();

    for (const auto& trade : result.trades) {
        trades.push_back({
            {"trade_seq", trade.trade_seq},
            {"event_seq", trade.event_seq},
            {"buy_id", trade.buy_id},
            {"sell_id", trade.sell_id},
            {"qty", trade.qty},
            {"price", trade.price}
        });
    }

    for (const auto& order : result.order_updates) {
        updates.push_back(order_json(order));
    }

    return {
        {"seq", result.seq},
        {"status", result.status},
        {"reject_code",
            result.status == "ACCEPTED"
                ? json(nullptr)
                : json(result.reject_code)},
        {"trades", trades},
        {"order_updates", updates}
    };
}

void print_rejection(
    std::uint64_t seq,
    const std::string& code
) {
    std::cout << json({
        {"seq", seq},
        {"status", "REJECTED"},
        {"reject_code", code},
        {"trades", json::array()},
        {"order_updates", json::array()}
    }).dump() << '\n';
}

}

int main() {
    aegis::Exchange exchange;

    std::string line;
    std::uint64_t physical_seq = 0;

    while (std::getline(std::cin, line)) {
        if (physical_seq ==
            std::numeric_limits<std::uint64_t>::max()) {
            std::cerr << "ARITHMETIC_OVERFLOW\n";
            return 1;
        }

        ++physical_seq;

        try {
            if (line.find_first_not_of(" \t\r") ==
                std::string::npos) {
                print_rejection(physical_seq, "MALFORMED_EVENT");
                continue;
            }

            json event;

            try {
                std::vector<std::set<std::string>> object_keys;

                auto callback = [&object_keys](
                    int,
                    json::parse_event_t parse_event,
                    json& parsed
                ) -> bool {
                    if (parse_event == json::parse_event_t::object_start) {
                        object_keys.emplace_back();
                    } else if (parse_event == json::parse_event_t::key) {
                        if (
                            object_keys.empty() ||
                            !object_keys.back().insert(
                                parsed.get<std::string>()
                            ).second
                        ) {
                            throw std::runtime_error("DUPLICATE_KEY");
                        }
                    } else if (parse_event == json::parse_event_t::object_end) {
                        if (!object_keys.empty()) {
                            object_keys.pop_back();
                        }
                    }

                    return true;
                };

                event = json::parse(line, callback);

            } catch (const std::exception&) {
                print_rejection(physical_seq, "MALFORMED_EVENT");
                continue;
            }

            if (
                !event.is_object() ||
                !event.contains("type") ||
                !event["type"].is_string()
            ) {
                print_rejection(physical_seq, "MALFORMED_EVENT");
                continue;
            }

            const std::string type =
                event["type"].get<std::string>();

            if (type == "LIMIT") {
                if (!has_exact_fields(
                    event,
                    {"type", "id", "client", "side", "price", "qty"}
                )) {
                    print_rejection(physical_seq, "MALFORMED_EVENT");
                    continue;
                }
            } else if (type == "MARKET") {
                if (!has_exact_fields(
                    event,
                    {"type", "id", "client", "side", "qty"}
                )) {
                    print_rejection(physical_seq, "MALFORMED_EVENT");
                    continue;
                }
            } else if (type == "CANCEL") {
                if (!has_exact_fields(
                    event,
                    {"type", "id", "client"}
                )) {
                    print_rejection(physical_seq, "MALFORMED_EVENT");
                    continue;
                }
            } else {
                print_rejection(physical_seq, "INVALID_TYPE");
                continue;
            }

            if (!event["client"].is_string()) {
                print_rejection(physical_seq, "INVALID_CLIENT");
                continue;
            }

            const std::string client =
                event["client"].get<std::string>();

            if (!valid_client(client)) {
                print_rejection(physical_seq, "INVALID_CLIENT");
                continue;
            }

            std::int64_t id_value = 0;

            if (
                !get_integer(event["id"], id_value) ||
                id_value < 1 ||
                id_value > std::numeric_limits<std::uint32_t>::max()
            ) {
                print_rejection(physical_seq, "INVALID_ID");
                continue;
            }

            const auto id =
                static_cast<std::uint32_t>(id_value);

            if (type == "CANCEL") {
                auto result = exchange.cancel(
                    physical_seq,
                    id,
                    client
                );

                std::cout << result_json(result).dump() << '\n';
                continue;
            }

            if (!event["side"].is_string()) {
                print_rejection(physical_seq, "INVALID_SIDE");
                continue;
            }

            const std::string side_text =
                event["side"].get<std::string>();

            aegis::Side side;

            if (side_text == "BUY") {
                side = aegis::Side::BUY;
            } else if (side_text == "SELL") {
                side = aegis::Side::SELL;
            } else {
                print_rejection(physical_seq, "INVALID_SIDE");
                continue;
            }

            std::int64_t price_value = 0;

            if (type == "LIMIT") {
                if (
                    !get_integer(event["price"], price_value) ||
                    price_value < 1 ||
                    price_value >
                        std::numeric_limits<std::int32_t>::max()
                ) {
                    print_rejection(physical_seq, "INVALID_PRICE");
                    continue;
                }
            }

            std::int64_t qty_value = 0;

            if (
                !get_integer(event["qty"], qty_value) ||
                qty_value < 1 ||
                qty_value >
                    std::numeric_limits<std::int32_t>::max()
            ) {
                print_rejection(physical_seq, "INVALID_QUANTITY");
                continue;
            }

            aegis::EventResult result;

            if (type == "LIMIT") {
                result = exchange.submit_limit(
                    physical_seq,
                    id,
                    client,
                    side,
                    static_cast<std::int32_t>(price_value),
                    static_cast<std::int32_t>(qty_value)
                );
            } else {
                result = exchange.submit_market(
                    physical_seq,
                    id,
                    client,
                    side,
                    static_cast<std::int32_t>(qty_value)
                );
            }

            std::cout << result_json(result).dump() << '\n';

        } catch (const std::overflow_error&) {
            std::cerr << "ARITHMETIC_OVERFLOW\n";
            return 1;

        } catch (const std::exception&) {
            print_rejection(physical_seq, "MALFORMED_EVENT");
        }
    }

    return 0;
}
