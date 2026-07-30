<?php
namespace local_tuneai;

defined('MOODLE_INTERNAL') || die();

require_once($CFG->libdir . '/filelib.php');

class client {
    private string $baseurl;
    private string $integrationkey;
    private int $timeout;

    public function __construct(?string $baseurl = null, ?string $integrationkey = null, ?int $timeout = null) {
        $this->baseurl = rtrim($baseurl ?? (string) get_config('local_tuneai', 'baseurl'), '/');
        $this->integrationkey = $integrationkey ?? (string) get_config('local_tuneai', 'integrationkey');
        $this->timeout = $timeout ?? (int) (get_config('local_tuneai', 'timeout') ?: 20);
    }

    public function manifest(?string $methodistemail = null, ?string $testid = null): array {
        $params = [];
        if ($methodistemail !== null && $methodistemail !== '') {
            $params['methodist_email'] = \core_text::strtolower($methodistemail);
        }
        if ($testid !== null && $testid !== '') {
            $params['test_id'] = $testid;
        }
        return $this->request('GET', '/integrations/moodle/manifest', $params);
    }

    public function submit_text(array $payload): array {
        return $this->request('POST', '/integrations/moodle/submissions/text', $payload);
    }

    public function submit_audio(array $payload, string $filepath, string $filename, string $contenttype): array {
        if ((int) get_config('local_tuneai', 'enabled') !== 1) {
            throw new \moodle_exception('TuneAI is disabled');
        }
        if ($this->baseurl === '' || $this->integrationkey === '') {
            throw new \moodle_exception('TuneAI base URL and integration key are required');
        }
        if (!is_readable($filepath)) {
            throw new \moodle_exception('TuneAI audio file is not readable');
        }
        $curl = new \curl();
        $curl->setHeader('X-TuneAI-Integration-Key: ' . $this->integrationkey);
        $curl->setopt(['CURLOPT_TIMEOUT' => $this->timeout]);
        $fields = [];
        foreach ($payload as $key => $value) {
            if ($value !== null) {
                $fields[$key] = (string) $value;
            }
        }
        $fields['file'] = new \CURLFile($filepath, $contenttype, $filename);
        $response = $curl->post($this->baseurl . '/integrations/moodle/submissions/audio', $fields);
        $info = $curl->get_info();
        $status = (int) ($info['http_code'] ?? 0);
        $decoded = json_decode((string) $response, true);
        if ($status < 200 || $status >= 300 || !is_array($decoded)) {
            throw new \moodle_exception('TuneAI audio request failed: HTTP ' . $status . ' ' . (string) $response);
        }
        return $decoded;
    }

    public function result(string $externalsubmissionid): array {
        return $this->request('GET', '/integrations/moodle/submissions/' . rawurlencode($externalsubmissionid) . '/result', []);
    }

    private function request(string $method, string $path, array $payload): array {
        if ((int) get_config('local_tuneai', 'enabled') !== 1) {
            throw new \moodle_exception('TuneAI is disabled');
        }
        if ($this->baseurl === '' || $this->integrationkey === '') {
            throw new \moodle_exception('TuneAI base URL and integration key are required');
        }
        $curl = new \curl();
        $curl->setHeader('X-TuneAI-Integration-Key: ' . $this->integrationkey);
        $curl->setHeader('Content-Type: application/json');
        $curl->setopt(['CURLOPT_TIMEOUT' => $this->timeout]);
        $url = $this->baseurl . $path;
        if ($method === 'GET') {
            if ($payload) {
                $url .= '?' . http_build_query($payload);
            }
            $response = $curl->get($url);
        } else {
            $response = $curl->post($url, json_encode($payload, JSON_UNESCAPED_UNICODE));
        }
        $info = $curl->get_info();
        $status = (int) ($info['http_code'] ?? 0);
        $decoded = json_decode((string) $response, true);
        if ($status < 200 || $status >= 300 || !is_array($decoded)) {
            throw new \moodle_exception('TuneAI request failed: HTTP ' . $status . ' ' . (string) $response);
        }
        return $decoded;
    }
}
