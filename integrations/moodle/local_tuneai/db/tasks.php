<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

defined('MOODLE_INTERNAL') || die();

$tasks = [
    [
        'classname' => 'local_tuneai\task\sync_submissions',
        'blocking' => 0,
        'minute' => '*/5',
        'hour' => '*',
        'day' => '*',
        'month' => '*',
        'dayofweek' => '*',
    ],
];
