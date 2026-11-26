
from aegis.mutation import (
    MUTANTS,
    make_events,
    run_correct_engine,
    run_mutation_tests,
)
from aegis.invariants import check_exchange


def test_correct_engine_passes_invariants():
    exchange = run_correct_engine(make_events())
    assert check_exchange(exchange).violations == []


def test_mutants_are_registered():
    assert len(MUTANTS) == 5


def test_mutation_report_contains_all_mutants():
    report = run_mutation_tests()
    assert report.total == 5
    assert len(report.results) == 5


def test_mutation_report_is_reproducible():
    first = run_mutation_tests()
    second = run_mutation_tests()
    assert first.results == second.results


def test_mutation_score_is_valid():
    report = run_mutation_tests()
    assert 0 <= report.score <= 100


def test_mutation_results_have_names():
    report = run_mutation_tests()
    assert all(result.name for result in report.results)


def test_mutation_results_have_boolean_status():
    report = run_mutation_tests()
    assert all(
        isinstance(result.detected, bool)
        for result in report.results
    )
