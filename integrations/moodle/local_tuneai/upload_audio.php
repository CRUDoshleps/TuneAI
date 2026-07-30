<?php
require_once(__DIR__ . '/../../config.php');

$courseid = required_param('courseid', PARAM_INT);
$cmid = required_param('cmid', PARAM_INT);
$questionid = required_param('questionid', PARAM_INT);
$groupid = optional_param('groupid', null, PARAM_INT);
$externalsubmissionid = optional_param('external_submission_id', '', PARAM_TEXT);

require_sesskey();
$cm = get_coursemodule_from_id('', $cmid, $courseid, false, MUST_EXIST);
require_login($courseid, false, $cm);
$context = context_module::instance($cmid);
require_capability('local/tuneai:submit', $context);

header('Content-Type: application/json; charset=utf-8');

try {
    if (empty($_FILES['audio']) || !is_uploaded_file($_FILES['audio']['tmp_name'])) {
        throw new moodle_exception('Audio file is required');
    }
    $file = $_FILES['audio'];
    if ((int) ($file['error'] ?? UPLOAD_ERR_OK) !== UPLOAD_ERR_OK) {
        throw new moodle_exception('Audio upload failed');
    }
    $maxbytes = 25 * 1024 * 1024;
    if ((int) ($file['size'] ?? 0) <= 0 || (int) ($file['size'] ?? 0) > $maxbytes) {
        throw new moodle_exception('Audio file size is not allowed');
    }
    $contenttype = (string) ($file['type'] ?: 'audio/webm');
    $allowed = ['audio/webm', 'audio/ogg', 'audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/x-wav'];
    if (!in_array($contenttype, $allowed, true)) {
        throw new moodle_exception('Unsupported audio type: ' . $contenttype);
    }
    $service = new \local_tuneai\submission_service();
    $result = $service->submit_audio_file(
        $courseid,
        $cmid,
        $questionid,
        $USER->id,
        $file['tmp_name'],
        (string) ($file['name'] ?: 'answer.webm'),
        $contenttype,
        $groupid,
        $externalsubmissionid !== '' ? $externalsubmissionid : null
    );
    echo json_encode(['ok' => true, 'result' => $result], JSON_UNESCAPED_UNICODE);
} catch (Throwable $exception) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => $exception->getMessage()], JSON_UNESCAPED_UNICODE);
}
