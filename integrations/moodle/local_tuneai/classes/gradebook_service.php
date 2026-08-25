<?php
// This file is part of Moodle - http://moodle.org/. Licensed under GNU GPL v3 or later.

namespace local_tuneai;

defined('MOODLE_INTERNAL') || die();

class gradebook_service {
    public function sync_result(array $result, \stdClass $submission): ?array {
        global $CFG;
        if ((int) get_config('local_tuneai', 'gradesync') !== 1) {
            return null;
        }
        if (empty($result['result_ready']) || !is_numeric($result['score'] ?? null) || !is_numeric($result['max_score'] ?? null)) {
            return null;
        }
        if (($result['teacher_signal'] ?? 'none') !== 'none') {
            return [
                'status' => 'review_required',
                'itemnumber' => null,
                'finalgrade' => null,
                'max_score' => (float) $result['max_score'],
            ];
        }
        require_once($CFG->libdir . '/gradelib.php');
        require_once($CFG->libdir . '/grade/grade_item.php');
        $score = (float) $result['score'];
        $maxscore = max(1.0, (float) $result['max_score']);
        $itemnumber = $this->item_number($submission);
        $idnumber = 'local_tuneai_' . $submission->cmid . '_' . $itemnumber;
        $itemdetails = [
            'itemname' => get_string('gradeitemname', 'local_tuneai', (object) [
                'cmid' => $submission->cmid,
                'questionid' => $submission->tuneai_question_id,
            ]),
            'idnumber' => $idnumber,
            'gradetype' => GRADE_TYPE_VALUE,
            'grademin' => 0,
            'grademax' => $maxscore,
        ];
        $itemparams = [
            'courseid' => (int) $submission->courseid,
            'itemtype' => 'manual',
            'iteminstance' => (int) $submission->cmid,
            'itemnumber' => $itemnumber,
        ];
        $gradeitem = \grade_item::fetch($itemparams);
        if (!$gradeitem) {
            $gradeitem = new \grade_item(array_merge($itemparams, $itemdetails), false);
            $gradeitem->insert('local/tuneai');
        } else {
            $changed = false;
            foreach ($itemdetails as $key => $value) {
                if ($gradeitem->{$key} != $value) {
                    $gradeitem->{$key} = $value;
                    $changed = true;
                }
            }
            if ($changed) {
                $gradeitem->update('local/tuneai');
            }
        }
        $updated = $gradeitem->update_final_grade(
            (int) $submission->userid,
            $score,
            'local/tuneai',
            (string) ($result['feedback'] ?? ''),
            FORMAT_PLAIN,
            null,
            time()
        );
        return [
            'status' => $updated ? GRADE_UPDATE_OK : GRADE_UPDATE_FAILED,
            'itemnumber' => $itemnumber,
            'finalgrade' => $score,
            'max_score' => $maxscore,
        ];
    }

    private function item_number(\stdClass $submission): int {
        return ((int) sprintf('%u', crc32((string) $submission->tuneai_question_id))) % 1000000000;
    }
}
