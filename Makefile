
.PHONY: test python-test cpp-test integration mutation benchmark clean

test: cpp-test python-test integration mutation

cpp-test:
	@echo "Building C++ engine tests..."
	clang++ -std=c++20 -Wall -Wextra -Wpedantic -O2 \
		-Icpp/include \
		cpp/src/exchange.cpp cpp/tests/test_exchange.cpp \
		-o cpp_exchange_tests
	./cpp_exchange_tests

python-test:
	PYTHONPATH=src pytest -v

integration:
	PYTHONPATH=src pytest \
		tests/test_cpp_jsonl.py \
		tests/test_cpp_adversarial.py \
		tests/test_adversarial_differential.py -v

mutation:
	PYTHONPATH=src python -c \
	'from aegis.mutation import run_mutation_tests, print_mutation_report; print_mutation_report(run_mutation_tests())'
	PYTHONPATH=src python benchmarks/cpp_mutation.py

benchmark:
	PYTHONPATH=src python benchmarks/benchmark.py

clean:
	rm -f cpp_exchange_tests aegis_cpp_jsonl aegis_cpp_benchmark
