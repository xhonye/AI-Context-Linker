from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ai_context_linker.blind_evaluation import evaluate_blind_run, freeze_blind_run
from ai_context_linker.core import ManifestError


QUESTIONS = tuple(f"Q{index}" for index in range(1, 7))
ORDERS = ("order-ab", "order-ba")


def _protocol() -> dict:
    return {
        "questions": {question: f"Synthetic question {question}." for question in QUESTIONS},
        "dimensions": ["grounding", "uncertainty"],
        "rubric": {str(score): f"Synthetic score {score}." for score in range(5)},
    }


def _response() -> dict:
    return {
        "conditions": {
            condition: {
                question: {
                    "answer": "SYNTHETIC_RAW_ANSWER_MUST_NOT_APPEAR",
                    "scores": {"grounding": 3, "uncertainty": 4},
                    "failures": ["SYNTHETIC_FAILURE_NOTE_MUST_NOT_APPEAR"],
                }
                for question in QUESTIONS
            }
            for condition in ("A", "B")
        },
        "winner_q6": "tie",
        "limitations": ["SYNTHETIC_LIMITATION_MUST_NOT_APPEAR"],
    }


def _run(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    run_dir = tmp_path / "blind-run"
    freeze_blind_run(run_dir, protocol=_protocol(), conditions={"A": "Synthetic context A.", "B": "Synthetic context B."})
    responses = {order: run_dir / f"{order}.json" for order in ORDERS}
    for index, path in enumerate(responses.values()):
        path.write_text(json.dumps(_response()) + "\n" * index, encoding="utf-8")
    return run_dir, responses


def test_frozen_run_audit_is_deterministic_and_contains_no_raw_prose_or_paths(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)

    report = evaluate_blind_run(run_dir, responses=responses)
    serialized = json.dumps(report)

    assert report == evaluate_blind_run(run_dir, responses=responses)
    assert report["replacement_ready"] is False
    assert report["scope"] == "local-subagent-diagnostic"
    assert report["both_orders_present"] is True
    assert report["model_settings_verified"] is False
    assert report["origin_verified"] is False
    assert report["truth_verified"] is False
    assert set(report["answer_sha256"]) == set(ORDERS)
    assert set(report["questions"]) == set(QUESTIONS)
    assert "SYNTHETIC_RAW" not in serialized
    assert "SYNTHETIC_FAILURE" not in serialized
    assert "SYNTHETIC_LIMITATION" not in serialized
    assert "Synthetic question" not in serialized
    assert str(tmp_path) not in serialized
    assert "order-ab.json" not in serialized


def test_freeze_refuses_existing_directory(tmp_path: Path) -> None:
    run_dir, _ = _run(tmp_path)

    with pytest.raises(ManifestError, match="exist"):
        freeze_blind_run(run_dir, protocol=_protocol(), conditions={"A": "A", "B": "B"})


@pytest.mark.parametrize("filename", ["condition-a.md", "condition-b.md", "protocol.json"])
def test_frozen_input_tampering_is_rejected(tmp_path: Path, filename: str) -> None:
    run_dir, responses = _run(tmp_path)
    with (run_dir / filename).open("a", encoding="utf-8") as handle:
        handle.write("\nChanged")

    with pytest.raises(ManifestError, match="hash"):
        evaluate_blind_run(run_dir, responses=responses)


def test_response_path_cannot_escape_run_directory(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(_response()), encoding="utf-8")
    responses["order-ab"] = outside

    with pytest.raises(ManifestError, match="inside"):
        evaluate_blind_run(run_dir, responses=responses)


def test_link_or_reparse_response_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir, responses = _run(tmp_path)
    target = responses["order-ab"]
    monkeypatch.setattr("ai_context_linker.blind_evaluation.is_link_or_reparse", lambda path: path == target)

    with pytest.raises(ManifestError, match="link|reparse"):
        evaluate_blind_run(run_dir, responses=responses)


def test_link_or_reparse_parent_is_rejected_before_freeze(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ai_context_linker.blind_evaluation.is_link_or_reparse", lambda path: path == tmp_path)

    with pytest.raises(ManifestError, match="link|reparse"):
        freeze_blind_run(tmp_path / "run", protocol=_protocol(), conditions={"A": "A", "B": "B"})
    assert not (tmp_path / "run").exists()


def test_missing_question_is_rejected(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    raw = _response()
    del raw["conditions"]["A"]["Q6"]
    responses["order-ab"].write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ManifestError, match="Q1.*Q6|questions"):
        evaluate_blind_run(run_dir, responses=responses)


@pytest.mark.parametrize("score", [True, -1, 5, 3.5, "4"])
def test_invalid_dimension_score_is_rejected(tmp_path: Path, score: object) -> None:
    run_dir, responses = _run(tmp_path)
    raw = _response()
    raw["conditions"]["B"]["Q3"]["scores"]["grounding"] = score
    responses["order-ba"].write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ManifestError, match="score"):
        evaluate_blind_run(run_dir, responses=responses)


def test_both_orders_and_distinct_response_files_are_required(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)

    with pytest.raises(ManifestError, match="orders"):
        evaluate_blind_run(run_dir, responses={"order-ab": responses["order-ab"]})
    with pytest.raises(ManifestError, match="distinct"):
        evaluate_blind_run(run_dir, responses={order: responses["order-ab"] for order in ORDERS})


def test_order_disagreement_is_reported_without_judge_prose(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    raw = _response()
    raw["conditions"]["A"]["Q6"]["scores"]["grounding"] = 1
    raw["winner_q6"] = "B"
    responses["order-ba"].write_text(json.dumps(raw), encoding="utf-8")

    report = evaluate_blind_run(run_dir, responses=responses)

    assert report["questions"]["Q6"]["order_disagreement"] is True
    assert report["questions"]["Q1"]["order_disagreement"] is False
    assert report["winner_q6_disagreement"] is True
    assert report["questions"]["Q6"]["scores_by_order"]["order-ba"]["A"]["grounding"] == 1


def test_context_privacy_and_protocol_mapping_fields_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="absolute path"):
        freeze_blind_run(tmp_path / "unsafe", protocol=_protocol(), conditions={"A": "C:/Users/example/private", "B": "Safe"})
    protocol = _protocol()
    protocol["private_mapping"] = {"A": "Generator one"}
    with pytest.raises(ManifestError, match="protocol"):
        freeze_blind_run(tmp_path / "mapping", protocol=protocol, conditions={"A": "Safe", "B": "Safe"})
    assert not (tmp_path / "unsafe").exists()
    assert not (tmp_path / "mapping").exists()


def test_oversized_response_is_rejected_before_parsing(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    responses["order-ab"].write_bytes(b"x" * (2 * 1024 * 1024 + 1))

    with pytest.raises(ManifestError, match="byte limit"):
        evaluate_blind_run(run_dir, responses=responses)


@pytest.mark.parametrize("field", ["questions", "dimensions", "rubric"])
def test_incomplete_protocol_is_rejected(tmp_path: Path, field: str) -> None:
    protocol = _protocol()
    del protocol[field]

    with pytest.raises(ManifestError, match="protocol"):
        freeze_blind_run(tmp_path / "incomplete", protocol=protocol, conditions={"A": "A", "B": "B"})


def test_frozen_hashes_bind_canonical_protocol_and_exact_context_bytes(tmp_path: Path) -> None:
    protocol = _protocol()
    contexts = {"A": "Synthetic line one.\r\nSynthetic Unicode 文本.", "B": "Synthetic B.\n"}
    first = freeze_blind_run(tmp_path / "first", protocol=protocol, conditions=contexts)
    reversed_protocol = {key: protocol[key] for key in reversed(protocol)}
    second = freeze_blind_run(tmp_path / "second", protocol=reversed_protocol, conditions=contexts)
    frozen = json.loads(first.read_text(encoding="utf-8"))
    canonical = json.dumps(protocol, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    assert first.read_bytes() == second.read_bytes()
    assert frozen["protocol_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert (first.parent / "protocol.json").read_bytes() == canonical
    for condition, context in contexts.items():
        assert frozen["context_sha256"][condition] == hashlib.sha256(context.encode("utf-8")).hexdigest()
        assert (first.parent / f"condition-{condition.lower()}.md").read_bytes() == context.encode("utf-8")


def test_audit_hashes_raw_response_bytes_not_reencoded_json(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    raw = json.dumps(_response(), indent=4).encode("utf-8") + b"\n\n"
    responses["order-ab"].write_bytes(raw)

    report = evaluate_blind_run(run_dir, responses=responses)

    assert report["answer_sha256"]["order-ab"] == hashlib.sha256(raw).hexdigest()


def test_duplicate_json_fields_are_rejected(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    duplicate = '{"conditions": {},' + json.dumps(_response())[1:]
    responses["order-ab"].write_text(duplicate, encoding="utf-8")

    with pytest.raises(ManifestError, match="duplicate JSON"):
        evaluate_blind_run(run_dir, responses=responses)


def test_two_hardlinked_response_names_are_not_independent_files(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    alias = run_dir / "same-response-alias.json"
    alias.hardlink_to(responses["order-ab"])
    responses["order-ba"] = alias

    with pytest.raises(ManifestError, match="distinct"):
        evaluate_blind_run(run_dir, responses=responses)


def test_unknown_frozen_index_fields_are_rejected(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    path = run_dir / "frozen-inputs.json"
    index = json.loads(path.read_text(encoding="utf-8"))
    index["private_mapping"] = {"A": "Generator one"}
    path.write_text(json.dumps(index), encoding="utf-8")

    with pytest.raises(ManifestError, match="frozen input index"):
        evaluate_blind_run(run_dir, responses=responses)


def test_missing_dimension_and_invalid_failures_shape_are_rejected(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    raw = _response()
    del raw["conditions"]["A"]["Q1"]["scores"]["grounding"]
    responses["order-ab"].write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ManifestError, match="scores"):
        evaluate_blind_run(run_dir, responses=responses)
    raw = _response()
    raw["conditions"]["A"]["Q1"]["failures"] = "not a list"
    responses["order-ab"].write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ManifestError, match="failures"):
        evaluate_blind_run(run_dir, responses=responses)


def test_winner_object_preserves_raw_hash_and_exports_only_label(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    raw = _response()
    raw["winner_q6"] = {
        "condition": "A",
        "reason": "SYNTHETIC_WINNER_REASON_MUST_NOT_APPEAR",
        "confidence": "SYNTHETIC_CONFIDENCE_MUST_NOT_APPEAR",
    }
    encoded = json.dumps(raw, indent=2).encode("utf-8") + b"\n"
    responses["order-ab"].write_bytes(encoded)

    report = evaluate_blind_run(run_dir, responses=responses)

    assert report["winner_q6_by_order"]["order-ab"] == "A"
    assert report["answer_sha256"]["order-ab"] == hashlib.sha256(encoded).hexdigest()
    assert report["answer_bytes"]["order-ab"] == len(encoded)
    assert report["answer_bytes"]["order-ba"] == len(responses["order-ba"].read_bytes())
    assert "SYNTHETIC_WINNER_REASON" not in json.dumps(report)
    assert "SYNTHETIC_CONFIDENCE" not in json.dumps(report)
    assert responses["order-ab"].read_bytes() == encoded


@pytest.mark.parametrize(
    "winner",
    [{"reason": "Missing condition"}, {"condition": "A", "extra": "No"}, {"condition": "A", "reason": 1}, {"condition": "A", "confidence": False}],
)
def test_winner_object_rejects_unknown_fields_and_nonstring_notes(tmp_path: Path, winner: dict) -> None:
    run_dir, responses = _run(tmp_path)
    raw = _response()
    raw["winner_q6"] = winner
    responses["order-ab"].write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ManifestError, match="winner_q6"):
        evaluate_blind_run(run_dir, responses=responses)


def test_distinct_response_paths_cannot_replay_identical_raw_bytes(tmp_path: Path) -> None:
    run_dir, responses = _run(tmp_path)
    responses["order-ba"].write_bytes(responses["order-ab"].read_bytes())

    with pytest.raises(ManifestError, match="replay|identical|distinct"):
        evaluate_blind_run(run_dir, responses=responses)
