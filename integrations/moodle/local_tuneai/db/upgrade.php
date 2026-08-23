<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

defined('MOODLE_INTERNAL') || die();

function xmldb_local_tuneai_upgrade($oldversion) {
    global $DB;

    $dbman = $DB->get_manager();

    if ($oldversion < 2026080601) {
        $table = new xmldb_table('local_tuneai_submission');
        $fields = [
            new xmldb_field('sync_attempts', XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL, null, '0', 'feedback'),
            new xmldb_field('next_sync_time', XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL, null, '0', 'sync_attempts'),
            new xmldb_field('last_error', XMLDB_TYPE_TEXT, null, null, null, null, null, 'next_sync_time'),
        ];
        foreach ($fields as $field) {
            if (!$dbman->field_exists($table, $field)) {
                $dbman->add_field($table, $field);
            }
        }
        $index = new xmldb_index('next_sync_time', XMLDB_INDEX_NOTUNIQUE, ['next_sync_time']);
        if (!$dbman->index_exists($table, $index)) {
            $dbman->add_index($table, $index);
        }
        upgrade_plugin_savepoint(true, 2026080601, 'local', 'tuneai');
    }

    if ($oldversion < 2026082300) {
        $maptable = new xmldb_table('local_tuneai_map');
        $answermode = new xmldb_field(
            'answer_mode',
            XMLDB_TYPE_CHAR,
            '16',
            null,
            XMLDB_NOTNULL,
            null,
            'both',
            'methodist_email'
        );
        if (!$dbman->field_exists($maptable, $answermode)) {
            $dbman->add_field($maptable, $answermode);
        }

        $submissiontable = new xmldb_table('local_tuneai_submission');
        $submissionfields = [
            new xmldb_field('confidence', XMLDB_TYPE_NUMBER, '10, 6', null, null, null, null, 'feedback'),
            new xmldb_field('review_reason', XMLDB_TYPE_TEXT, null, null, null, null, null, 'confidence'),
            new xmldb_field('transcript', XMLDB_TYPE_TEXT, null, null, null, null, null, 'review_reason'),
        ];
        foreach ($submissionfields as $field) {
            if (!$dbman->field_exists($submissiontable, $field)) {
                $dbman->add_field($submissiontable, $field);
            }
        }
        upgrade_plugin_savepoint(true, 2026082300, 'local', 'tuneai');
    }

    if ($oldversion < 2026082301) {
        $sql = "SELECT MIN(id) AS id, courseid, cmid, questionid, COUNT(*) AS mappingcount
                  FROM {local_tuneai_map}
                 WHERE groupid IS NULL
              GROUP BY courseid, cmid, questionid
                HAVING COUNT(*) > 1";
        foreach ($DB->get_records_sql($sql) as $duplicate) {
            $records = $DB->get_records_select(
                'local_tuneai_map',
                'courseid = :courseid AND cmid = :cmid AND questionid = :questionid AND groupid IS NULL',
                [
                    'courseid' => $duplicate->courseid,
                    'cmid' => $duplicate->cmid,
                    'questionid' => $duplicate->questionid,
                ],
                'timemodified DESC, id DESC'
            );
            array_shift($records);
            if ($records) {
                $DB->delete_records_list('local_tuneai_map', 'id', array_keys($records));
            }
        }
        $DB->set_field_select('local_tuneai_map', 'groupid', 0, 'groupid IS NULL');
        $maptable = new xmldb_table('local_tuneai_map');
        $groupfield = new xmldb_field(
            'groupid',
            XMLDB_TYPE_INTEGER,
            '10',
            null,
            XMLDB_NOTNULL,
            null,
            '0',
            'questionid'
        );
        $dbman->change_field_notnull($maptable, $groupfield);
        $dbman->change_field_default($maptable, $groupfield);
        upgrade_plugin_savepoint(true, 2026082301, 'local', 'tuneai');
    }

    if ($oldversion < 2026082302) {
        $maptable = new xmldb_table('local_tuneai_map');
        $questiontext = new xmldb_field(
            'question_text',
            XMLDB_TYPE_TEXT,
            null,
            null,
            null,
            null,
            null,
            'tuneai_question_id'
        );
        if (!$dbman->field_exists($maptable, $questiontext)) {
            $dbman->add_field($maptable, $questiontext);
        }
        upgrade_plugin_savepoint(true, 2026082302, 'local', 'tuneai');
    }

    return true;
}
