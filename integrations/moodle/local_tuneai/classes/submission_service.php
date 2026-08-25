<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

namespace local_tuneai;

defined('MOODLE_INTERNAL') || die();

class submission_service {
    private client $client;
    private mapping_repository $repository;
    private question_reader $reader;
    private gradebook_service $gradebook;

    public function __construct(?client $client = null, ?mapping_repository $repository = null, ?question_reader $reader = null, ?gradebook_service $gradebook = null) {
        $this->client = $client ?? new client();
        $this->repository = $repository ?? new mapping_repository();
        $this->reader = $reader ?? new question_reader();
        $this->gradebook = $gradebook ?? new gradebook_service();
    }

    public function submit_question_attempt(int $courseid, int $cmid, int $questionattemptid, int $userid, ?int $groupid = null): array {
        $qa = $this->reader->read_question_attempt($questionattemptid);
        return $this->submit_text_answer(
            $courseid,
            $cmid,
            $qa['questionid'],
            $userid,
            $qa['answertext'],
            $groupid,
            $this->external_submission_id($courseid, $cmid, $questionattemptid, $userid, $groupid),
            $questionattemptid,
            'moodle-quba-' . $qa['questionusageid'] . '-user-' . $userid
        );
    }

    public function submit_text_answer(
        int $courseid,
        int $cmid,
        int $questionid,
        int $userid,
        string $answertext,
        ?int $groupid = null,
        ?string $externalsubmissionid = null,
        ?int $questionattemptid = null,
        ?string $externalattemptid = null
    ): array {
        global $DB;
        $mapping = $this->repository->find_mapping($courseid, $cmid, $questionid, $groupid);
        if (!$mapping) {
            throw new \moodle_exception('TuneAI mapping was not found for this Moodle question');
        }
        $user = $DB->get_record('user', ['id' => $userid], '*', MUST_EXIST);
        $groupname = null;
        if ($groupid !== null) {
            $group = $DB->get_record('groups', ['id' => $groupid]);
            $groupname = $group ? $group->name : null;
        }
        $submissionid = $externalsubmissionid ?: $this->external_text_submission_id($courseid, $cmid, $questionid, $userid, $groupid);
        $payload = [
            'external_submission_id' => $submissionid,
            'external_attempt_id' => $externalattemptid ?: 'moodle-submission-' . $submissionid,
            'moodle_user_id' => (string) $userid,
            'moodle_course_id' => (string) $courseid,
            'moodle_activity_id' => (string) $cmid,
            'moodle_group_id' => $groupid !== null ? (string) $groupid : null,
            'moodle_group_name' => $groupname,
            'methodist_email' => $mapping->methodist_email ?: null,
            'user_email' => $user->email,
            'user_full_name' => fullname($user),
            'test_id' => $mapping->tuneai_test_id,
            'question_id' => $mapping->tuneai_question_id,
            'text' => $answertext,
        ];
        if (trim($payload['text']) === '') {
            throw new \moodle_exception('Moodle answer text is empty');
        }
        $result = $this->client->submit_text($payload);
        $this->repository->save_submission($result, [
            'courseid' => $courseid,
            'cmid' => $cmid,
            'questionattemptid' => $questionattemptid,
            'userid' => $userid,
            'groupid' => $groupid,
            'tuneai_test_id' => $mapping->tuneai_test_id,
            'tuneai_question_id' => $mapping->tuneai_question_id,
        ]);
        return $result;
    }

    public function submit_audio_file(
        int $courseid,
        int $cmid,
        int $questionid,
        int $userid,
        string $filepath,
        string $filename,
        string $contenttype,
        ?int $groupid = null,
        ?string $externalsubmissionid = null,
        ?string $externalattemptid = null
    ): array {
        global $DB;
        $mapping = $this->repository->find_mapping($courseid, $cmid, $questionid, $groupid);
        if (!$mapping) {
            throw new \moodle_exception('TuneAI mapping was not found for this Moodle question');
        }
        $user = $DB->get_record('user', ['id' => $userid], '*', MUST_EXIST);
        $groupname = null;
        if ($groupid !== null) {
            $group = $DB->get_record('groups', ['id' => $groupid]);
            $groupname = $group ? $group->name : null;
        }
        $submissionid = $externalsubmissionid ?: $this->external_audio_submission_id($courseid, $cmid, $questionid, $userid, $groupid);
        $payload = [
            'external_submission_id' => $submissionid,
            'external_attempt_id' => $externalattemptid ?: 'moodle-submission-' . $submissionid,
            'moodle_user_id' => (string) $userid,
            'moodle_course_id' => (string) $courseid,
            'moodle_activity_id' => (string) $cmid,
            'moodle_group_id' => $groupid !== null ? (string) $groupid : null,
            'moodle_group_name' => $groupname,
            'methodist_email' => $mapping->methodist_email ?: null,
            'user_email' => $user->email,
            'user_full_name' => fullname($user),
            'test_id' => $mapping->tuneai_test_id,
            'question_id' => $mapping->tuneai_question_id,
        ];
        $result = $this->client->submit_audio($payload, $filepath, $filename, $contenttype);
        $this->repository->save_submission($result, [
            'courseid' => $courseid,
            'cmid' => $cmid,
            'questionattemptid' => null,
            'userid' => $userid,
            'groupid' => $groupid,
            'tuneai_test_id' => $mapping->tuneai_test_id,
            'tuneai_question_id' => $mapping->tuneai_question_id,
        ]);
        return $result;
    }

