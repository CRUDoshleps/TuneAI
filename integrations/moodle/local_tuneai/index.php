<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

require_once(__DIR__ . '/../../config.php');
require_once($CFG->dirroot . '/group/lib.php');

$courseid = optional_param('courseid', SITEID, PARAM_INT);
$course = get_course($courseid);
$context = context_course::instance($courseid);

require_login($course);
if (!has_any_capability(['local/tuneai:submit', 'local/tuneai:manage', 'local/tuneai:viewresults'], $context)) {
    throw new required_capability_exception($context, 'local/tuneai:submit', 'nopermissions', '');
}

$PAGE->set_url(new moodle_url('/local/tuneai/index.php', ['courseid' => $courseid]));
$PAGE->set_context($context);
$PAGE->set_title(get_string('pluginname', 'local_tuneai'));
$PAGE->set_heading(format_string($course->fullname));

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('pluginname', 'local_tuneai'));
echo html_writer::tag('p', get_string('pluginoverview', 'local_tuneai'));
if (has_capability('local/tuneai:manage', $context)) {
    echo html_writer::link(new moodle_url('/local/tuneai/manage.php', ['courseid' => $courseid]), get_string('openmapping', 'local_tuneai'), ['class' => 'btn btn-secondary']);
}
if (has_capability('local/tuneai:viewresults', $context)) {
    echo ' ' . html_writer::link(
        new moodle_url('/local/tuneai/results.php', ['courseid' => $courseid]),
        get_string('openresults', 'local_tuneai'),
        ['class' => 'btn btn-secondary']
    );
}

$repository = new \local_tuneai\mapping_repository();
$mappings = $repository->course_mappings($courseid);
if (!$mappings) {
    echo $OUTPUT->notification(get_string('nomappings', 'local_tuneai'), 'notifyinfo');
} else {
    echo html_writer::start_tag('div', ['class' => 'local-tuneai-assessments']);
    foreach ($mappings as $mapping) {
        $cm = get_coursemodule_from_id('', (int) $mapping->cmid, $courseid, false, IGNORE_MISSING);
        if (!$cm) {
            continue;
        }
        $modulecontext = context_module::instance((int) $mapping->cmid);
        if (!has_capability('local/tuneai:submit', $modulecontext) && !has_capability('local/tuneai:manage', $modulecontext)) {
            continue;
        }
        if ($mapping->groupid && !groups_is_member((int) $mapping->groupid, $USER->id) && !has_capability('local/tuneai:manage', $modulecontext)) {
            continue;
        }
        $label = $mapping->question_text ? s($mapping->question_text) : get_string('assessmentlabel', 'local_tuneai', (object) [
            'questionid' => $mapping->questionid,
            'mode' => $mapping->answer_mode,
        ]);
        echo html_writer::link(
            new moodle_url('/local/tuneai/take.php', ['courseid' => $courseid, 'mappingid' => $mapping->id]),
            $label,
            ['class' => 'btn btn-primary']
        );
    }
    echo html_writer::end_tag('div');
}
echo $OUTPUT->footer();
