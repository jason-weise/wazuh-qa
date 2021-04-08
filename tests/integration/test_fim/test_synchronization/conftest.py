# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import pytest

from wazuh_testing.fim import LOG_FILE_PATH, detect_initial_scan, detect_realtime_start, detect_whodata_start
from wazuh_testing.tools.file import truncate_file
from wazuh_testing.tools.monitoring import FileMonitor
from wazuh_testing.tools.services import control_service


@pytest.fixture(scope='module')
def restart_syscheckd(get_configuration, request):
    """
    Reset wazuh.log and start a new monitor.
    """
    control_service('stop', daemon='wazuh-syscheckd')
    truncate_file(LOG_FILE_PATH)
    file_monitor = FileMonitor(LOG_FILE_PATH)
    setattr(request.module, 'wazuh_log_monitor', file_monitor)
    control_service('start', daemon='wazuh-syscheckd')


@pytest.fixture(scope='module')
def wait_for_fim_start(get_configuration, request):
    """
    Wait for realtime start, whodata start or end of initial FIM scan.
    """
    file_monitor = getattr(request.module, 'wazuh_log_monitor')
    mode_key = 'fim_mode' if 'fim_mode2' not in get_configuration['metadata'] else 'fim_mode2'

    try:
        if get_configuration['metadata'][mode_key] == 'realtime':
            detect_realtime_start(file_monitor)
        elif get_configuration['metadata'][mode_key] == 'whodata':
            detect_whodata_start(file_monitor)
        else:  # scheduled
            detect_initial_scan(file_monitor)
    except KeyError:
        detect_initial_scan(file_monitor)


@pytest.fixture(scope='module')
def wait_for_fim_start_sync_disabled(request):
    """
    Wait for en of initial FIM scan.

    If detect_realtime_start is used, the synchronization event is skipped and the test fails.
    """
    file_monitor = getattr(request.module, 'wazuh_log_monitor')
    detect_initial_scan(file_monitor)
