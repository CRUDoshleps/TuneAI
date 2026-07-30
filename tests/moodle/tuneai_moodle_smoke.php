<?php
declare(strict_types=1);

$baseUrl = rtrim((string) getenv('TUNEAI_BASE_URL'), '/');
$token = (string) getenv('TUNEAI_MOODLE_KEY');

if ($baseUrl === '' || $token === '') {
    fail('TUNEAI_BASE_URL and TUNEAI_MOODLE_KEY are required');
}

waitForTuneAI($baseUrl);

$stamp = (string) time();
$demo = requestJson(
    'POST',
    $baseUrl . '/public/demo/bootstrap',
    [],
    [
        'scenario_id' => 'moodle-e2e-' . $stamp,
        'label' => 'Moodle E2E',
        'test_type' => 'exam',
        'role_label' => 'Экзаменуемый Moodle',
        'title' => 'Moodle text answer e2e',
        'description' => 'Проверка отправки ответа из Moodle в TuneAI',
        'question' => 'Explain transactional outbox in one paragraph.',
        'expected_answer' => 'Transactional outbox stores an event in the same transaction as business data and publishes it later.',
        'agent_profile' => 'moodle-e2e-reviewer',
        'competencies' => ['Reliability', 'Architecture'],
    ],
    201
);

$accessToken = $demo['tokens']['access_token'] ?? null;
$testId = $demo['test']['id'] ?? null;

if (!is_string($accessToken) || !is_string($testId)) {
    fail('Demo bootstrap response does not include token and test id');
}

$attempt = requestJson(
    'POST',
    $baseUrl . '/attempts',
    ['Authorization: Bearer ' . $accessToken],
    ['test_id' => $testId],
    201
);

$questionId = $attempt['questions'][0]['id'] ?? null;

if (!is_string($questionId)) {
    fail('Attempt response does not include visible question id');
}

$externalSubmissionId = 'moodle-e2e-submission-' . $stamp;
$submission = requestJson(
    'POST',
    $baseUrl . '/integrations/moodle/submissions/text',
    ['X-TuneAI-Integration-Key: ' . $token],
    [
        'external_submission_id' => $externalSubmissionId,
        'external_attempt_id' => 'moodle-e2e-attempt-' . $stamp,
        'moodle_user_id' => 'moodle-e2e-user-' . $stamp,
        'moodle_course_id' => 'course-e2e',
        'moodle_activity_id' => 'quiz-e2e',
        'user_email' => 'moodle-e2e-' . $stamp . '@example.edu',
        'user_full_name' => 'Moodle E2E Student',
        'test_id' => $testId,
        'question_id' => $questionId,
        'text' => 'The transactional outbox saves the event with the database change and a worker publishes it after commit.',
    ],
    201
);

assertSame($externalSubmissionId, $submission['external_submission_id'] ?? null, 'submission id');
assertSame(false, (bool) ($submission['result_ready'] ?? false), 'initial result_ready');

$replay = requestJson(
    'POST',
    $baseUrl . '/integrations/moodle/submissions/text',
    ['X-TuneAI-Integration-Key: ' . $token],
    [
        'external_submission_id' => $externalSubmissionId,
        'external_attempt_id' => 'moodle-e2e-attempt-' . $stamp,
        'moodle_user_id' => 'moodle-e2e-user-' . $stamp,
        'moodle_course_id' => 'course-e2e',
        'moodle_activity_id' => 'quiz-e2e',
        'user_email' => 'moodle-e2e-' . $stamp . '@example.edu',
        'user_full_name' => 'Moodle E2E Student',
        'test_id' => $testId,
        'question_id' => $questionId,
        'text' => 'Replay text must not replace the original Moodle submission.',
    ],
    201
);

assertSame($submission['answer_id'] ?? null, $replay['answer_id'] ?? null, 'idempotent answer id');
assertSame($submission['attempt_id'] ?? null, $replay['attempt_id'] ?? null, 'idempotent attempt id');

$result = pollResult($baseUrl, $token, $externalSubmissionId);

