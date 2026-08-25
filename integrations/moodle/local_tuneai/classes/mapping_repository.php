<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

namespace local_tuneai;

defined('MOODLE_INTERNAL') || die();

class mapping_repository {
    public const MAP_TABLE = 'local_tuneai_map';
    public const SUBMISSION_TABLE = 'local_tuneai_submission';

    public function upsert_mapping(
        int $courseid,
        int $cmid,
        int $questionid,
        ?int $groupid,
        string $tuneaitestid,
        string $tuneaiquestionid,
        ?string $methodistemail,
        string $answermode = 'both',
        ?string $questiontext = null
    ): \stdClass {
        global $DB;
        $params = [
            'courseid' => $courseid,
            'cmid' => $cmid,
            'questionid' => $questionid,
            'groupid' => $groupid ?: 0,
        ];
        $record = $DB->get_record(self::MAP_TABLE, $params);
        $now = time();
        if (!$record) {
            $record = (object) $params;
            $record->timecreated = $now;
        }
        $record->tuneai_test_id = $tuneaitestid;
        $record->tuneai_question_id = $tuneaiquestionid;
        $record->question_text = $questiontext;
        $record->methodist_email = $methodistemail ? \core_text::strtolower($methodistemail) : null;
        $record->answer_mode = in_array($answermode, ['audio', 'text', 'both'], true) ? $answermode : 'both';
        $record->timemodified = $now;
        if (!empty($record->id)) {
            $DB->update_record(self::MAP_TABLE, $record);
        } else {
            $record->id = $DB->insert_record(self::MAP_TABLE, $record);
        }
        return $record;
    }

    public function find_mapping(int $courseid, int $cmid, int $questionid, ?int $groupid): ?\stdClass {
        global $DB;
        if ($groupid !== null) {
            $record = $DB->get_record(self::MAP_TABLE, [
                'courseid' => $courseid,
                'cmid' => $cmid,
                'questionid' => $questionid,
                'groupid' => $groupid,
            ]);
            if ($record) {
                return $record;
            }
        }
        $sql = 'courseid = :courseid AND cmid = :cmid AND questionid = :questionid AND groupid = 0';
        $records = $DB->get_records_select(self::MAP_TABLE, $sql, [
            'courseid' => $courseid,
            'cmid' => $cmid,
            'questionid' => $questionid,
        ], 'id DESC', '*', 0, 1);
        return $records ? reset($records) : null;
    }

    public function course_mappings(int $courseid): array {
        global $DB;
        return array_values($DB->get_records(self::MAP_TABLE, ['courseid' => $courseid], 'cmid, questionid, groupid'));
    }

    public function get_mapping(int $mappingid, int $courseid): ?\stdClass {
        global $DB;
        $record = $DB->get_record(self::MAP_TABLE, ['id' => $mappingid, 'courseid' => $courseid]);
        return $record ?: null;
    }

    public function course_submissions(int $courseid, int $limit = 50, int $offset = 0): array {
        global $DB;
        return array_values($DB->get_records(
            self::SUBMISSION_TABLE,
            ['courseid' => $courseid],
            'timecreated DESC',
            '*',
            $offset,
            $limit
        ));
    }

    public function count_course_submissions(int $courseid): int {
        global $DB;
        return $DB->count_records(self::SUBMISSION_TABLE, ['courseid' => $courseid]);
    }

    public function save_submission(array $result, array $context): \stdClass {
        global $DB;
        $record = $DB->get_record(self::SUBMISSION_TABLE, ['external_submission_id' => $result['external_submission_id']]);
        $now = time();
        if (!$record) {
            $record = new \stdClass();
            $record->external_submission_id = $result['external_submission_id'];
            $record->courseid = $context['courseid'];
            $record->cmid = $context['cmid'];
            $record->questionattemptid = $context['questionattemptid'] ?? null;
            $record->userid = $context['userid'];
            $record->groupid = $context['groupid'] ?? null;
            $record->tuneai_test_id = $context['tuneai_test_id'];
            $record->tuneai_question_id = $context['tuneai_question_id'];
            $record->timecreated = $now;
        }
        $record->tuneai_attempt_id = $result['attempt_id'] ?? null;
        $record->tuneai_answer_id = $result['answer_id'] ?? null;
        $record->answer_status = $result['answer_status'] ?? null;
        $record->result_ready = !empty($result['result_ready']) ? 1 : 0;
        $record->score = $result['score'] ?? null;
        $record->max_score = $result['max_score'] ?? null;
        $record->grade = $result['grade'] ?? null;
        $record->teacher_signal = $result['teacher_signal'] ?? null;
        $record->feedback = $result['feedback'] ?? null;
        $record->confidence = $result['confidence'] ?? null;
        $record->review_reason = $result['review_reason'] ?? null;
        $record->transcript = $result['transcript'] ?? null;
        $record->last_error = null;
        $answerstatus = (string) ($result['answer_status'] ?? '');
        $teachersignal = (string) ($result['teacher_signal'] ?? 'none');
        if ($answerstatus === 'failed') {
            $record->next_sync_time = 0;
        } else if (!empty($result['result_ready']) && $teachersignal === 'none') {
            $record->next_sync_time = 0;
            $record->sync_attempts = 0;
        } else if (!empty($result['result_ready']) && $teachersignal === 'review_recommended') {
            $record->next_sync_time = time() + 300;
        } else {
            $record->next_sync_time = time() + 30;
        }
        $record->timemodified = $now;
        if (!empty($record->id)) {
            $DB->update_record(self::SUBMISSION_TABLE, $record);
        } else {
            $record->id = $DB->insert_record(self::SUBMISSION_TABLE, $record);
        }
        return $record;
    }

    public function find_submission(string $externalsubmissionid): ?\stdClass {
        global $DB;
        $record = $DB->get_record(self::SUBMISSION_TABLE, ['external_submission_id' => $externalsubmissionid]);
        return $record ?: null;
    }

    public function pending_submissions(int $limit = 50): array {
        global $DB;
        $sql = "next_sync_time > 0
                AND next_sync_time <= :now
                AND (result_ready = 0 OR teacher_signal = 'review_recommended')";
        return array_values($DB->get_records_select(self::SUBMISSION_TABLE, $sql, ['now' => time()], 'timemodified ASC', '*', 0, $limit));
    }

    public function mark_sync_error(\stdClass $submission, string $message): void {
        global $DB;
        $attempts = ((int) ($submission->sync_attempts ?? 0)) + 1;
        $delay = min(3600, 30 * (2 ** min($attempts, 6)));
        $submission->sync_attempts = $attempts;
        if ($attempts >= 10) {
            $submission->answer_status = 'sync_failed';
            $submission->teacher_signal = 'processing_failed';
            $submission->next_sync_time = 0;
        } else {
            $submission->next_sync_time = time() + $delay;
        }
        $submission->last_error = \core_text::substr($message, 0, 4000);
        $submission->timemodified = time();
        $DB->update_record(self::SUBMISSION_TABLE, $submission);
    }
}
