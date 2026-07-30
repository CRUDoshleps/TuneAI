from app.schemas import EvaluationResult


def test_ai_readiness_discloses_mock_mode(client):
    response = client.get("/readiness/ai")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["mode"] == "mock"
    assert payload["configured"] is True
    assert payload["provider"] == "Mock AI"
    assert {"Mock evaluation", "RAG"} <= set(payload["capabilities"])
    assert "Демонстрационный режим" in payload["disclosure"]


def test_evaluation_score_is_clamped_to_rubric_maximum():
    result = EvaluationResult(
        score=42,
        max_score=10,
        correct_points=["Тезис раскрыт"],
        feedback="Ответ проверен.",
        recommendations="Добавить пример.",
        confidence=0.9,
        source_excerpts=["  Фрагмент материала  "],
    )

    assert result.score == 10
    assert result.source_excerpts == ["Фрагмент материала"]


def test_evaluation_limits_source_excerpts_for_safe_report_size():
    result = EvaluationResult(
        score=5,
        max_score=10,
        feedback="Ответ частичный.",
        recommendations="Повторить тему.",
        confidence=0.5,
        source_excerpts=["A" * 700, "B", "C", "D"],
    )

    assert len(result.source_excerpts) == 3
    assert len(result.source_excerpts[0]) == 600
