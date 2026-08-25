<?php
declare(strict_types=1);

define('CLI_SCRIPT', true);
require_once('/var/www/html/public/config.php');
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/user/lib.php');
require_once($CFG->libdir . '/enrollib.php');
require_once($CFG->libdir . '/gradelib.php');

$baseUrl = rtrim((string) getenv('TUNEAI_BASE_URL'), '/');
$token = (string) getenv('TUNEAI_MOODLE_KEY');

if ($baseUrl === '' || $token === '') {
    fail('TUNEAI_BASE_URL and TUNEAI_MOODLE_KEY are required');
}

set_config('enabled', 1, 'local_tuneai');
set_config('baseurl', $baseUrl, 'local_tuneai');
set_config('integrationkey', $token, 'local_tuneai');
set_config('siteid', 'tuneai-moodle-e2e', 'local_tuneai');
set_config('timeout', 30, 'local_tuneai');
set_config('gradesync', 1, 'local_tuneai');
set_config('curlsecurityblockedhosts', '');
set_config('curlsecurityallowedport', '');

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

$client = new \local_tuneai\client();
$manifest = $client->manifest('demo-methodist-owner@tuneai.dev', $testId);

assertSame($testId, $manifest['tests'][0]['id'] ?? null, 'manifest test id');
assertSame('demo-methodist-owner@tuneai.dev', $manifest['tests'][0]['owner_email'] ?? null, 'manifest owner email');
assertSame($questionId, $manifest['tests'][0]['questions'][0]['id'] ?? null, 'manifest question id');
assertSame('both', $manifest['tests'][0]['questions'][0]['answer_mode'] ?? null, 'manifest answer mode');

[$course, $user] = createMoodleFixture($stamp);
$cmid = 900000 + ((int) $stamp % 100000);
$moodlequestionid = 800000 + ((int) $stamp % 100000);
$repository = new \local_tuneai\mapping_repository();
$repository->upsert_mapping(
    (int) $course->id,
    $cmid,
    $moodlequestionid,
    null,
    $testId,
    $questionId,
    'demo-methodist-owner@tuneai.dev'
);

$service = new \local_tuneai\submission_service();
$externalSubmissionId = 'moodle-plugin-e2e-submission-' . $stamp;
$submission = $service->submit_text_answer(
    (int) $course->id,
    $cmid,
    $moodlequestionid,
    (int) $user->id,
    'The transactional outbox saves the event with the database change and a worker publishes it after commit.',
    null,
    $externalSubmissionId
);

assertSame($externalSubmissionId, $submission['external_submission_id'] ?? null, 'submission id');
assertSame(false, (bool) ($submission['result_ready'] ?? false), 'initial result_ready');
assertSame((string) $course->id, $submission['moodle_course_id'] ?? null, 'submission course id');
assertSame((string) $cmid, $submission['moodle_activity_id'] ?? null, 'submission activity id');

$replay = $service->submit_text_answer(
    (int) $course->id,
    $cmid,
    $moodlequestionid,
    (int) $user->id,
    'Replay text must not replace the original Moodle submission.',
    null,
    $externalSubmissionId
);

assertSame($submission['answer_id'] ?? null, $replay['answer_id'] ?? null, 'idempotent answer id');
assertSame($submission['attempt_id'] ?? null, $replay['attempt_id'] ?? null, 'idempotent attempt id');

$retake = $service->submit_text_answer(
    (int) $course->id,
    $cmid,
    $moodlequestionid,
    (int) $user->id,
    'A second quiz attempt stores the event and business update atomically before publishing.',
    null,
    $externalSubmissionId . '-retake',
    null,
    'moodle-plugin-e2e-attempt-' . $stamp . '-retake'
);
if (($retake['attempt_id'] ?? null) === ($submission['attempt_id'] ?? null)) {
    fail('A Moodle retake must create a separate TuneAI attempt');
}

$result = pollScheduledTaskResult($repository, $externalSubmissionId);

assertSame(true, (bool) ($result['result_ready'] ?? false), 'final result_ready');
requireNumber($result, 'score');
requireNumber($result, 'max_score');
requireNumber($result, 'grade');
requireNumber($result, 'confidence');
requireString($result, 'feedback');
requireString($result, 'transcript');

assertSame('review_recommended', $result['teacher_signal'] ?? null, 'initial teacher signal');
assertMoodleGradeMissing((int) $course->id, $cmid, (int) $user->id);

$reviewer = $DB->get_record('user', ['username' => 'admin'], '*', MUST_EXIST);
$result = $service->review_submission(
    $externalSubmissionId,
    8.5,
    'Approved by the Moodle E2E teacher.',
    (int) $reviewer->id,
    fullname($reviewer)
);
assertSame('none', $result['teacher_signal'] ?? null, 'reviewed teacher signal');
assertSame(8.5, (float) ($result['score'] ?? -1), 'reviewed score');
assertSame('Approved by the Moodle E2E teacher.', $result['feedback'] ?? null, 'reviewed feedback');
if (!isset($result['moodle_grade_sync']) || !is_array($result['moodle_grade_sync'])) {
    fail('Moodle grade sync payload is missing after teacher review');
}
assertMoodleGrade((int) $course->id, $cmid, (int) $user->id, $result);

