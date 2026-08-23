<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

require_once(__DIR__ . '/../../config.php');

$courseid = required_param('courseid', PARAM_INT);
$externalsubmissionid = required_param('external_submission_id', PARAM_TEXT);
$course = get_course($courseid);
$coursecontext = context_course::instance($courseid);
require_login($course);

$repository = new \local_tuneai\mapping_repository();
$submission = $repository->find_submission($externalsubmissionid);
if (!$submission || (int) $submission->courseid !== $courseid) {
    throw new moodle_exception('TuneAI submission was not found');
}
if ((int) $submission->userid !== (int) $USER->id && !has_capability('local/tuneai:viewresults', $coursecontext)) {
    throw new required_capability_exception($coursecontext, 'local/tuneai:viewresults', 'nopermissions', '');
}

$canreview = has_capability('local/tuneai:viewresults', $coursecontext);
$reviewnotice = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    require_sesskey();
    require_capability('local/tuneai:viewresults', $coursecontext);
    $score = required_param('score', PARAM_FLOAT);
    $feedback = required_param('feedback', PARAM_TEXT);
    try {
        (new \local_tuneai\submission_service())->review_submission(
            $externalsubmissionid,
            $score,
            $feedback,
            (int) $USER->id,
            fullname($USER)
        );
        redirect(new moodle_url('/local/tuneai/result.php', [
            'courseid' => $courseid,
            'external_submission_id' => $externalsubmissionid,
            'reviewed' => 1,
        ]));
    } catch (Throwable $exception) {
        $refresherror = $exception->getMessage();
    }
}
$reviewnotice = optional_param('reviewed', 0, PARAM_BOOL) ? get_string('reviewsaved', 'local_tuneai') : '';

if ((int) $submission->next_sync_time > 0) {
    try {
        (new \local_tuneai\submission_service())->refresh_submission_result($externalsubmissionid);
        $submission = $repository->find_submission($externalsubmissionid);
    } catch (Throwable $exception) {
        $refresherror = $exception->getMessage();
    }
}

$PAGE->set_url(new moodle_url('/local/tuneai/result.php', ['courseid' => $courseid, 'external_submission_id' => $externalsubmissionid]));
$PAGE->set_context($coursecontext);
$PAGE->set_title(get_string('resulttitle', 'local_tuneai'));
$PAGE->set_heading(format_string($course->fullname));

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('resulttitle', 'local_tuneai'));
if ($reviewnotice) {
    echo $OUTPUT->notification($reviewnotice, 'notifysuccess');
}
if (!empty($refresherror)) {
    echo $OUTPUT->notification(s($refresherror), 'notifyproblem');
}
if ($submission->answer_status === 'failed' || $submission->answer_status === 'sync_failed') {
    echo $OUTPUT->notification(s($submission->last_error ?: $submission->review_reason ?: get_string('processingfailed', 'local_tuneai')), 'notifyproblem');
} else if (!(int) $submission->result_ready) {
    echo $OUTPUT->notification(get_string('processing', 'local_tuneai'), 'notifyinfo');
    echo html_writer::tag('meta', '', ['http-equiv' => 'refresh', 'content' => '10']);
} else {
    echo html_writer::tag('p', get_string('scorelabel', 'local_tuneai', (object) ['score' => $submission->score, 'max' => $submission->max_score]));
    if ($submission->teacher_signal === 'review_recommended') {
        echo $OUTPUT->notification(s($submission->review_reason ?: get_string('reviewrequired', 'local_tuneai')), 'notifywarning');
        if ($canreview) {
            echo html_writer::start_tag('form', ['method' => 'post', 'class' => 'local-tuneai-review-form']);
            echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'sesskey', 'value' => sesskey()]);
            echo html_writer::tag('label', get_string('reviewscore', 'local_tuneai'), ['for' => 'local-tuneai-review-score']);
            echo html_writer::empty_tag('input', [
                'id' => 'local-tuneai-review-score',
                'type' => 'number',
                'name' => 'score',
                'required' => 'required',
                'min' => 0,
                'max' => $submission->max_score,
                'step' => '0.01',
                'value' => $submission->score,
            ]);
            echo html_writer::tag('label', get_string('reviewfeedback', 'local_tuneai'), ['for' => 'local-tuneai-review-feedback']);
            echo html_writer::tag('textarea', s((string) $submission->feedback), [
                'id' => 'local-tuneai-review-feedback',
                'name' => 'feedback',
                'rows' => 5,
                'maxlength' => 10000,
                'required' => 'required',
            ]);
            echo html_writer::empty_tag('input', [
                'type' => 'submit',
                'class' => 'btn btn-primary',
                'value' => get_string('approvereview', 'local_tuneai'),
            ]);
            echo html_writer::end_tag('form');
        }
    }
    if ($submission->feedback) {
        echo html_writer::tag('h3', get_string('feedbacklabel', 'local_tuneai'));
        echo html_writer::tag('p', s($submission->feedback));
    }
    if (is_numeric($submission->confidence)) {
        echo html_writer::tag('p', get_string('confidencelabel', 'local_tuneai', format_float((float) $submission->confidence, 2)));
    }
    if ($submission->transcript) {
        echo html_writer::tag('h3', get_string('transcriptlabel', 'local_tuneai'));
        echo html_writer::tag('p', s($submission->transcript));
    }
}
echo html_writer::link(new moodle_url('/local/tuneai/index.php', ['courseid' => $courseid]), get_string('backtocourseassessments', 'local_tuneai'));
echo $OUTPUT->footer();
