<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

require_once(__DIR__ . '/../../config.php');

$courseid = required_param('courseid', PARAM_INT);
$course = get_course($courseid);
$context = context_course::instance($courseid);

require_login($course);
require_capability('local/tuneai:viewresults', $context);

$PAGE->set_url(new moodle_url('/local/tuneai/results.php', ['courseid' => $courseid]));
$PAGE->set_context($context);
$PAGE->set_title(get_string('resultstitle', 'local_tuneai'));
$PAGE->set_heading(format_string($course->fullname));

$repository = new \local_tuneai\mapping_repository();
$page = optional_param('page', 0, PARAM_INT);
$perpage = 50;
$total = $repository->count_course_submissions($courseid);
$submissions = $repository->course_submissions($courseid, $perpage, $page * $perpage);

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('resultstitle', 'local_tuneai'));

if (!$submissions) {
    echo $OUTPUT->notification(get_string('noresults', 'local_tuneai'), 'notifyinfo');
} else {
    echo $OUTPUT->paging_bar($total, $page, $perpage, $PAGE->url);
    $table = new html_table();
    $table->head = [
        get_string('participant', 'local_tuneai'),
        get_string('questionlabel', 'local_tuneai'),
        get_string('statuslabel', 'local_tuneai'),
        get_string('scoreheading', 'local_tuneai'),
        get_string('submittedat', 'local_tuneai'),
        get_string('actions', 'local_tuneai'),
    ];
    foreach ($submissions as $submission) {
        $user = core_user::get_user((int) $submission->userid, '*', IGNORE_MISSING);
        $status = (string) ($submission->answer_status ?: get_string('processing', 'local_tuneai'));
        if ($submission->teacher_signal === 'review_recommended') {
            $status = get_string('reviewrequired', 'local_tuneai');
        }
        $score = is_numeric($submission->score) && is_numeric($submission->max_score)
            ? format_float((float) $submission->score, 2) . ' / ' . format_float((float) $submission->max_score, 2)
            : '—';
        $table->data[] = [
            $user ? fullname($user) : get_string('deleteduser', 'local_tuneai'),
            s((string) $submission->tuneai_question_id),
            s($status),
            $score,
            userdate((int) $submission->timecreated),
            html_writer::link(
                new moodle_url('/local/tuneai/result.php', [
                    'courseid' => $courseid,
                    'external_submission_id' => $submission->external_submission_id,
                ]),
                get_string('viewresult', 'local_tuneai')
            ),
        ];
    }
    echo html_writer::tag('div', html_writer::table($table), ['class' => 'local-tuneai-results-table']);
    echo $OUTPUT->paging_bar($total, $page, $perpage, $PAGE->url);
}

echo html_writer::link(
    new moodle_url('/local/tuneai/index.php', ['courseid' => $courseid]),
    get_string('backtocourseassessments', 'local_tuneai')
);
echo $OUTPUT->footer();