assertSame(true, (bool) ($result['result_ready'] ?? false), 'final result_ready');
requireNumber($result, 'score');
requireNumber($result, 'max_score');
requireNumber($result, 'grade');
requireNumber($result, 'confidence');
requireString($result, 'feedback');
requireString($result, 'transcript');

$teacherSignal = $result['teacher_signal'] ?? null;
if (!in_array($teacherSignal, ['none', 'review_recommended', 'processing_failed'], true)) {
    fail('Unexpected teacher_signal: ' . json_encode($teacherSignal, JSON_UNESCAPED_UNICODE));
}

if (($result['grade'] < 0) || ($result['grade'] > 1)) {
    fail('Grade must be normalized between 0 and 1');
}

echo "Moodle E2E passed\n";
echo json_encode(
    [
        'external_submission_id' => $externalSubmissionId,
        'answer_id' => $result['answer_id'],
        'score' => $result['score'],
        'max_score' => $result['max_score'],
        'grade' => $result['grade'],
        'teacher_signal' => $teacherSignal,
    ],
    JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE
) . "\n";

function waitForTuneAI(string $baseUrl): void
{
    $deadline = time() + 120;
    do {
        [$status] = request('GET', $baseUrl . '/health', [], null, 5);
        if ($status === 200) {
            return;
        }
        sleep(2);
    } while (time() < $deadline);
    fail('TuneAI health endpoint is not ready');
}

function pollResult(string $baseUrl, string $token, string $externalSubmissionId): array
{
    $deadline = time() + 180;
    $last = null;
    do {
        $last = requestJson(
            'GET',
            $baseUrl . '/integrations/moodle/submissions/' . rawurlencode($externalSubmissionId) . '/result',
            ['X-TuneAI-Integration-Key: ' . $token],
            null,
            200
        );
        if (($last['result_ready'] ?? false) === true) {
            return $last;
        }
        sleep(3);
    } while (time() < $deadline);
    fail('Timed out waiting for Moodle result: ' . json_encode($last, JSON_UNESCAPED_UNICODE));
}

function requestJson(string $method, string $url, array $headers, ?array $payload, int $expectedStatus): array
{
    $body = $payload === null ? null : json_encode($payload, JSON_UNESCAPED_UNICODE);
    [$status, $raw] = request($method, $url, array_merge(['Accept: application/json'], $headers), $body, 30);
    $decoded = json_decode($raw, true);
    if ($status !== $expectedStatus) {
        fail($method . ' ' . $url . ' returned ' . $status . ': ' . $raw);
    }
    if (!is_array($decoded)) {
        fail($method . ' ' . $url . ' did not return JSON: ' . $raw);
    }
    return $decoded;
}

function request(string $method, string $url, array $headers, ?string $body, int $timeout): array
{
    if ($body !== null) {
        $headers[] = 'Content-Type: application/json';
    }
    $context = stream_context_create([
        'http' => [
            'method' => $method,
            'header' => implode("\r\n", $headers),
            'content' => $body ?? '',
            'ignore_errors' => true,
            'timeout' => $timeout,
        ],
    ]);
    $raw = @file_get_contents($url, false, $context);
    $status = 0;
    foreach (($http_response_header ?? []) as $header) {
        if (preg_match('/^HTTP\/\S+\s+(\d+)/', $header, $matches)) {
            $status = (int) $matches[1];
            break;
        }
    }
    return [$status, $raw === false ? '' : $raw];
}

function assertSame(mixed $expected, mixed $actual, string $label): void
{
    if ($expected !== $actual) {
        fail($label . ' mismatch: expected ' . json_encode($expected) . ', got ' . json_encode($actual));
    }
}

function requireNumber(array $payload, string $key): void
{
    if (!array_key_exists($key, $payload) || !is_numeric($payload[$key])) {
        fail($key . ' must be numeric');
    }
}

function requireString(array $payload, string $key): void
{
    if (!array_key_exists($key, $payload) || !is_string($payload[$key]) || trim($payload[$key]) === '') {
        fail($key . ' must be a non-empty string');
    }
}

function fail(string $message): void
{
    fwrite(STDERR, $message . PHP_EOL);
    exit(1);
}
