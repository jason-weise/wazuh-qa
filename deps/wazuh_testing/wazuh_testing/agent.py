# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import re


# Callbacks
def callback_state_interval_not_valid(line):
    match = re.match(r'.*Invalid definition for agent.state_interval:', line)
    if match:
        return True
    return None


def callback_state_interval_not_found(line):
    match = re.match(r".*Definition not found for: 'agent.state_interval'",
                     line)
    if match:
        return True
    return None


def callback_state_file_not_enabled(line):
    match = re.match(r'.*State file is disabled', line)
    if match:
        return True
    return None


def callback_state_file_enabled(line):
    match = re.match(r'.*State file updating thread started', line)
    if match:
        return True
    return None
