# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2
import os
import re
import yaml
import csv
import numpy as np
import pandas as pd
from datetime import datetime
from itertools import groupby
from mmap import ACCESS_READ, mmap


class LogAnalyzer:
    """This class group several statics methods to gather specific information from Wazuh logs."""
    error_codes = ['warning', 'error', 'critical']

    @staticmethod
    def get_log_timestamp(line):
        """Get the timestamp of the line.

        Args:
            component (str): Log line.
        """
        timestamp_match = re.match(r"^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}).*", line)
        return datetime.strptime(timestamp_match.group(1), '%Y/%m/%d %H:%M:%S') if timestamp_match else None

    @staticmethod
    def findall_regex_line(lines, regex, flags=None):
        """Get all the lines that match a certain regex.

        Args:
            lines (list): List of lines.
            regex (str): Regex to match.
            flags (str): Flags to use in the findall regex method.
        """
        if flags:
            error_lines = re.findall(bytes(regex, encoding='utf8'), lines, flags=flags)
        else:
            error_lines = re.findall(bytes(regex, encoding='utf8'), lines)

        error_lines = [error.decode(encoding='utf8') for error in error_lines] if error_lines else []
        return error_lines

    @staticmethod
    def get_error_log_file(log_path, type='error'):
        """Get all the lines of the specified type of the log file.

        Args:
            log_path (list): Log path
            type (str): Type of log to search.
        """
        error_lines = []
        if os.path.getsize(log_path) != 0:
            with open(log_path) as f:
                log_file_content = mmap(f.fileno(), 0, access=ACCESS_READ)

                error_lines = LogAnalyzer.findall_regex_line(lines=log_file_content, regex=f"(^.*?{type}\:.*?$)",
                                                             flags=re.MULTILINE | re.IGNORECASE)
        return error_lines

    @staticmethod
    def get_error_logs_hosts(log_dict):
        """Get all the error/warning/critical logs of the logs dictionary.

        Args:
            log_dict (dict): Dictionary with the name of the host and the log path.
        """
        error_dict = {'critical': [], 'error': [], 'warning': []}
        for type in LogAnalyzer.error_codes:
            for host_log in log_dict:
                error_list_host = []
                for host_name, log_path in host_log['logs'].items():
                    if os.path.exists(log_path):
                        host_error = LogAnalyzer.get_error_log_file(log_path, type)
                        if host_error:
                            error_list_host += \
                                              [f"[{host_name}] " + host_error_line for host_error_line in host_error]
                if error_list_host:
                    error_dict[type] += [{host_log['name']:  error_list_host}]
        return error_dict

    @staticmethod
    def keep_alive_log_parser(log_files):
        """Get keep-alive information of the manager log.

        Args:
            log_files (list): List of manager logs to gather agent connection information.
        """
        keep_alive_regex = '(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) wazuh\-remoted.* reading ' + \
            "'(.*)\|(.*)\|(.*)\|(.*)\|(.* \[.*\].*)\n(.*)\n.*:(\d+\.\d+\.\d+\.\d+)"

        keep_alives = {}
        for log_file in log_files:
            regex = re.compile(rf"{keep_alive_regex}", re.MULTILINE)

            with open(log_file['logs']['ossec.log']) as log:
                for match in regex.finditer(log.read()):
                    if match.group(3) not in keep_alives:
                        keep_alives[match.group(3)] = {"n_keep_alive": 1, "max_difference": 0, "mean_difference": 0,
                                                       "last_keep_alive": match.group(1),
                                                       "first_keep_alive": match.group(1)}
                    else:
                        keep_alives[match.group(3)]["n_keep_alive"] += 1

                        last_keep_alive_datetime = datetime.strptime(keep_alives[match.group(3)]["last_keep_alive"],
                                                                     '%Y/%m/%d %H:%M:%S')
                        recent_keep_alive_datetime = datetime.strptime(match.group(1), '%Y/%m/%d %H:%M:%S')

                        if keep_alives[match.group(3)]["max_difference"] < \
                                abs(recent_keep_alive_datetime - last_keep_alive_datetime).seconds:
                            keep_alives[match.group(3)]["max_difference"] = \
                                abs(recent_keep_alive_datetime - last_keep_alive_datetime).seconds

                        keep_alives[match.group(3)]["mean_difference"] += \
                            abs(recent_keep_alive_datetime - last_keep_alive_datetime).seconds

                        keep_alives[match.group(3)]["last_keep_alive"] = match.group(1)

                last_timestamp = None
                log.seek(0)
                log_lines = log.readlines()
                for line in reversed(log_lines):
                    last_log_line = line
                    timestamp = LogAnalyzer.get_log_timestamp(last_log_line)
                    if timestamp:
                        last_timestamp = timestamp
                        break

            for agent in keep_alives.keys():
                # Calculate means
                keep_alives[agent]["mean_difference"] = \
                    keep_alives[agent]["mean_difference"]/keep_alives[agent]["n_keep_alive"]

                # Calculate last keep alive
                last_keep_alive = datetime.strptime(keep_alives[agent]['last_keep_alive'], '%Y/%m/%d %H:%M:%S')
                keep_alives[agent] = \
                    {**keep_alives[agent], **{'remainder': abs(last_timestamp - last_keep_alive).seconds}}

        keep_alives_report = {'keep_alives': keep_alives}
        return keep_alives_report


