<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

defined('MOODLE_INTERNAL') || die();

function local_tuneai_extend_navigation_course(
    navigation_node $parentnode,
    stdClass $course,
    context_course $context
): void {
    if ((int) get_config('local_tuneai', 'enabled') !== 1) {
        return;
    }
    if (!has_any_capability(
        ['local/tuneai:submit', 'local/tuneai:manage', 'local/tuneai:viewresults'],
        $context
    )) {
        return;
    }
    $parentnode->add(
        get_string('coursenav', 'local_tuneai'),
        new moodle_url('/local/tuneai/index.php', ['courseid' => $course->id]),
        navigation_node::TYPE_SETTING,
        null,
        'local_tuneai'
    );
}
