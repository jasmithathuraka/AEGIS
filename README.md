# AEGIS
### The Exchange That Hunts Its Own Bugs

**A deterministic electronic exchange and adversarial verification framework.**

[![C++20](https://img.shields.io/badge/C%2B%2B-20-00599C?logo=cplusplus)](https://isocpp.org/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Testing](https://img.shields.io/badge/Testing-Differential%20%7C%20Adversarial-8A6D45)](#verification-framework)
[![Deployment](https://img.shields.io/badge/Demo-Live-success)](https://aegis-lom5.onrender.com)

**[Live Demo](https://aegis-lom5.onrender.com) · [GitHub Repository](https://github.com/jasmithathuraka/AEGIS)**

---

## Overview

AEGIS is a miniature electronic exchange paired with an adversarial verification framework designed to expose, reproduce, and detect correctness bugs in exchange systems.

It combines independently implemented Python and C++ matching engines with deterministic event generation, invariant checking, differential testing, failure shrinking, mutation testing, and performance benchmarking.

The central idea is simple:

> An exchange should not just execute orders. It should be tested against the ways it can fail.

Rather than evaluating an implementation only through expected inputs, AEGIS deliberately exercises edge cases, compares independent implementations, and tests whether its verification framework can detect injected defects.

## System Architecture

AEGIS is organised around two cooperating components: the exchange engines and the verification framework.

```text
                         AEGIS
                           |
             +-------------+-------------+
             |                           |
       EXCHANGE ENGINES            VERIFICATION
             |                           |
       +-----+-----+          +----------+----------+
       |           |          |          |          |
     Python       C++     Invariant  Differential  Adversarial
     Engine      Engine   Checking    Testing      Testing
       |           |          |          |          |
       +-----+-----+          +----------+----------+
             |                           |
       Order Matching              Failure Shrinking
                                        |
                                  Mutation Testing
                                        |
                                  Test Reports
```

### Exchange engines

**Python engine**

An independent implementation of the exchange rules, used for execution and comparison during verification.

**C++ engine**

A C++20 implementation using an indexed order book and FIFO price-level queues, with rollback handling for tested internal failures.

Both engines implement the same documented exchange rules while maintaining separate implementations.

## Exchange Functionality

AEGIS supports:

- Limit and market orders
- Order cancellation
- Price-time priority
- Order matching and trade execution
- Self-trade prevention
- Order and trade state tracking

The exchange models the core behaviour of a simplified electronic limit order book.

## Verification Framework

The verification layer is the central feature of AEGIS. It evaluates not only whether the exchange works under normal conditions, but whether its behaviour remains correct under deliberately challenging event sequences.

### 1. Invariant Checking

Checks exchange-state properties, including:

- Quantity conservation
- Valid order quantities and statuses
- Valid order sides and prices
- Absence of crossed resting orders
- Trade consistency
- Consistency between executed order quantities and trade history

### 2. Deterministic Adversarial Testing

Generates reproducible event sequences to exercise exchange behaviour and expose edge cases.

Using deterministic seeds makes failing scenarios repeatable and easier to debug.

### 3. Differential Testing

Runs corresponding event sequences through the independent Python and C++ implementations and compares their resulting exchange states.

This helps identify behavioural disagreements that may not be caught by testing either implementation in isolation.

### 4. Failure Shrinking

Reduces failing event sequences into smaller reproductions.

The current shrinker uses chunk-based event removal followed by reduction of positive integer `price` and `qty` values.

It preserves a failure according to the supplied failure-checking callback; it does not guarantee a globally minimal sequence.

### 5. Mutation Testing

Introduces deliberate defects into exchange behaviour to evaluate whether the testing framework detects them.

The current C++ mutation suite detects all five implemented mutants:

| Injected defect | Result |
|---|---|
| Reversed FIFO priority | Detected |
| Incorrect execution price | Detected |
| Incorrect execution quantity | Detected |
| Cancellation leaves stale book entry | Detected |
| Self-trade prevention disabled | Detected |

**Current result: 5/5 implemented mutants detected (100%).**

This result applies only to the five implemented mutants, not every possible exchange defect.

## Testing

AEGIS includes unit, integration, adversarial, differential, randomized, and boundary-condition tests.

The latest full-suite result reported during development was:

**148 tests passed.**

Additional verification work includes:

- C++ engine and integration tests
- Independent reference-engine tests
- Randomized differential testing
- Randomized invariant checking
- Adversarial event-sequence testing
- Mutation testing
- Failure-shrinker tests

The randomized differential testing campaign compared implementations across 10 seeds and 500 generated events per seed.

The GitHub Actions workflow runs the project's automated test workflow on pushes and pull requests.

## Performance Benchmarking

AEGIS includes a deterministic benchmark comparing the Python and C++ exchange implementations.

### Methodology

- Deterministic generated workloads using seed `42`
- Two warm-up runs per implementation
- Seven measured repetitions per workload
- Median execution time reported
- Alternating execution order between Python and C++
- Event generation and JSON input parsing excluded from timing
- Final order state and trade history compared for correctness

### Observed Results

| Events | Python median | C++ median | Observed ratio |
|---:|---:|---:|---:|
| 1,000 | 0.016041 s | 0.000306 s | 52.36× |
| 5,000 | 0.345453 s | 0.001589 s | 217.36× |
| 10,000 | 1.364677 s | 0.003332 s | 409.60× |

All three workloads completed with matching final exchange states.

**Benchmark limitations:** These measurements compare the current implementations, not universally equivalent workloads. Python constructs event-result objects and dictionary-based order updates, while the C++ benchmark constructs full order-update objects. The benchmark compares complete final states rather than every intermediate event result.

The observed ratios are implementation-specific measurements, not universal performance claims.

## Technology Stack

| Component | Technology |
|---|---|
| Exchange engine | C++20 |
| Independent implementation | Python 3.12 |
| API backend | FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Testing | pytest, C++ tests |
| Benchmarking | Python and C++ |
| Build | GNU Make, g++ |
| Deployment | Docker, Render |
| CI | GitHub Actions |

## Project Structure

```text
AEGIS/
├── .github/
│   └── workflows/
├── backend/
├── benchmarks/
│   ├── benchmark.py
│   └── cpp_mutation.py
├── bugs/
├── cpp/
│   ├── include/
│   ├── src/
│   └── tests/
├── docs/
├── frontend/
├── src/
│   └── aegis/
│       ├── exchange.py
│       ├── invariants.py
│       ├── generator.py
│       ├── shrinker.py
│       ├── runner.py
│       ├── mutation.py
│       ├── pipeline.py
│       ├── differential.py
│       └── reference.py
├── tests/
├── Dockerfile
├── Makefile
├── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.12
- A C++20-compatible compiler
- GNU Make
- `nlohmann/json` headers for C++ JSONL integration tests

### Clone the repository

```bash
git clone https://github.com/jasmithathuraka/AEGIS.git
cd AEGIS
```

### Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
```

On macOS with Homebrew, install the JSON library if needed:

```bash
brew install nlohmann-json
```

### Run the test suite

```bash
make test
```

Alternatively, run the Python suite independently:

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

## Continuous Integration

AEGIS uses GitHub Actions to execute its automated test workflow on pushes and pull requests.

The workflow builds and tests the C++ engine, runs the Python and integration test suite, and executes the C++ mutation tests.

## Design Principles

- **Correctness before performance:** Validate exchange behaviour before optimising it.
- **Reproducibility:** Make failures reproducible from deterministic event sequences.
- **Independent implementations:** Use separate Python and C++ engines for differential verification.
- **Adversarial thinking:** Test deliberate failure modes rather than only expected inputs.
- **Evidence over claims:** Report measured results alongside their limitations.

## Future Improvements

- Broader mutation operators and branch coverage
- Stronger intermediate-event differential comparisons
- More representative, workload-equivalent benchmarks
- Additional documented minimal bug reproductions
- Further optimisation of exchange operations

---

**AEGIS — Building an exchange that doesn't just work, but actively hunts for the ways it could fail.**