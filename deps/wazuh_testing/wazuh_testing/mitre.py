# Copyright (C) 2015-2020, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import json
import os
import re

from jsonschema import validate

_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')


def validate_mitre_event(event):
    """
    Check if a Mitre event is properly formatted.

    Parameters
    ----------
    event : dict
        Event generated by rule enhanced by MITRE.
    """
    with open(os.path.join(_data_path, 'mitre_event.json'), 'r') as f:
        schema = json.load(f)
    validate(schema=schema, instance=event)


def callback_detect_mitre_event(line):
    """
    Callback to detect Mitre event

    Parameters
    ----------
    line : str
        Text to be compared with alerts in ossec.log

    Returns
    -------
        dict
            JSON object on success or None on fail
    """
    match = re.match(r'.*Ossec started again with Mitre information for testing.*', line)
    if match:
        return json.loads(line)
    return None
