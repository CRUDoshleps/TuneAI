<?php
require_once(__DIR__ . '/../../config.php');

$courseid = optional_param('courseid', SITEID, PARAM_INT);
$course = get_course($courseid);
$context = context_course::instance($courseid);

require_login($course);
require_capability('local/tuneai:manage', $context);

$PAGE->set_url(new moodle_url('/local/tuneai/index.php', ['courseid' => $courseid]));
$PAGE->set_context($context);
$PAGE->set_title(get_string('pluginname', 'local_tuneai'));
$PAGE->set_heading(format_string($course->fullname));

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('pluginname', 'local_tuneai'));
echo html_writer::tag('p', get_string('pluginoverview', 'local_tuneai'));
echo html_writer::link(new moodle_url('/local/tuneai/manage.php', ['courseid' => $courseid]), get_string('openmapping', 'local_tuneai'), ['class' => 'btn btn-primary']);
echo $OUTPUT->footer();
