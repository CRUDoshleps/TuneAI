"""Run a reproducible end-to-end demo against a running TuneAI stack.

The script intentionally uses mock audio bytes. In YANDEX_MOCK mode this checks
the complete application path: auth, attempt, upload, outbox, RabbitMQ worker,
RAG, evaluation persistence and the public API response.
"""

from __future__ import annotations

import argparse
import mimetypes
import sys
import time
from pathlib import Path

import httpx


def wait_for_api(client: httpx.Client, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = client.get("/health")
            if response.is_success:
                return
            last_error = RuntimeError(f"health endpoint returned {response.status_code}")
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(1)
    raise TimeoutError(f"TuneAI API did not become ready in {timeout_seconds} seconds") from last_error


def login(client: httpx.Client, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def find_or_create_attempt(
    client: httpx.Client,
    *,
    admin_token: str,
    student_token: str,
    student_email: str,
    reuse_latest: bool,
) -> dict:
    if reuse_latest:
        response = client.get("/admin/attempts", headers=auth(admin_token))
        response.raise_for_status()
        for item in response.json():
            if item["user_email"] == student_email and item["status"] == "started":
                attempt = client.get(f"/attempts/{item['id']}", headers=auth(student_token))
                attempt.raise_for_status()
                return attempt.json()

    tests = client.get("/tests", headers=auth(student_token))
    tests.raise_for_status()
    available = [item for item in tests.json() if item["status"] == "published"]
    if not available:
        raise RuntimeError("No published test is available for the demo student")
    response = client.post("/attempts", headers=auth(student_token), json={"test_id": available[0]["id"]})
    response.raise_for_status()
    return response.json()


def upload_current_question(
    client: httpx.Client,
    token: str,
    attempt: dict,
    *,
    audio_file: Path | None,
) -> dict:
    answered = {answer["question_id"] for answer in attempt["answers"] if answer["status"] != "failed"}
    question = next((item for item in attempt["questions"] if item["id"] not in answered), None)
    if question is None:
        raise RuntimeError("The selected attempt has no answerable question")
    if audio_file:
        content = audio_file.read_bytes()
        filename = audio_file.name
        content_type = mimetypes.guess_type(audio_file.name)[0] or "application/octet-stream"
    else:
        content = b"tuneai conference smoke audio"
        filename = "conference-demo.webm"
        content_type = "audio/webm;codecs=opus"
    response = client.post(
        f"/attempts/{attempt['id']}/questions/{question['id']}/audio",
        headers=auth(token),
        files={"file": (filename, content, content_type)},
    )
    response.raise_for_status()
    return response.json()


def wait_for_answer(client: httpx.Client, token: str, attempt_id: str, timeout_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/attempts/{attempt_id}", headers=auth(token))
        response.raise_for_status()
        attempt = response.json()
        if attempt["answers"] and attempt["answers"][-1]["status"] in {"completed", "failed"}:
            return attempt
        time.sleep(1)
    raise TimeoutError(f"Attempt {attempt_id} did not finish in {timeout_seconds} seconds")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--student-email", default="student@tuneai.dev")
    parser.add_argument("--password", default="password123")
    parser.add_argument("--admin-email", default="admin@tuneai.dev")
    parser.add_argument("--reuse-latest", action="store_true")
    parser.add_argument("--audio-file", type=Path)
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()
    if args.audio_file and not args.audio_file.is_file():
        parser.error(f"audio file does not exist: {args.audio_file}")

    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        wait_for_api(client, args.timeout)
        readiness = client.get("/readiness/ai")
        readiness.raise_for_status()
        ai_mode = readiness.json()["mode"]
        if ai_mode == "real" and args.audio_file is None:
            parser.error("--audio-file is required when TuneAI runs in real AI mode")
        admin_token = login(client, args.admin_email, args.password)
        student_token = login(client, args.student_email, args.password)
        attempt = find_or_create_attempt(
            client,
            admin_token=admin_token,
            student_token=student_token,
            student_email=args.student_email,
            reuse_latest=args.reuse_latest,
        )
        attempt = upload_current_question(
            client,
            student_token,
            attempt,
            audio_file=args.audio_file,
        )
        result = wait_for_answer(client, student_token, attempt["id"], args.timeout)

    answer = result["answers"][-1]
    evaluation = answer.get("evaluation") or {}
    print(f"ai_mode={ai_mode}")
    print(f"attempt={result['id']}")
    print(f"status={answer['status']}")
    print(f"score={answer.get('score')}/{answer.get('max_score')}")
    print(f"grounded={evaluation.get('grounded')}")
    print(f"review_recommended={evaluation.get('review_recommended')}")
    print(f"sources={len(evaluation.get('source_excerpts') or [])}")
    return 0 if answer["status"] == "completed" and evaluation.get("grounded") else 1


if __name__ == "__main__":
    sys.exit(main())
