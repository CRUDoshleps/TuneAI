<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

namespace local_tuneai;

defined('MOODLE_INTERNAL') || die();

class question_reader {
    public function read_question_attempt(int $questionattemptid): array {
        global $DB;
        $attempt = $DB->get_record('question_attempts', ['id' => $questionattemptid], '*', MUST_EXIST);
        $answer = $this->latest_answer_text($questionattemptid);
        return [
            'questionattemptid' => $questionattemptid,
            'questionusageid' => (int) $attempt->questionusageid,
            'questionid' => (int) $attempt->questionid,
            'questiontext' => trim((string) ($attempt->questionsummary ?? '')),
            'answertext' => $answer !== '' ? $answer : trim((string) ($attempt->responsesummary ?? '')),
        ];
    }

    private function latest_answer_text(int $questionattemptid): string {
        global $DB;
        $sql = "SELECT qasd.value
                  FROM {question_attempt_steps} qas
                  JOIN {question_attempt_step_data} qasd ON qasd.attemptstepid = qas.id
                 WHERE qas.questionattemptid = :questionattemptid
                   AND qasd.name IN ('answer', 'answertext', 'response', 'text')
              ORDER BY qas.sequencenumber DESC, qasd.id DESC";
        $records = $DB->get_records_sql($sql, ['questionattemptid' => $questionattemptid], 0, 1);
        if (!$records) {
            return '';
        }
        $record = reset($records);
        return trim((string) $record->value);
    }
}