    public function refresh_submission_result(string $externalsubmissionid): array {
        $submission = $this->repository->find_submission($externalsubmissionid);
        if (!$submission) {
            throw new \moodle_exception('TuneAI submission was not found in Moodle');
        }
        $result = $this->client->result($externalsubmissionid);
        $updated = $this->repository->save_submission($result, [
            'courseid' => (int) $submission->courseid,
            'cmid' => (int) $submission->cmid,
            'questionattemptid' => $submission->questionattemptid !== null ? (int) $submission->questionattemptid : null,
            'userid' => (int) $submission->userid,
            'groupid' => $submission->groupid !== null ? (int) $submission->groupid : null,
            'tuneai_test_id' => $submission->tuneai_test_id,
            'tuneai_question_id' => $submission->tuneai_question_id,
        ]);
        $gradesync = $this->gradebook->sync_result($result, $updated);
        if ($gradesync !== null) {
            $result['moodle_grade_sync'] = $gradesync;
        }
        return $result;
    }

    public function review_submission(
        string $externalsubmissionid,
        float $score,
        string $feedback,
        int $reviewerid,
        string $reviewername
    ): array {
        $submission = $this->repository->find_submission($externalsubmissionid);
        if (!$submission) {
            throw new \moodle_exception('TuneAI submission was not found in Moodle');
        }
        $result = $this->client->review($externalsubmissionid, [
            'score' => $score,
            'feedback' => $feedback,
            'reviewer_moodle_user_id' => (string) $reviewerid,
            'reviewer_name' => $reviewername,
        ]);
        $updated = $this->repository->save_submission($result, [
            'courseid' => (int) $submission->courseid,
            'cmid' => (int) $submission->cmid,
            'questionattemptid' => $submission->questionattemptid !== null ? (int) $submission->questionattemptid : null,
            'userid' => (int) $submission->userid,
            'groupid' => $submission->groupid !== null ? (int) $submission->groupid : null,
            'tuneai_test_id' => $submission->tuneai_test_id,
            'tuneai_question_id' => $submission->tuneai_question_id,
        ]);
        $gradesync = $this->gradebook->sync_result($result, $updated);
        if ($gradesync !== null) {
            $result['moodle_grade_sync'] = $gradesync;
        }
        return $result;
    }

    private function external_submission_id(int $courseid, int $cmid, int $questionattemptid, int $userid, ?int $groupid): string {
        $parts = ['course', $courseid, 'cm', $cmid, 'qa', $questionattemptid, 'user', $userid];
        if ($groupid !== null) {
            $parts[] = 'group';
            $parts[] = $groupid;
        }
        return implode('-', array_map('strval', $parts));
    }

    private function external_audio_submission_id(int $courseid, int $cmid, int $questionid, int $userid, ?int $groupid): string {
        $parts = ['course', $courseid, 'cm', $cmid, 'question', $questionid, 'user', $userid, 'audio'];
        if ($groupid !== null) {
            $parts[] = 'group';
            $parts[] = $groupid;
        }
        return implode('-', array_map('strval', $parts));
    }

    private function external_text_submission_id(int $courseid, int $cmid, int $questionid, int $userid, ?int $groupid): string {
        $parts = ['course', $courseid, 'cm', $cmid, 'question', $questionid, 'user', $userid, 'text'];
        if ($groupid !== null) {
            $parts[] = 'group';
            $parts[] = $groupid;
        }
        return implode('-', array_map('strval', $parts));
    }
}
