from app.services.moderation import censor_text
from app.tests.conftest import auth_header, register_and_login


def test_censor_text_masks_russian_profanity_and_keeps_regular_words():
    assert censor_text("Блять, что за хуйня?") == "*****, что за *****?"
    assert censor_text("хуйхуй") == "******"
    assert censor_text("сосал") == "*****"
    assert censor_text("Учебный процесс и хлеб полезны.") == "Учебный процесс и хлеб полезны."


def test_test_creation_censors_russian_profanity(client):
    admin_token = register_and_login(client, "admin@example.com")

    response = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Блять сложный тест",
            "description": "Описание с пиздецом",
            "test_type": "self_training",
            "criteria": {"rubric": ["Не ебать формулировки"]},
            "questions": [
                {
                    "text": "Что за хуйня происходит?",
                    "expected_answer": "Ответ без блядства.",
                    "order_index": 0,
                    "max_score": 10,
                }
            ],
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["title"] == "***** сложный тест"
    assert payload["description"] == "Описание с ********"
    assert payload["criteria"] == {"rubric": ["Не ***** формулировки"]}
    assert payload["questions"][0]["text"] == "Что за ***** происходит?"
    assert payload["questions"][0]["expected_answer"] == "Ответ без ********."


def test_test_update_censors_russian_profanity(client):
    admin_token = register_and_login(client, "admin@example.com")
    created = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Clean title",
            "test_type": "self_training",
            "questions": [{"text": "Clean question?", "max_score": 10}],
        },
    )
    assert created.status_code == 201, created.text
    test_id = created.json()["id"]

    updated = client.patch(
        f"/tests/{test_id}",
        headers=auth_header(admin_token),
        json={
            "title": "Пиздец тест",
            "description": "Ёбаный кейс",
            "criteria": {"note": "заебал повтор"},
        },
    )

    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["title"] == "****** тест"
    assert payload["description"] == "****** кейс"
    assert payload["criteria"] == {"note": "****** повтор"}


def test_question_creation_censors_russian_profanity(client):
    admin_token = register_and_login(client, "admin@example.com")
    created = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "Clean title",
            "test_type": "self_training",
            "questions": [{"text": "Clean question?", "max_score": 10}],
        },
    )
    assert created.status_code == 201, created.text
    test_id = created.json()["id"]

    response = client.post(
        f"/tests/{test_id}/questions",
        headers=auth_header(admin_token),
        json={
            "text": "Почему всё заебало?",
            "expected_answer": "Без хуйни в ответе.",
            "order_index": 1,
            "max_score": 10,
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["text"] == "Почему всё *******?"
    assert payload["expected_answer"] == "Без ***** в ответе."


def test_existing_screenshot_case_is_censored_on_create(client):
    admin_token = register_and_login(client, "admin@example.com")

    response = client.post(
        "/tests",
        headers=auth_header(admin_token),
        json={
            "title": "хуйхуй",
            "test_type": "self_training",
            "questions": [{"text": "сосал", "max_score": 10}],
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["title"] == "******"
    assert payload["questions"][0]["text"] == "*****"
