
import json

from aegis.pipeline import (
    json_safe,
    run_pipeline,
)


def test_json_safe_converts_nested_data():
    result = json_safe({
        "events": [{"id": 1, "qty": 5}],
        "status": "ACCEPTED",
    })

    assert result["events"][0]["id"] == 1


def test_pipeline_generates_report(tmp_path):
    report = run_pipeline(
        seed=123,
        event_count=20,
        output_dir=tmp_path,
    )

    assert report["seed"] == 123
    assert report["generated_event_count"] == 20
    assert "mutation_score" in report


def test_pipeline_saves_report_file(tmp_path):
    run_pipeline(
        seed=456,
        event_count=10,
        output_dir=tmp_path,
    )

    report_file = tmp_path / "pipeline_report.json"

    assert report_file.exists()

    with report_file.open(encoding="utf-8") as file:
        saved_report = json.load(file)

    assert saved_report["project"] == "AEGIS"
    assert saved_report["seed"] == 456


def test_pipeline_saves_original_events(tmp_path):
    run_pipeline(
        seed=789,
        event_count=15,
        output_dir=tmp_path,
    )

    events_file = tmp_path / "original_events.jsonl"

    assert events_file.exists()

    lines = events_file.read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(lines) == 15

    for line in lines:
        assert isinstance(json.loads(line), dict)


def test_same_seed_generates_same_events(tmp_path):
    first = run_pipeline(
        seed=999,
        event_count=12,
        output_dir=tmp_path / "first",
    )

    second = run_pipeline(
        seed=999,
        event_count=12,
        output_dir=tmp_path / "second",
    )

    first_events = (
        tmp_path / "first" / "original_events.jsonl"
    ).read_text(encoding="utf-8")

    second_events = (
        tmp_path / "second" / "original_events.jsonl"
    ).read_text(encoding="utf-8")

    assert first_events == second_events
    assert first["seed"] == second["seed"]
