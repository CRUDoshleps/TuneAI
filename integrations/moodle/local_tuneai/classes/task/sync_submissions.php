<?php
namespace local_tuneai\task;

defined('MOODLE_INTERNAL') || die();

class sync_submissions extends \core\task\scheduled_task {
    public function get_name(): string {
        return get_string('tasksyncsubmissions', 'local_tuneai');
    }

    public function execute(): void {
        if ((int) get_config('local_tuneai', 'enabled') !== 1) {
            return;
        }
        $repository = new \local_tuneai\mapping_repository();
        $service = new \local_tuneai\submission_service(null, $repository);
        foreach ($repository->pending_submissions(50) as $submission) {
            try {
                $service->refresh_submission_result($submission->external_submission_id);
            } catch (\Throwable $exception) {
                $repository->mark_sync_error($submission, $exception->getMessage());
            }
        }
    }
}