$localSubmission = $repository->find_submission($externalSubmissionId);
if (!$localSubmission || (int) $localSubmission->result_ready !== 1) {
    fail('Moodle local submission mirror was not updated');
}

$teacherSignal = $result['teacher_signal'] ?? null;
if (!in_array($teacherSignal, ['none', 'review_recommended', 'processing_failed'], true)) {
    fail('Unexpected teacher_signal: ' . json_encode($teacherSignal, JSON_UNESCAPED_UNICODE));
}

if (($result['grade'] < 0) || ($result['grade'] > 1)) {
    fail('Grade must be normalized between 0 and 1');
}

echo "Moodle plugin E2E passed\n";
echo json_encode(
    [
        'external_submission_id' => $externalSubmissionId,
        'answer_id' => $result['answer_id'],
        'score' => $result['score'],
        'max_score' => $result['max_score'],
        'grade' => $result['grade'],
        'teacher_signal' => $teacherSignal,
        'moodle_grade_sync' => $result['moodle_grade_sync'],
    ],
    JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE
) . "\n";

function createMoodleFixture(string $stamp): array
{
    global $CFG, $DB;
    $course = create_course((object) [
        'fullname' => 'TuneAI Moodle E2E ' . $stamp,
        'shortname' => 'tuneai-e2e-' . $stamp,
        'category' => 1,
        'visible' => 1,
    ]);
    $user = (object) [
        'auth' => 'manual',
        'confirmed' => 1,
        'mnethostid' => $CFG->mnet_localhost_id,
        'username' => 'tuneai-e2e-' . $stamp,
        'password' => 'TuneAI-e2e-password-123',
        'firstname' => 'Moodle',
        'lastname' => 'Student',
        'email' => 'moodle-e2e-' . $stamp . '@example.edu',
    ];
    $user->id = user_create_user($user, true, false);
    $studentroleid = (int) $DB->get_field('role', 'id', ['shortname' => 'student'], MUST_EXIST);
    $manual = enrol_get_plugin('manual');
    if (!$manual) {
        fail('Manual enrolment plugin is not available');
    }
    $instances = enrol_get_instances((int) $course->id, true);
    $instance = null;
    foreach ($instances as $candidate) {
        if ($candidate->enrol === 'manual') {
            $instance = $candidate;
            break;
        }
    }
    if ($instance === null) {
        $instanceid = $manual->add_instance($course);
        $instance = $DB->get_record('enrol', ['id' => $instanceid], '*', MUST_EXIST);
    }
    $manual->enrol_user($instance, (int) $user->id, $studentroleid);
    return [$course, $user];
}

function assertMoodleGrade(int $courseid, int $cmid, int $userid, array $result): void
{
    global $DB;
    $sync = $result['moodle_grade_sync'];
    $item = $DB->get_record('grade_items', [
        'courseid' => $courseid,
        'itemtype' => 'manual',
        'iteminstance' => $cmid,
        'itemnumber' => (int) $sync['itemnumber'],
        'idnumber' => 'local_tuneai_' . $cmid . '_' . (int) $sync['itemnumber'],
    ]);
    if (!$item) {
        fail('Moodle grade item was not created');
    }
    $grade = $DB->get_record('grade_grades', ['itemid' => $item->id, 'userid' => $userid]);
    if (!$grade) {
        fail('Moodle user grade was not written');
    }
    $expected = round((float) $result['score'], 4);
    $actual = round((float) $grade->finalgrade, 4);
    if ($expected !== $actual) {
        fail('Moodle final grade mismatch: expected ' . $expected . ', got ' . $actual);
    }
}

function assertMoodleGradeMissing(int $courseid, int $cmid, int $userid): void
{
    global $DB;
    $items = $DB->get_records('grade_items', [
        'courseid' => $courseid,
        'itemtype' => 'manual',
        'iteminstance' => $cmid,
    ]);
    foreach ($items as $item) {
        if ($DB->record_exists('grade_grades', ['itemid' => $item->id, 'userid' => $userid])) {
            fail('A review-required AI result must not be written to the Moodle gradebook');
        }
    }
}

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

function pollScheduledTaskResult(\local_tuneai\mapping_repository $repository, string $externalSubmissionId): array
{
    global $DB;
    $deadline = time() + 180;
    $task = new \local_tuneai\task\sync_submissions();
    do {
        $submission = $repository->find_submission($externalSubmissionId);
        if ($submission) {
            $submission->next_sync_time = time() - 1;
            $DB->update_record(\local_tuneai\mapping_repository::SUBMISSION_TABLE, $submission);
        }
        $task->execute();
        $submission = $repository->find_submission($externalSubmissionId);
        if ($submission && (int) $submission->result_ready === 1) {
            return [
                'external_submission_id' => $submission->external_submission_id,
                'answer_id' => $submission->tuneai_answer_id,
                'result_ready' => true,
                'score' => (float) $submission->score,
                'max_score' => (float) $submission->max_score,
                'grade' => (float) $submission->grade,
                'confidence' => (float) $submission->confidence,
                'feedback' => (string) $submission->feedback,
                'transcript' => (string) $submission->transcript,
                'teacher_signal' => $submission->teacher_signal,
                'review_reason' => $submission->review_reason,
            ];
        }
        sleep(3);
    } while (time() < $deadline);
    fail('Timed out waiting for Moodle scheduled sync');
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