class StatisticsAnalyzer:
    """This class group several statics methods to gather specific information from Wazuh statistics."""
    @staticmethod
    def calculate_values(statistis_files, fields):
        """Calculate statistical values of the specified files.

        Args:
            statistis_files (list): List of statistics csv files.
            fields (list): List of fields to calculate certain statistical values.
        """
        n_stats = len(statistis_files)
        mean_fields = {}

        for field in fields:
            mean_fields['mean_' + field] = 0
            mean_fields['max_mean_' + field] = None
            mean_fields['min_mean_' + field] = None

            mean_fields['min_' + field] = None
            mean_fields['max_' + field] = None

            mean_fields['mean_reg_cof_' + field] = 0
            mean_fields['max_reg_cof_' + field] = None
            mean_fields['min_reg_cof_' + field] = None

        dataframe = pd.DataFrame()

        for statistic in statistis_files:
            for field in fields:
                dataframe = pd.read_csv(statistic['path'])

                mean = dataframe[field].mean()
                max = dataframe[field].max()
                min = dataframe[field].min()

                mean_fields['max_' + field] = int(max) if not mean_fields['max_' + field] or \
                    max > mean_fields['max_' + field] else int(mean_fields['max_' + field])

                mean_fields['min_' + field] = int(min) if not mean_fields['min_' + field] or \
                    min < mean_fields['min_' + field] else int(mean_fields['min_' + field])

                mean_fields['max_mean_' + field] = int(mean) if not mean_fields['max_mean_' + field] or \
                    mean > mean_fields['max_mean_' + field] else int(mean_fields['max_mean_' + field])

                mean_fields['min_mean_' + field] = int(mean) if not mean_fields['min_mean_' + field] or \
                    mean < mean_fields['min_mean_' + field] else \
                    int(mean_fields['min_mean_' + field])

                mean_fields['mean_' + field] += int(mean)

                reg_cof = int(np.polyfit(range(len(dataframe)), list(dataframe[field]), 1)[0])

                mean_fields['mean_reg_cof_' + field] += reg_cof
                mean_fields['max_reg_cof_' + field] = int(reg_cof) if not mean_fields['max_reg_cof_' + field] or \
                    reg_cof > mean_fields['max_reg_cof_' + field] else int(mean_fields['max_reg_cof_' + field])
                mean_fields['min_reg_cof_' + field] = int(reg_cof) if not mean_fields['min_reg_cof_' + field] or \
                    reg_cof < mean_fields['min_reg_cof_' + field] else int(mean_fields['min_reg_cof_' + field])

        for field in fields:
            mean_fields['mean_' + field] = mean_fields['mean_' + field] / n_stats
            mean_fields['mean_reg_cof_' + field] = mean_fields['mean_reg_cof_' + field] / n_stats

        return mean_fields

    def analyze_agentd_statistics(agentd_statistics_files):
        """Create a report for wazuh-agentd daemon.

        Args:
            agentd_statistics_files (dict): Agentd statistics files.
        """
        # Status
        n_stats = len(agentd_statistics_files)
        agentd_report = {
            "begin_status": {"connected": 0, "pending": 0, "disconnected": 0},
            "end_status": {"connected": 0, "pending": 0, "disconnected": 0},
            "ever_disconnected": 0,
            "ever_connected": 0,
            "ever_pending": 0,

            "mean_status_change_count": 0,
            "max_status_change_count": 0,

            "max_diff_ack_keep_alive": 0,
            "mean_diff_ack_keep_alive": 0
        }

        status_dataframe = pd.DataFrame()
        for agentd_stat in agentd_statistics_files:
            agent_dataframe = pd.read_csv(agentd_stat['path'])
            status_dataframe = agent_dataframe['status']

            begin_status_value = status_dataframe.iloc[0]
            end_status_value = status_dataframe.iloc[len(status_dataframe.index) - 1]
            agentd_report["begin_status"][begin_status_value] += 1
            agentd_report["end_status"][end_status_value] += 1

            agent_status_count = status_dataframe.value_counts().to_dict()
            if 'pending' in agent_status_count:
                agentd_report["ever_pending"] += 1

            if 'connected' in agent_status_count:
                agentd_report["ever_connected"] += 1

            if 'disconnected' in agent_status_count:
                agentd_report["ever_disconnected"] += 1

            status_change_count = len([x[0] for x in groupby(agent_status_count)]) - 1
            agentd_report['mean_status_change_count'] += status_change_count

            if status_change_count > agentd_report['max_status_change_count']:
                agentd_report['max_status_change_count'] = status_change_count

            # ACK - KEEP ALIVE
            diff = (abs(pd.to_datetime(agent_dataframe['last_keepalive']) -
                    pd.to_datetime(agent_dataframe['last_ack']))).astype('timedelta64[s]')

            agentd_report["mean_diff_ack_keep_alive"] += diff.mean()
            max = diff.max()

            if max > agentd_report["max_diff_ack_keep_alive"]:
                agentd_report["max_diff_ack_keep_alive"] = max
        agentd_report['mean_status_change_count'] /= n_stats

        agentd_report = {**agentd_report, **(StatisticsAnalyzer.calculate_values(agentd_statistics_files,
                         ['msg_sent', 'msg_count', 'msg_buffer']))}

        return agentd_report

    def analyze_remoted_statistics(remoted_statistics_files):
        """Create a report for wazuh-remoted daemon.

        Args:
            agentd_statistics_files (dict): Remoted statistics files.
        """
        remoted_report = StatisticsAnalyzer.calculate_values(remoted_statistics_files,
                                                             ['queue_size', 'total_queue_size', 'tcp_sessions',
                                                              'evt_count', 'ctrl_msg_count', 'discarded_count',
                                                              'queued_msgs', 'sent_bytes', 'recv_bytes',
                                                              'dequeued_after_close'])
        return remoted_report


