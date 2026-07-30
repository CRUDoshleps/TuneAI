<?php
defined('MOODLE_INTERNAL') || die();

if ($hassiteconfig) {
    $settings = new admin_settingpage('local_tuneai', get_string('pluginname', 'local_tuneai'));
    $ADMIN->add('localplugins', $settings);

    $settings->add(new admin_setting_configcheckbox(
        'local_tuneai/enabled',
        get_string('enabled', 'local_tuneai'),
        get_string('enabled_desc', 'local_tuneai'),
        0
    ));

    $settings->add(new admin_setting_configtext(
        'local_tuneai/baseurl',
        get_string('baseurl', 'local_tuneai'),
        get_string('baseurl_desc', 'local_tuneai'),
        '',
        PARAM_URL
    ));

    $settings->add(new admin_setting_configpasswordunmask(
        'local_tuneai/integrationkey',
        get_string('integrationkey', 'local_tuneai'),
        get_string('integrationkey_desc', 'local_tuneai'),
        ''
    ));

    $settings->add(new admin_setting_configtext(
        'local_tuneai/timeout',
        get_string('timeout', 'local_tuneai'),
        get_string('timeout_desc', 'local_tuneai'),
        '20',
        PARAM_INT
    ));
}
