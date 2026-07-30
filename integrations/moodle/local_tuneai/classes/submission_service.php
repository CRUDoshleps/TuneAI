<?php
namespace local_tuneai;

defined('MOODLE_INTERNAL') || die();

class submission_service {
    private client $client;
    private mapping_repository $repository;
    private question_reader $reader;

    public function __construct(?client $client = null, ?mapping_repository $repository = null, ?question_reader $reader = null) {
        $this->client = $client ?? new client();
        $this->repository = $repository ?? new mapping_repository();
        $this->reader = $reader ?? new question_reader();
    }

    public function submit_question_attempt(int $courseid, int $cmid, int $questionattemptid, int $userid, ?int $groupid = null): array {
        global $DB;
        $qa = $this->reader->read_question_attempt($questionattemptid);
        $mapping = $this->repository->find_mapping($courseid, $cmid, $qa['questionid'], $groupid);
        if (!$mapping) {
            throw new \moodle_exception('TuneAI mapping was not found for this Moodle question');
        }
        $user = $DB->get_record('user', ['id' => $userid], '*', MUST_EXIST);
        $groupname = null;
        if ($groupid !== null) {
            $group = $DB->get_record('groups', ['id' => $groupid]);
            $groupname = $group ? $group->name : null;
        }
        $payload = [
            'external_submission_id' => $this->external_submission_id($courseid, $cmid, $questionattemptid, $userid, $groupid),
            'external_attempt_id' => 'moodle-cm-' . $cmid . '-user-' . $userid,
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
            'text' => $qa['answertext'],
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
        ?string $externalsubmissionid = null
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
            'external_attempt_id' => 'moodle-cm-' . $cmid . '-user-' . $userid,
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
}