class ReportGenerator:
    """This class generates a Python object to generate a JSON report, that synthesizes the state of the environment.

    This class will use an artifact folder with a specified format in order to gather data from logs, statistics and,
    metrics. All this data will be used for the generation of an environment report during the uptime.

    Args:
        target (str): Artifact path.
        configuration (str): Configuration file path.

    Attributes:
        artifact_path (str): Root artifact path.
        configuration_path (str): Root configuration path.
        agents_path (str): Agents artifact path.
        managers_path (str): Managers artifact path.
        master_path (str): Master artifact path.
        worker_path (str): Worker artifact path.
        n_workers (str): Number of workers nodes.
        n_agents (str): Number of agents.
        cluster_environment (boolean): Cluster or single node environment.
    """
    def __init__(self, artifact_path, configuration_path=None):

        if os.path.isdir(artifact_path):
            self.artifact_path = artifact_path

            agents_path = os.path.join(artifact_path, 'agents')
            managers_path = os.path.join(artifact_path, 'managers')

            master_path = os.path.join(artifact_path, 'managers', 'master')
            worker_path = os.path.join(artifact_path, 'managers', 'worker')

            if not (os.path.isdir(agents_path) or os.path.isdir(managers_path) or os.path.isdir(master_path)):
                print("ERROR: The artifact file structure should follow this scheme")
                print("""
                ├── agents
                │   └── agent1
                │       ├── data
                │       │   ├── binaries
                │       │   └── stats
                │       └── logs
                └── managers
                    ├── master
                    │   └── master-instance
                    │       ├── data
                    │       │   ├── binaries
                    │       │   └── stats
                    │       └── logs
                    └── workers
                        └── worker1
                            ├── data
                            │   ├── binaries
                            │   └── stats
                            └── logs
                """)
                raise ValueError

        self.component_path = {
            'agents': agents_path,
            'managers': managers_path,
            'master': master_path,
            'workers': worker_path
        }

        if os.path.isdir(worker_path):
            self.n_workers = len(os.listdir(worker_path))
            self.cluster_environment = True
        else:
            self.n_workers = 0
            self.cluster_environment = False

        self.n_agents = len(os.listdir(agents_path))

        if configuration_path:
            if os.path.isfile(configuration_path):
                self.configuration_path = configuration_path
                with open(configuration_path, 'r') as configuration_file:
                    configurations = yaml.full_load(configuration_file)
                    for phase in configurations:
                        if phase['phase']['timeframe'] != 'all':
                            start = datetime.strptime(phase['phase']['timeframe']['start'], '%Y/%m/%d %H:%M:%S')
                            end = datetime.strptime(phase['phase']['timeframe']['end'], '%Y/%m/%d %H:%M:%S')
                            for component_path in self.get_instances_artifacts(component=phase['phase']['hosts']):
                                phase_dir = os.path.join(component_path['path'], f"phase-{phase['phase']['timeframe']['start'].replace('/','.')}-{phase['phase']['timeframe']['end'].replace('/','.')}")
                                if not os.path.exists(phase_dir):
                                    os.makedirs(os.path.join(phase_dir, 'logs'))
                                    os.makedirs(os.path.join(phase_dir, 'data', 'stats'))
                                    os.makedirs(os.path.join(phase_dir, 'data', 'binaries'))
                                ## LOGS
                                for component_logs in self.get_instances_logs(log="all", component=phase['phase']['hosts'], hosts_regex=f"{component_path['name']}"):
                                    for log_files, path in component_logs['logs'].items():
                                        if os.path.isfile(path):
                                            with open(path) as f:
                                                log_file_content = f.readlines()
                                                phase_content = []
                                                for line in log_file_content:
                                                    timestamp = LogAnalyzer.get_log_timestamp(line)
                                                    if timestamp:
                                                        if start <= timestamp <= end:
                                                            phase_content += line
                                            with open(os.path.join(phase_dir, 'logs', log_files), 'w') as file:
                                                file.writelines(phase_content)
                                ## STATISTICS
                                statistics_path = os.path.join(component_path['path'], 'data', 'stats')
                                for component_statistics in os.listdir(statistics_path):
                                    dataframe = pd.DataFrame()
                                    dataframe = pd.read_csv(os.path.join(statistics_path, component_statistics))
                                    timestamp = dataframe['Timestamp']
                                    phase_dataframe = dataframe[pd.to_datetime(dataframe["Timestamp"]) > start]
                                    phase_dataframe.to_csv(os.path.join(phase_dir, 'data', 'stats', component_statistics))
                                ## BINARIES
                                binaries_path = os.path.join(component_path['path'], 'data', 'binaries')
                                for component_binaries in os.listdir(binaries_path):
                                    dataframe = pd.DataFrame()
                                    dataframe = pd.read_csv(os.path.join(binaries_path, component_binaries))
                                    timestamp = dataframe['Timestamp']
                                    phase_dataframe = dataframe[pd.to_datetime(dataframe["Timestamp"]) > start]
                                    phase_dataframe.to_csv(os.path.join(phase_dir, 'data', 'binaries', component_binaries))

                        else:
                            for component_path in self.get_instances_artifacts(component=phase['phase']['hosts']):
                                phase_dir = os.path.join(component_path['path'], f"phase-{phase['phase']['timeframe']}")
                                if not os.path.exists(phase_dir):
                                    os.makedirs(os.path.join(phase_dir, 'logs'))
                                    os.makedirs(os.path.join(phase_dir, 'data', 'stats'))
                                    os.makedirs(os.path.join(phase_dir, 'data', 'binaries'))
                                ## LOGS
                                for component_logs in self.get_instances_logs(log="all", component=phase['phase']['hosts'], hosts_regex=f"{component_path['name']}"):
                                    for log_files, path in component_logs['logs'].items():
                                        if os.path.isfile(path):
                                            with open(path) as f:
                                                log_file_content = f.readlines()
                                            with open(os.path.join(phase_dir, 'logs', log_files), 'w') as file:
                                                file.writelines(log_file_content)
                                ## STATISTICS
                                statistics_path = os.path.join(component_path['path'], 'data', 'stats')
                                for component_statistics in os.listdir(statistics_path):
                                    dataframe = pd.DataFrame()
                                    dataframe = pd.read_csv(os.path.join(statistics_path, component_statistics))
                                    dataframe.to_csv(os.path.join(phase_dir, 'data', 'stats', component_statistics))
                                ## BINARIES
                                binaries_path = os.path.join(component_path['path'], 'data', 'binaries')
                                for component_binaries in os.listdir(binaries_path):
                                    dataframe = pd.DataFrame()
                                    dataframe = pd.read_csv(os.path.join(binaries_path, component_binaries))
                                    dataframe.to_csv(os.path.join(phase_dir, 'data', 'binaries', component_binaries))
        else:
            self.configuration_path = None

    def get_instances_artifacts(self, component, hosts_regex=".*"):
        """Get the artifact path for specified hosts_regex

        Args:
            component (str): Wazuh installation type (agents/managers/all).
            hosts_regex (str): Regex to filter by hostname.
        """
        artifacts_files = []
        if component == 'all':
            artifacts_files += self.get_instances_artifacts('managers', hosts_regex)
            artifacts_files += self.get_instances_artifacts('agents', hosts_regex)
        elif component == 'managers':
            artifacts_files += self.get_instances_artifacts('master', hosts_regex)
            if self.cluster_environment:
                artifacts_files += self.get_instances_artifacts('workers', hosts_regex)
        else:
            artifact_path = self.component_path[component]
            artifacts_files = [{"name": filename, "path": os.path.join(artifact_path, filename)}
                               for filename in os.listdir(artifact_path) if re.match(rf'{hosts_regex}', filename)]
        return artifacts_files

    def get_instance_all_log_files(self, hostname):
        """Get all the log's paths files of the specified host.

        Args:
            hostname (str): Hostname to get all the logs files.
        """
        files = os.path.join(self.get_instances_artifacts('all', hostname)[0]['path'], 'logs')
        host_log_list = [log for log in os.listdir(files)]
        return host_log_list

    def get_instances_logs(self, log, component, hosts_regex=".*"):
        """Get the logs path for specified hosts_regex

        Args:
            log (str): Host log file.
            component (str): Wazuh installation type (agents/managers/all).
            hosts_regex (str): Regex to filter by hostname.
        """
        artifacts_paths = self.get_instances_artifacts(component, hosts_regex)
        for host_artifact_path in artifacts_paths:
            host_artifact_path['logs'] = {}
            log_files = self.get_instance_all_log_files(host_artifact_path['name']) if log == 'all' else [log]

            for log_file in log_files:
                general_path = os.path.join(host_artifact_path['path'], 'logs')
                host_artifact_path['logs'][log_file] = os.path.join(general_path, log_file)
            del host_artifact_path['path']

        return artifacts_paths

    def get_instances_process_metrics(self, process, component, hosts_regex='.*'):
        """Get the metrics statistics path for specified hosts_regex

        Args:
            process (str): Process name.
            component (str): Wazuh installation type (agents/managers/all).
            hosts_regex (str): Regex to filter by hostname.
        """
        files = self.get_instances_artifacts(component, hosts_regex)
        for file in files:
            file.update((host, os.path.join(artifact_path, 'data', 'binaries', process + '.csv'))
                        for host, artifact_path in file.items())
        return files

    def get_instances_statistics(self, statistic, component, hosts_regex='.*'):
        """Get the daemons statistics path for specified hosts_regex

        Args:
            statistic (str): Statistic name.
            component (str): Wazuh installation type (agents/managers/all).
            hosts_regex (str): Regex to filter by hostname.
        """
        files = self.get_instances_artifacts(component, hosts_regex)
        for file in files:
            file['path'] = os.path.join(file['path'], 'data', 'stats', statistic + '_stats.csv')
        return files

    def agentd_report(self, component='agents', hosts_regex='.*'):
        """Generate wazuh-agentd daemon report, combining metric and statistics.

        Args:
            component (str): Wazuh installation type (agents/managers/all).
            hosts_regex (str): Regex to filter by hostname.
        """
        agentd_report = StatisticsAnalyzer.analyze_agentd_statistics(self.get_instances_statistics('wazuh-agentd',
                                                                                                   component,
                                                                                                   hosts_regex))
        return agentd_report

    def remoted_report(self, component='managers', hosts_regex='.*'):
        """Generate wazuh-remoted daemon report, combining metric and statistics.

        Args:
            component (str): Wazuh installation type (agents/managers/all).
            hosts_regex (str): Regex to filter by hostname.
        """
        remoted_report = StatisticsAnalyzer.analyze_remoted_statistics(self.get_instances_statistics('wazuh-remoted',
                                                                                                     component,
                                                                                                     hosts_regex))
        remoted_report = {**remoted_report, **LogAnalyzer.keep_alive_log_parser(self.get_instances_logs(log='ossec.log',
                                                                                component=component,
                                                                                hosts_regex=hosts_regex))}

        return remoted_report

    def make_report(self):
        """Build the JSON report of the environment."""
        report = {}

        report['metadata'] = {'n_agents': self.n_agents, 'n_workers': self.n_workers}

        report['agents'] = LogAnalyzer.get_error_logs_hosts(log_dict=self.get_instances_logs(log='all',
                                                                                             component='agents'))
        report['managers'] = LogAnalyzer.get_error_logs_hosts(log_dict=self.get_instances_logs(log='all',
                                                                                               component='managers'))

        report['agents']['wazuh-agentd'] = self.agentd_report()
        report['managers']['wazuh-remoted'] = self.remoted_report()

        return report
