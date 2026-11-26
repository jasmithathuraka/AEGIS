
#include "exchange.hpp"

#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace aegis {

struct ExchangeTestAccess {
    static void exhaust_trade_sequence(Exchange& exchange) {
        exchange.trade_sequence_exhausted_ = true;
    }
};

}

using namespace aegis;

int checks = 0;
int failures = 0;

void check(bool condition, const std::string& name) {
    ++checks;

    if (condition) {
        std::cout << "PASSED: " << name << '\n';
    } else {
        ++failures;
        std::cout << "FAILED: " << name << '\n';
    }
}

void test_overflow_rolls_back_event() {
    Exchange exchange;

    exchange.submit_limit(
        1, 1, "seller", Side::SELL, 100, 10
    );

    const auto original_order = exchange.orders().at(1);
    const auto original_trade_count = exchange.trades().size();

    ExchangeTestAccess::exhaust_trade_sequence(exchange);

    bool overflow_detected = false;

    try {
        exchange.submit_limit(
            2, 2, "buyer", Side::BUY, 100, 5
        );
    } catch (const std::overflow_error& error) {
        overflow_detected =
            std::string(error.what()) == "ARITHMETIC_OVERFLOW";
    }

    check(overflow_detected, "trade sequence exhaustion detected");

    check(
        exchange.orders().at(1).remaining_qty ==
            original_order.remaining_qty,
        "resting order unchanged after overflow"
    );

    check(
        exchange.orders().at(1).executed_qty ==
            original_order.executed_qty,
        "resting executed quantity unchanged after overflow"
    );

    check(
        exchange.orders().count(2) == 0,
        "incoming order not committed after overflow"
    );

    check(
        exchange.trades().size() == original_trade_count,
        "trade history unchanged after overflow"
    );
}

void test_maximum_quantity_conservation() {
    Exchange exchange;

    const auto maximum =
        std::numeric_limits<std::int32_t>::max();

    exchange.submit_limit(
        1, 1, "seller", Side::SELL, 100, maximum
    );

    auto result = exchange.submit_market(
        2, 2, "buyer", Side::BUY, maximum
    );

    const auto& seller = exchange.orders().at(1);
    const auto& buyer = exchange.orders().at(2);

    check(result.trades.size() == 1,
          "maximum quantity trade executes");

    check(result.trades[0].qty == maximum,
          "maximum quantity is preserved");

    check(
        seller.remaining_qty == 0 &&
        seller.executed_qty == maximum,
        "maximum seller quantity conserved"
    );

    check(
        buyer.remaining_qty == 0 &&
        buyer.executed_qty == maximum,
        "maximum buyer quantity conserved"
    );
}

int main() {
    test_overflow_rolls_back_event();
    test_maximum_quantity_conservation();

    std::cout << "\n" << checks << " checks run, "
              << failures << " failed.\n";

    return failures == 0 ? 0 : 1;
}
