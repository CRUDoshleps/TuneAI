<?php
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

    return true;
}
