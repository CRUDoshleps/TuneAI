<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

require_once(__DIR__ . '/../../config.php');
require_once($CFG->dirroot . '/group/lib.php');

$courseid = required_param('courseid', PARAM_INT);
$mappingid = required_param('mappingid', PARAM_INT);
$course = get_course($courseid);
$repository = new \local_tuneai\mapping_repository();
$mapping = $repository->get_mapping($mappingid, $courseid);
if (!$mapping) {
    throw new moodle_exception('TuneAI mapping was not found');
}
$cm = get_coursemodule_from_id('', (int) $mapping->cmid, $courseid, false, MUST_EXIST);
$context = context_module::instance((int) $mapping->cmid);

require_login($course, false, $cm);
require_capability('local/tuneai:submit', $context);
if ($mapping->groupid && !groups_is_member((int) $mapping->groupid, $USER->id)) {
    throw new required_capability_exception($context, 'local/tuneai:submit', 'nopermissions', '');
}

$PAGE->set_url(new moodle_url('/local/tuneai/take.php', ['courseid' => $courseid, 'mappingid' => $mappingid]));
$PAGE->set_context($context);
$PAGE->set_title(get_string('takeassessment', 'local_tuneai'));
$PAGE->set_heading(format_string($course->fullname));

$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    require_sesskey();
    if (!in_array($mapping->answer_mode, ['text', 'both'], true)) {
        throw new moodle_exception('Text answers are disabled for this TuneAI question');
    }
    $answer = required_param('answer', PARAM_RAW);
    $nonce = bin2hex(random_bytes(12));
    try {
        (new \local_tuneai\submission_service())->submit_text_answer(
            $courseid,
            (int) $mapping->cmid,
            (int) $mapping->questionid,
            (int) $USER->id,
            $answer,
            $mapping->groupid ? (int) $mapping->groupid : null,
            'moodle-page-' . $nonce,
            null,
            'moodle-page-attempt-' . $nonce
        );
        redirect(new moodle_url('/local/tuneai/result.php', [
            'courseid' => $courseid,
            'external_submission_id' => 'moodle-page-' . $nonce,
        ]));
    } catch (Throwable $exception) {
        $error = $exception->getMessage();
    }
}

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('takeassessment', 'local_tuneai'));
if ($mapping->question_text) {
    echo html_writer::tag('div', format_text($mapping->question_text, FORMAT_PLAIN), ['class' => 'alert alert-info']);
}
if ($error) {
    echo $OUTPUT->notification(s($error), 'notifyproblem');
}
if (in_array($mapping->answer_mode, ['text', 'both'], true)) {
    echo html_writer::start_tag('form', ['method' => 'post', 'class' => 'local-tuneai-text-answer']);
    echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'sesskey', 'value' => sesskey()]);
    echo html_writer::tag('label', get_string('textanswer', 'local_tuneai'), ['for' => 'local-tuneai-answer']);
    echo html_writer::tag('textarea', '', [
        'id' => 'local-tuneai-answer',
        'name' => 'answer',
        'rows' => 8,
        'maxlength' => 20000,
        'required' => 'required',
    ]);
    echo html_writer::empty_tag('input', ['type' => 'submit', 'class' => 'btn btn-primary', 'value' => get_string('submitanswer', 'local_tuneai')]);
    echo html_writer::end_tag('form');
}
if (in_array($mapping->answer_mode, ['audio', 'both'], true)) {
    echo $OUTPUT->render_from_template('local_tuneai/recorder', [
        'endpoint' => (new moodle_url('/local/tuneai/upload_audio.php'))->out(false),
        'resulturl' => (new moodle_url('/local/tuneai/result.php', ['courseid' => $courseid]))->out(false),
        'courseid' => $courseid,
        'cmid' => $mapping->cmid,
        'questionid' => $mapping->questionid,
        'groupid' => $mapping->groupid,
        'sesskey' => sesskey(),
    ]);
    $PAGE->requires->js_call_amd('local_tuneai/recorder', 'init', ['.local-tuneai-recorder']);
}
echo $OUTPUT->footer();
