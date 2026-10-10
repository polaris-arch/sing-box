#!/usr/bin/env python3
"""Select only allowlisted native jobs for a reviewed candidate dispatch."""
import json
import os

TARGETS = [
    {'os': 'linux', 'arch': 'amd64', 'tool_arch': 'x64', 'runner': 'ubuntu-24.04'},
    {'os': 'linux', 'arch': 'arm64', 'tool_arch': 'arm64', 'runner': 'ubuntu-24.04-arm'},
    {'os': 'windows', 'arch': 'amd64', 'tool_arch': 'x64', 'runner': 'windows-2025'},
    {'os': 'windows', 'arch': 'arm64', 'tool_arch': 'arm64', 'runner': 'windows-11-arm'},
    {'os': 'darwin', 'arch': 'amd64', 'tool_arch': 'x64', 'runner': 'macos-15-intel'},
    {'os': 'darwin', 'arch': 'arm64', 'tool_arch': 'arm64', 'runner': 'macos-15'},
]


def select_targets(platform):
    selected = TARGETS if platform == 'all' else [
        target for target in TARGETS if platform == target['os'] + '/' + target['arch']]
    if not selected:
        raise ValueError('unknown candidate platform: ' + repr(platform))
    return selected


if __name__ == '__main__':
    value = json.dumps(select_targets(os.environ['CANDIDATE_PLATFORM']), separators=(',', ':'))
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('matrix=' + value + '\n')
