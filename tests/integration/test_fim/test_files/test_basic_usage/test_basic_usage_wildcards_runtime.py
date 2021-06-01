# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import os
import sys
import pytest
from shutil import rmtree
from wazuh_testing import global_parameters
from wazuh_testing import fim
from wazuh_testing.tools import PREFIX
from wazuh_testing.tools.configuration import load_wazuh_configurations, check_apply_test
from wazuh_testing.tools.monitoring import FileMonitor

# marks

pytestmark = pytest.mark.tier(level=0)

# variables

test_folder = os.path.join(PREFIX, 'test_folder')
test_directories = [test_folder]
frequency_scan = 10
matched_dirs = ['simple1', 'stars123']
test_subdirectories = matched_dirs + ['not_monitored_directory']
expresions = [os.path.join(test_folder, 'simple?'),
              os.path.join(test_folder, 'star*')]

expresion_str = ','.join(expresions)
wazuh_log_monitor = FileMonitor(fim.LOG_FILE_PATH)
test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'wazuh_conf_wildcards_rt.yml')

# configurations

conf_params = {'TEST_WILDCARDS': expresion_str, 'FREQUENCY': frequency_scan}
parameters, metadata = fim.generate_params(extra_params=conf_params)
configurations = load_wazuh_configurations(configurations_path, __name__, params=parameters, metadata=metadata)

# fixtures


@pytest.fixture(scope='module', params=configurations)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


@pytest.fixture(scope='module')
def wait_for_initial_scan():
    """Fixture that waits for the initial scan, independently of the configured mode."""
    fim.detect_initial_scan(wazuh_log_monitor)


@pytest.fixture()
def create_test_folders():
    """Fixture that creates all the folders specified in the `test_subdirectories` list"""
    for sub_directory in test_subdirectories:
        if not os.path.exists(os.path.join(test_folder, sub_directory)):
            os.mkdir(os.path.join(test_folder, sub_directory))


@pytest.fixture()
def remove_test_folders():
    """Fixture that removes all the folders specified in the `test_subdirectories` list"""
    for sub_directory in test_subdirectories:
        if os.path.exists(os.path.join(test_folder, sub_directory)):
            rmtree(os.path.join(test_folder, sub_directory))


@pytest.fixture()
def wait_for_wildcards_scan():
    """Fixture that waits until the end of the wildcards scan.
    The wildcards scan is triggered at the beggining of the FIM scan)."""
    wazuh_log_monitor.start(timeout=global_parameters.default_timeout + frequency_scan,
                            callback=fim.callback_detect_end_scan,
                            error_message='End of FIM scan not detected').result()


@pytest.mark.parametrize('parent_folder', [test_folder])
@pytest.mark.parametrize('subfolder_name', test_subdirectories)
@pytest.mark.parametrize('file_name', ['regular_1'])
@pytest.mark.parametrize('tags_to_apply', [{'ossec_conf_wildcards_runtime'}])
def test_basic_usage_wildcards_runtime(parent_folder, subfolder_name, file_name, tags_to_apply,
                                       get_configuration, configure_environment, remove_test_folders, restart_syscheckd,
                                       wait_for_initial_scan, create_test_folders, wait_for_wildcards_scan):
    """Test the expansion once a given directory matches a configured expresion.

    The test monitors a given expresion and will create folders that match the configured expresion. It also creates
    folders that doesn't match the expresion and check that no event is triggered if changes are made inside a folder
    that doesn't match the glob expresion.
    Params:
        parent_folder (str): Name of the root folder.
        subfolder_name (str): Name of the subfolder under root folder.
        file_name (str): Name of the file that will be created under subfolder.
        tags_to_apply (str): Value holding the configuration used in the test.
        get_configuration (fixture): Gets the current configuration of the test.
        configure_environment (fixture): Configure the environment for the execution of the test.
        remove_test_folders (fixture): Fixture that will delete all folders inside the test folder
        restart_syscheckd (fixture): Restarts syscheck.
        wait_for_initial_scan (fixture): Waits until the first FIM scan is completed.
        create_test_folders (fixture): Creates the folders that will match (or not) the configured glob expresion.
        wait_for_wildcards_scan (fixture): Waits until the end of wildcards scan event is triggered.
    """
    check_apply_test(tags_to_apply, get_configuration['tags'])
    if sys.platform == 'win32':
        if '?' in file_name or '*' in file_name:
            pytest.skip("Windows can't create files with wildcards.")

    folder_path = os.path.join(parent_folder, subfolder_name)

    fim.regular_file_cud(folder_path, wazuh_log_monitor, file_list=[file_name],
                         time_travel=get_configuration['metadata']['fim_mode'] == 'scheduled',
                         min_timeout=global_parameters.default_timeout, triggers_event=subfolder_name in matched_dirs)
