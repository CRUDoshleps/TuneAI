<?php
require_once(__DIR__ . '/../../config.php');

$courseid = required_param('courseid', PARAM_INT);
$cmid = optional_param('cmid', 0, PARAM_INT);
$methodistemail = optional_param('methodist_email', '', PARAM_EMAIL);
$selectedtestid = optional_param('test_id', '', PARAM_TEXT);
$course = get_course($courseid);
$context = context_course::instance($courseid);

require_login($course);
require_capability('local/tuneai:manage', $context);

$PAGE->set_url(new moodle_url('/local/tuneai/manage.php', ['courseid' => $courseid, 'cmid' => $cmid]));
$PAGE->set_context($context);
$PAGE->set_title(get_string('mappingtitle', 'local_tuneai'));
$PAGE->set_heading(format_string($course->fullname));

$repository = new \local_tuneai\mapping_repository();
$notice = '';
$error = '';
$manifest = ['tests' => []];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    require_sesskey();
    $cmid = required_param('cmid', PARAM_INT);
    $moodlequestionid = required_param('moodle_question_id', PARAM_INT);
    $selectedtestid = required_param('test_id', PARAM_TEXT);
    $tuneaiquestionid = required_param('tuneai_question_id', PARAM_TEXT);
    $groupid = optional_param('groupid', 0, PARAM_INT);
    $methodistemail = optional_param('methodist_email', '', PARAM_EMAIL);
    $repository->upsert_mapping($courseid, $cmid, $moodlequestionid, $groupid ?: null, $selectedtestid, $tuneaiquestionid, $methodistemail ?: null);
    $notice = get_string('mappingsaved', 'local_tuneai');
}

if ((int) get_config('local_tuneai', 'enabled') === 1 && get_config('local_tuneai', 'baseurl') && get_config('local_tuneai', 'integrationkey')) {
    try {
        $manifest = (new \local_tuneai\client())->manifest($methodistemail ?: null, $selectedtestid ?: null);
    } catch (Throwable $exception) {
        $error = $exception->getMessage();
    }
} else {
    $error = get_string('connectionnotconfigured', 'local_tuneai');
}

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('mappingtitle', 'local_tuneai'));

if ($notice) {
    echo $OUTPUT->notification($notice, 'notifysuccess');
}
if ($error) {
    echo $OUTPUT->notification(get_string('connectionfailed', 'local_tuneai') . ': ' . s($error), 'notifyproblem');
} else {
    echo $OUTPUT->notification(get_string('connectionok', 'local_tuneai'), 'notifysuccess');
}

echo html_writer::start_tag('form', ['method' => 'get', 'class' => 'local-tuneai-filter']);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'courseid', 'value' => $courseid]);
echo html_writer::tag('label', get_string('activityid', 'local_tuneai') . html_writer::empty_tag('input', ['type' => 'number', 'name' => 'cmid', 'value' => $cmid, 'min' => 1]));
echo html_writer::tag('label', get_string('methodistemail', 'local_tuneai') . html_writer::empty_tag('input', ['type' => 'email', 'name' => 'methodist_email', 'value' => $methodistemail]));
echo html_writer::tag('label', get_string('tuneaitestid', 'local_tuneai') . html_writer::empty_tag('input', ['type' => 'text', 'name' => 'test_id', 'value' => $selectedtestid]));
echo html_writer::empty_tag('input', ['type' => 'submit', 'value' => get_string('refreshmanifest', 'local_tuneai')]);
echo html_writer::end_tag('form');

if (!empty($manifest['tests'])) {
    echo html_writer::start_tag('div', ['class' => 'local-tuneai-manifest']);
    foreach ($manifest['tests'] as $test) {
        echo html_writer::tag('h3', s($test['title']));
        echo html_writer::tag('p', s($test['owner_email']) . ' · ' . s($test['test_type']));
        echo html_writer::start_tag('table', ['class' => 'generaltable']);
        echo html_writer::tag('tr', html_writer::tag('th', get_string('moodlequestionid', 'local_tuneai')) . html_writer::tag('th', get_string('tuneaiquestion', 'local_tuneai')) . html_writer::tag('th', get_string('answermode', 'local_tuneai')) . html_writer::tag('th', get_string('groupid', 'local_tuneai')) . html_writer::tag('th', ''));
        foreach ($test['questions'] as $question) {
            echo html_writer::start_tag('tr');
            echo html_writer::start_tag('form', ['method' => 'post']);
            echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'sesskey', 'value' => sesskey()]);
            echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'courseid', 'value' => $courseid]);
            echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'cmid', 'value' => $cmid]);
            echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'methodist_email', 'value' => $methodistemail]);
            echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'test_id', 'value' => $test['id']]);
            echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'tuneai_question_id', 'value' => $question['id']]);
            echo html_writer::tag('td', html_writer::empty_tag('input', ['type' => 'number', 'name' => 'moodle_question_id', 'required' => 'required', 'min' => 1]));
            echo html_writer::tag('td', s($question['text']) . html_writer::tag('div', s($question['id']), ['class' => 'muted']));
            echo html_writer::tag('td', s($question['answer_mode']));
            echo html_writer::tag('td', html_writer::empty_tag('input', ['type' => 'number', 'name' => 'groupid', 'min' => 1]));
            echo html_writer::tag('td', html_writer::empty_tag('input', ['type' => 'submit', 'value' => get_string('savemapping', 'local_tuneai')]));
            echo html_writer::end_tag('form');
            echo html_writer::end_tag('tr');
        }
        echo html_writer::end_tag('table');
    }
    echo html_writer::end_tag('div');
} else if (!$error) {
    echo html_writer::tag('p', get_string('manifestempty', 'local_tuneai'));
}

echo $OUTPUT->footer();
