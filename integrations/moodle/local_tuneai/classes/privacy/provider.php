<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

namespace local_tuneai\privacy;

use core_privacy\local\metadata\collection;
use core_privacy\local\request\approved_contextlist;
use core_privacy\local\request\contextlist;
use core_privacy\local\request\writer;

defined('MOODLE_INTERNAL') || die();

/**
 * Privacy provider for the TuneAI Moodle integration.
 *
 * @package    local_tuneai
 * @copyright  2026 CRUDoshleps
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class provider implements
    \core_privacy\local\metadata\provider,
    \core_privacy\local\request\plugin\provider {

    public static function get_metadata(collection $collection): collection {
        $collection->add_database_table(
            'local_tuneai_submission',
            [
                'external_submission_id' => 'privacy:metadata:submission:externalid',
                'courseid' => 'privacy:metadata:submission:courseid',
                'cmid' => 'privacy:metadata:submission:cmid',
                'questionattemptid' => 'privacy:metadata:submission:questionattemptid',
                'userid' => 'privacy:metadata:submission:userid',
                'groupid' => 'privacy:metadata:submission:groupid',
                'tuneai_test_id' => 'privacy:metadata:submission:tuneaitestid',
                'tuneai_question_id' => 'privacy:metadata:submission:tuneaiquestionid',
                'tuneai_attempt_id' => 'privacy:metadata:submission:tuneaiattemptid',
                'tuneai_answer_id' => 'privacy:metadata:submission:tuneaianswerid',
                'answer_status' => 'privacy:metadata:submission:answerstatus',
                'result_ready' => 'privacy:metadata:submission:resultready',
                'score' => 'privacy:metadata:submission:score',
                'max_score' => 'privacy:metadata:submission:maxscore',
                'grade' => 'privacy:metadata:submission:grade',
                'feedback' => 'privacy:metadata:submission:feedback',
                'confidence' => 'privacy:metadata:submission:confidence',
                'review_reason' => 'privacy:metadata:submission:reviewreason',
                'transcript' => 'privacy:metadata:submission:transcript',
                'teacher_signal' => 'privacy:metadata:submission:teachersignal',
                'sync_attempts' => 'privacy:metadata:submission:syncattempts',
                'next_sync_time' => 'privacy:metadata:submission:nextsynctime',
                'last_error' => 'privacy:metadata:submission:lasterror',
                'timecreated' => 'privacy:metadata:submission:timecreated',
                'timemodified' => 'privacy:metadata:submission:timemodified',
            ],
            'privacy:metadata:submission'
        );
        $collection->add_external_location_link(
            'tuneai',
            [
                'moodle_user_id' => 'privacy:metadata:tuneai:moodleuserid',
                'user_email' => 'privacy:metadata:tuneai:useremail',
                'user_full_name' => 'privacy:metadata:tuneai:fullname',
                'moodle_course_id' => 'privacy:metadata:tuneai:courseid',
                'moodle_activity_id' => 'privacy:metadata:tuneai:activityid',
                'answer' => 'privacy:metadata:tuneai:answer',
            ],
            'privacy:metadata:tuneai'
        );
        return $collection;
    }

    public static function get_contexts_for_userid(int $userid): contextlist {
        $contextlist = new contextlist();
        $sql = "SELECT DISTINCT ctx.id
                  FROM {context} ctx
                  JOIN {local_tuneai_submission} submission
                    ON submission.courseid = ctx.instanceid
                 WHERE ctx.contextlevel = :contextlevel
                   AND submission.userid = :userid";
        $contextlist->add_from_sql($sql, ['contextlevel' => CONTEXT_COURSE, 'userid' => $userid]);
        return $contextlist;
    }

    public static function export_user_data(approved_contextlist $contextlist): void {
        global $DB;
        $courseids = self::course_ids($contextlist);
        if (!$courseids) {
            return;
        }
        $userid = (int) $contextlist->get_user()->id;
        foreach ($courseids as $courseid) {
            $records = $DB->get_records(
                'local_tuneai_submission',
                ['courseid' => $courseid, 'userid' => $userid],
                'timecreated ASC'
            );
            foreach ($records as $record) {
                writer::with_context(\context_course::instance($courseid))->export_data(
                    [get_string('privacy:submissionpath', 'local_tuneai'), (string) $record->id],
                    $record
                );
            }
        }
    }

    public static function delete_data_for_all_users_in_context(\context $context): void {
        global $DB;
        if ($context->contextlevel !== CONTEXT_COURSE) {
            return;
        }
        $DB->delete_records('local_tuneai_submission', ['courseid' => $context->instanceid]);
    }

    public static function delete_data_for_user(approved_contextlist $contextlist): void {
        global $DB;
        $courseids = self::course_ids($contextlist);
        if (!$courseids) {
            return;
        }
        [$insql, $params] = $DB->get_in_or_equal($courseids, SQL_PARAMS_NAMED, 'course');
        $params['userid'] = (int) $contextlist->get_user()->id;
        $DB->delete_records_select(
            'local_tuneai_submission',
            "userid = :userid AND courseid {$insql}",
            $params
        );
    }

    private static function course_ids(approved_contextlist $contextlist): array {
        $courseids = [];
        foreach ($contextlist->get_contexts() as $context) {
            if ($context->contextlevel === CONTEXT_COURSE) {
                $courseids[] = (int) $context->instanceid;
            }
        }
        return array_values(array_unique($courseids));
    }
}
