# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys
import argparse
import pandas as pd
import time
from tqdm import tqdm
import re
import subprocess

def setup_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root_path',type=str, help='Root path')
    parser.add_argument('--repo_name', type=str, default='langchain', help='Repository name')
    return parser


def get_repo_path(repo_name):
    repo_info_path = os.path.join(args.root_path, 'repo_info.json')
    tested_testfile = {}
    with open(repo_info_path, 'r') as file:
        repo_info = json.load(file)
    repo_data = repo_info[repo_name]
    repo_path = os.path.join(args.root_path, repo_data.get('repo_path', ''))
    running_path_relative = repo_data.get('_running_path', '').lstrip('/')
    repo_running_path = os.path.join(repo_path, running_path_relative)
    return repo_path, repo_running_path

def load_jsonl_to_list(file, key_value=None):
    res = []
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                if key_value is None:
                    res.append(json.loads(line.strip()))
                else:
                    line_json = json.loads(line.strip())
                    if line_json[key_value[0]] == key_value[1]:
                        res.append(json.loads(line.strip()))
            except Exception as e:
                print('Error loading JSON to list: ', line)
                print('File:', file)
                print(e)
                sys.exit()
    return res

def read_log(log):
    passed_pattern = r'(\d+) passed'
    xpassed_pattern = r'(\d+) xpassed'
    skipped_pattern = r'(\d+) skipped'
    failed_pattern = r'(\d+) failed'
    xfailed_pattern = r'(\d+) xfailed'
    warning_pattern = r'(\d+) warnings?'
    
    # 搜索匹配
    passed_match = re.search(passed_pattern, log)
    xpassed_match = re.search(xpassed_pattern, log)
    skipped_match = re.search(skipped_pattern, log)
    failed_match = re.search(failed_pattern, log)
    xfailed_match = re.search(xfailed_pattern, log)
    warn_match = re.search(warning_pattern, log)
    
    # 提取匹配结果
    passed = int(passed_match.group(1)) if passed_match else 0
    xpassed = int(xpassed_match.group(1)) if xpassed_match else 0
    skipped = int(skipped_match.group(1)) if skipped_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    xfailed = int(xfailed_match.group(1)) if xfailed_match else 0
    warn = int(warn_match.group(1)) if warn_match else 0
    
    return passed, skipped, failed


if __name__ == "__main__":
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    args.testcase_file = os.path.join(args.root_path, "CoreCodeBench/CoreCodeBench_Single.jsonl")
    repo_path, repo_running_path = get_repo_path(args.repo_name)
    testcases = load_jsonl_to_list(args.testcase_file, ['project', args.repo_name])  
    if args.repo_name == 'langchain':
        apped_testcases =  load_jsonl_to_list(args.testcase_file, ['project', 'langchain_core'])
        testcases += apped_testcases
    for testcase in tqdm(testcases):
        test_file_list = testcase['test_list']
        total_num = 0
        for test_file in test_file_list:
            path = os.path.join(repo_path, test_file)
            os.environ['PYTHONPATH'] = repo_running_path
            result = subprocess.run(['pytest', path, '--tb=long'], capture_output=True, text=True)  # pytest --snapshot-update
            output = result.stdout
            print(output)
            passed, skipped, failed = read_log(output)
            try:
                assert failed == 0
            except Exception as e:
                print('Failed in file: {}'.format(path))
                sys.exit(1)
            total_num += passed

        pytest_info =  testcase['pytest_info']['total_num']
        try:
            assert total_num == pytest_info
        except Exception as e:
            print('Wrong in file {}, Total_num: {}, Pytest_info: {}'.format(testcase['id'], total_num, pytest_info))
            sys.exit(1)
    print('Check environment of repo {} passed!'.format(args.repo_name))