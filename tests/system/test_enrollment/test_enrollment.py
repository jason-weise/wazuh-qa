# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import os
import json
import socket
from netifaces import interfaces, ifaddresses, AF_INET
import pytest
from wazuh_testing.tools import WAZUH_PATH, WAZUH_LOGS_PATH
from wazuh_testing.tools.monitoring import HostMonitor
from wazuh_testing.tools.system import HostManager

# Hosts
testinfra_hosts = ["wazuh-manager", "wazuh-agent1"]

inventory_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              'provisioning', 'basic_environment', 'inventory.yml')
host_manager = HostManager(inventory_path)
local_path = os.path.dirname(os.path.abspath(__file__))
messages_path = os.path.join(local_path, 'data/messages.yml')
tmp_path = os.path.join(local_path, 'tmp')
agent_conf_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', 'provisioning', 'basic_environment', 'roles', 'agent-role', 'files', 'ossec.conf')

system_elements = ['manager', 'agent']
ip_format = ['ipv4', 'ipv6']

network_configuration = [
    {
        'name': 'manager_ipv4_agent_ipv4',
        'wazuh-manager': 'ipv4',
        'wazuh-agent1': 'ipv4'
    },
    {
        'name': 'manager_ipv6_agent_ipv4',
        'wazuh-manager': 'ipv6',
        'wazuh-agent1': 'ipv4'
    },
    {
        'name': 'manager_ipv4_agent_ipv6',
        'wazuh-manager': 'ipv4',
        'wazuh-agent1': 'ipv6'
    },
    {
        'name': 'manager_ipv6_agent_ipv6',
        'wazuh-manager': 'ipv6',
        'wazuh-agent1': 'ipv6'
    },
    {
        'name': 'manager_dns',
        'wazuh-manager': 'dns',
        'wazuh-agent1': 'ipv4'
    }
]

network = {}


# Remove the agent once the test has finished
@pytest.fixture(scope='module')
def clean_environment():
    yield
    agent_id = host_manager.run_command('wazuh-manager', f'cut -c 1-3 {WAZUH_PATH}/etc/client.keys')
    host_manager.get_host('wazuh-manager').ansible("command", f'{WAZUH_PATH}/bin/manage_agents -r {agent_id}',
                                                  check=False)
    host_manager.control_service(host='wazuh-agent1', service='wazuh', state="stopped")
    host_manager.clear_file(host='wazuh-agent1', file_path=os.path.join(WAZUH_PATH, 'etc', 'client.keys'))


@pytest.mark.parametrize('test_case', [cases for cases in network_configuration], ids = [cases['name'] for cases in network_configuration])
def test_agent_enrollment(test_case, get_ip_directions, modify_ip_address_conf, clean_environment):
    """Check agent enrollment process works as expected. An agent pointing to a worker should be able to register itself
    into the manager by starting Wazuh-agent process."""
    # Clean ossec.log and cluster.log
    host_manager.clear_file(host='wazuh-manager', file_path=os.path.join(WAZUH_LOGS_PATH, 'ossec.log'))
    host_manager.clear_file(host='wazuh-agent1', file_path=os.path.join(WAZUH_LOGS_PATH, 'ossec.log'))

    ## Start the agent enrollment process by restarting the wazuh-agent
    host_manager.control_service(host='wazuh-manager', service='wazuh', state="restarted")
    host_manager.get_host('wazuh-agent1').ansible('command', f'service wazuh-agent restart', check=False)

    # Run the callback checks for the ossec.log
    HostMonitor(inventory_path=inventory_path,
                messages_path=messages_path,
                tmp_path=tmp_path).run()

    # Make sure the agent's client.keys is not empty
    assert host_manager.get_file_content('wazuh-agent1', os.path.join(WAZUH_PATH, 'etc', 'client.keys'))

    # Check if the agent is active
    agent_id = host_manager.run_command('wazuh-manager', f'cut -c 1-3 {WAZUH_PATH}/etc/client.keys')
    assert host_manager.run_command('wazuh-manager', f'{WAZUH_PATH}/bin/agent_control -i {agent_id} | grep Active')

# IPV6 fixtures
@pytest.fixture(scope='module')
def get_ip_directions():
    global network
    host_manager.get_host('wazuh-manager')
    manager_network = host_manager.get_host_ip('wazuh-manager')
    agent_network = host_manager.get_host_ip('wazuh-agent1')

    network['manager_network'] = manager_network
    network['agent_network'] = agent_network


@pytest.fixture(scope='function')
def configure_network(get_ip_direcctions, network_configuration):
    for key,value in network_configuration.items():
        if value == 'ipv6':
            host_manager.run_command(key, f'ip -4 addr flush dev eth0')

    yield

    for key,value in network_configuration.items():
        if value == 'ipv6':
            host_manager.run_command(key, f"ip addr add {get_ip_direcctions[key][1]['addr_info'][0]['local']} dev eth0")


@pytest.fixture(scope='function')
def modify_ip_address_conf(test_case):
    print(f'CASE: {test_case}')


    with open(agent_conf_file, 'r') as file:
	    old_configuration = file.read()
        #print(f'OLD: {old_configuration}')
    if 'ipv4' in test_case['wazuh-manager']:
        print('HOLI')
        new_configuration = old_configuration.replace('<address>MANAGER_IP</address>',f"<address>{network['manager_network'][0]}</address>")
        host_manager.modify_file_content(host='wazuh-agent1', path='/var/ossec/etc/ossec.conf', content=new_configuration)
        #print(f'NEW: {new_configuration}')
    elif 'ipv6' in test_case['wazuh-manager']:
        print('CHAO')
        new_configuration = old_configuration.replace('<address>MANAGER_IP</address>',f"<address>{network['manager_network'][1]}</address>")
        host_manager.modify_file_content(host='wazuh-agent1', path='/var/ossec/etc/ossec.conf', content=new_configuration)
    else:
        new_configuration = old_configuration.replace('<address>MANAGER_IP</address>',f"<address>wazuh-manager</address>")
        host_manager.modify_file_content(host='wazuh-agent1', path='/var/ossec/etc/ossec.conf', content=new_configuration)
