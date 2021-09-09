'''
copyright:
    Copyright (C) 2015-2021, Wazuh Inc.

    Created by Wazuh, Inc. <info@wazuh.com>.

    This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type:
    integration

brief:
    These tests will check that the API works correctly using the `HTTPS` protocol.

tier:
    0

modules:
    - api

components:
    - manager

path:
    tests/integration/test_api/test_config/test_https/test_https.py

daemons:
    - wazuh-apid
    - wazuh-analysisd
    - wazuh-syscheckd
    - wazuh-db

os_platform:
    - linux

os_version:
    - Amazon Linux 1
    - Amazon Linux 2
    - Arch Linux
    - CentOS 6
    - CentOS 7
    - CentOS 8
    - Debian Buster
    - Debian Stretch
    - Debian Jessie
    - Debian Wheezy
    - Red Hat 6
    - Red Hat 7
    - Red Hat 8
    - Ubuntu Bionic
    - Ubuntu Trusty
    - Ubuntu Xenial

references:
    - https://documentation.wazuh.com/current/user-manual/api/getting-started.html
    - https://documentation.wazuh.com/current/user-manual/api/configuration.html#https

tags:
    - api
'''
import os

import pytest
import requests
from wazuh_testing.tools import PREFIX
from wazuh_testing.tools.configuration import check_apply_test, get_api_conf

# Marks

pytestmark = pytest.mark.server

# Variables

test_directories = [os.path.join(PREFIX, 'test_cert')]

# Configurations

test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'conf.yaml')
configuration = get_api_conf(configurations_path)


# Fixtures

@pytest.fixture(scope='module', params=configuration)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


# Tests

@pytest.mark.parametrize('tags_to_apply', [
    {'https_disabled'},
    {'https_enabled'},
])
def test_https(tags_to_apply, get_configuration, configure_api_environment,
               restart_api, wait_for_start, get_api_details):
    '''
    description:
        Check that the API works with `HTTP` and `HTTPS` protocols.
        To do this, it configures the API to use both protocols
        and makes requests to it, waiting for a correct response.

    wazuh_min_version:
        4.2

    parameters:
        - tags_to_apply:
            type: set
            brief: Run test if match with a configuration identifier, skip otherwise.
        - get_configuration:
            type: fixture
            brief: Get configurations from the module.
        - configure_api_environment:
            type: fixture
            brief: Configure a custom environment for API testing.
        - restart_api:
            type: fixture
            brief: Reset `api.log` and start a new monitor.
        - wait_for_start:
            type: fixture
            brief: Wait until the API starts.
        - get_api_details:
            type: fixture
            brief: Get API information.

    assertions:
        - Verify that the API requests are made correctly using both `HTTP` and `HTTPS` protocols.

    input_description:
        Different test cases are contained in an external `YAML` file (conf.yaml)
        which includes API configuration parameters (HTTPS settings).

    expected_output:
        - r'200' ('OK' HTTP status code)

    tags:
        - ssl
    '''
    check_apply_test(tags_to_apply, get_configuration['tags'])
    https = get_configuration['configuration']['https']['enabled']
    api_details = get_api_details(protocol='https' if https else 'http')

    get_response = requests.get(api_details['base_url'], headers=api_details['auth_headers'], verify=False)

    assert get_response.status_code == 200, f'Expected status code was 200, but {get_response.status_code} was ' \
                                            f'returned. \nFull response: {get_response.text}'
