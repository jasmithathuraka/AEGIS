# AEGIS
### The Exchange That Hunts Its Own Bugs

AEGIS is a miniature electronic exchange paired with an adversarial verification framework designed to expose, reproduce, and detect correctness bugs in exchange systems.

It combines two independent exchange implementations — Python and C++ — with automated testing, differential verification, invariant checking, mutation testing, and performance benchmarking.

The central idea is simple:

**An exchange should not just execute orders. It should be tested against the ways it can fail.**

---

## Overview

AEGIS explores the engineering challenges behind a simplified electronic limit order book.

The exchange supports:

- Limit and market orders
- Order cancellation
- Price-time priority
- Order matching and trade execution
- Self-trade prevention
- Order and trade state tracking

The project goes beyond implementing exchange functionality. It includes a separate testing framework that generates event sequences, checks exchange invariants, compares implementations, and evaluates whether tests can detect deliberately introduced bugs.

## Architecture

```text
                         AEGIS
                           |
             +-------------+-------------+
             |                           |
       Exchange Engines            Verification Layer
             |                           |
       +-----+-----+             +-------+--------+
       |           |             |       |        |
     Python       C++         Invariant Differential
     Engine      Engine        Checking   Testing
       |           |                 |
       +-----+-----+                 |
             |                       |
       Event Processing        Adversarial Testing
                                     |
                            +--------+--------+
                            |                 |
                         Shrinker        Mutation Testing
                            |                 |
                            +--------+--------+
                                     |
                                Test Reports
```

### Exchange implementations

**Python engine**

Provides an implementation of the exchange logic and serves as one side of differential testing.

**C++ engine**

Provides an independently implemented exchange engine with an indexed order book and rollback handling for tested internal failures.

Both implementations follow the same documented exchange rules.

---

## Verification and Testing

### 1. Invariant checking

The verification layer checks properties of the exchange state, including:

- Quantity conservation
- Valid order quantities and statuses
- Valid order sides and prices
- No crossed resting order book
- Trade consistency
- Executed quantity consistency between orders and trades

### 2. Adversarial testing

Generates event sequences designed to exercise exchange behaviour and expose edge cases.

### 3. Differential testing

Runs corresponding scenarios through the Python and C++ implementations and compares their resulting exchange states.

### 4. Failure shrinking

Reduces failing event sequences to smaller reproductions, making bugs easier to understand and debug.

### 5. Mutation testing

Introduces deliberate defects into exchange behaviour to evaluate whether the testing framework detects them.

The C++ mutation suite currently detects all five implemented mutants.

| Mutation | Detection |
|---|---|
| Reversed FIFO priority | Detected |
| Incorrect execution price | Detected |
| Incorrect execution quantity | Detected |
| Cancellation leaves stale book entry | Detected |
| Self-trade prevention disabled | Detected |

**C++ mutation result: 5/5 detected (100%).**

This score applies to the five implemented mutants, not every possible exchange defect.

---

## Testing Results

The following results were observed during local testing:

| Test suite | Result |
|---|---:|
| C++ engine tests | 9 passed |
| Python test suite, including integration tests | 105 passed |
| C++ integration, adversarial and differential tests | 31 passed |
| C++ mutation tests | 5/5 detected |

The GitHub Actions CI workflow also completed successfully.

---

## Performance Benchmarking

AEGIS includes a benchmark comparing the Python and C++ exchange implementations over deterministic generated event workloads.

### Methodology

- Deterministic workloads generated using seed 42.
- Two warm-up runs per implementation.
- Seven measured repetitions per workload.
- Median execution time reported.
- Execution order alternates between Python and C++.
- Event generation and JSON input parsing are excluded from timing.
- Complete final order state and trade history are compared.

### Observed Results

| Events | Python median | C++ median | Observed ratio |
|---:|---:|---:|---:|
| 1,000 | 0.016041 s | 0.000306 s | 52.36× |
| 5,000 | 0.345453 s | 0.001589 s | 217.36× |
| 10,000 | 1.364677 s | 0.003332 s | 409.60× |

All three workloads completed with matching final exchange states.

**Limitations:** These measurements compare the current Python and C++ implementations, not universally equivalent workloads. Python constructs event-result objects and dictionary-based order updates, while the C++ benchmark constructs full order-update objects. The benchmark compares complete final states rather than every intermediate event result.

The observed ratios should therefore be treated as implementation-specific measurements, not universal performance claims.

---

## Project Structure

```text
AEGIS/
├── .github/
│   └── workflows/
│       └── tests.yml
├── benchmarks/
│   ├── benchmark.py
│   └── cpp_mutation.py
├── bugs/
│   ├── README.md
│   └── mutation-cases.md
├── cpp/
│   ├── include/
│   ├── src/
│   └── tests/
├── docs/
│   └── exchange_rules.md
├── src/
│   └── aegis/
│       ├── exchange.py
│       ├── differential.py
│       ├── generator.py
│       ├── invariants.py
│       ├── mutation.py
│       ├── parser.py
│       ├── pipeline.py
│       ├── runner.py
│       └── shrinker.py
├── tests/
├── Makefile
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.12
- pytest
- A C++20-compatible compiler
- nlohmann/json headers for the C++ JSONL integration tests
- GNU Make

### Setup

Clone the repository:

```bash
git clone https://github.com/jasmithathuraka/AEGIS.git
cd AEGIS
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the Python test dependency:

```bash
python -m pip install pytest
```

On macOS with Homebrew, install the JSON library if needed:

```bash
brew install nlohmann-json
```

### Run tests

Run the complete project test target:

```bash
make test
```

Run the Python suite independently:

```bash
PYTHONPATH=src pytest -v
```

### Run mutation tests

```bash
PYTHONPATH=src python benchmarks/cpp_mutation.py
```

### Run benchmarks

```bash
PYTHONPATH=src python benchmarks/benchmark.py
```

---

## Continuous Integration

AEGIS uses GitHub Actions to automatically execute its test workflow on pushes and pull requests.

The CI workflow builds and tests the C++ engine, runs the Python and integration test suite, and executes the C++ mutation tests.

---

## Design Principles

- **Correctness before performance:** Validate exchange behaviour before optimising it.
- **Reproducibility:** Make failures reproducible from event sequences.
- **Independent implementations:** Use separate Python and C++ engines to enable differential verification.
- **Adversarial thinking:** Test deliberate failure modes rather than only expected inputs.
- **Evidence over claims:** Report measured results with their limitations.

---

## Future Improvements

- More comprehensive mutation operators and branch coverage.
- Stronger intermediate-event differential comparisons.
- More representative, workload-equivalent performance benchmarks.
- Additional documented minimal bug reproductions.
- Further optimisation of exchange operations.

---

**AEGIS — Building an exchange that doesn't just work, but actively hunts for the ways it could fail.**