import subprocess
import re
import ast
import textwrap  # 用于移除额外的缩进
import json
import os
import argparse
# from variable_tracker import extract_lvalues_and_rvalues, extract_lvalues_new
from CorePipe.utils import read_log
import CorePipe.config as config
from tqdm import tqdm
import pandas as pd
import argparse
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo_name', type=str, default='', help='name of repo')
    args = parser.parse_args()
    repo_name = args.repo_name

    mapping_path = os.path.join(config.workspace, args.repo_name, "testcase_mapping.jsonl")
    valid_mapping_path = os.path.join(config.workspace, args.repo_name, "output_testcase_mapping_valid.jsonl")
    invalid_mapping_path = os.path.join(config.workspace, args.repo_name, "output_testcase_mapping_invalid.jsonl")
    repo_info_path = config.repo_info_path

    with open(repo_info_path, 'r') as file:
        repo_info = json.load(file)

    if repo_name in repo_info:
        repo_data = repo_info[repo_name]
        repo_path = os.path.join(config.repo_path, args.repo_name)
        running_path_relative = repo_data.get('_running_path', '').lstrip('/')
        repo_running_path = os.path.join(repo_path, running_path_relative)
    else:
        logging.warning("Repository '%s' not found in the JSON file.", repo_name)

    results_df = pd.DataFrame(columns=['test_id', 'passed', 'skipped', 'failed'])

    with open(mapping_path, 'r', encoding='utf-8') as file:
        for line_num, line in enumerate(tqdm(file, desc="Processing lines")):
            data = json.loads(line.strip())
            test_file = data.get("test_file", "")
            origin_file = data.get("origin_file", "")
            test_path = test_file
            file_name = origin_file.split('/')[-1].replace('.py', '')

            logging.info("Test Path: %s", test_path)
            logging.info("Origin File: %s", origin_file)
            logging.info("File Name: %s", file_name)
            logging.info("-" * 40)
            
            result_dir = os.path.join(config.workspace, args.repo_name, 'logs', 'test_all_test')
            if not os.path.exists(result_dir):
                os.makedirs(result_dir)
            
            # 执行命令
            os.chdir(repo_path)
            BASH = f'''PYTHONPATH={repo_running_path} timeout 120 pytest {test_path} --tb=long > {result_dir}/{file_name}_origin_test_result.log'''
            logging.info(BASH)
            exit_code = os.system(BASH)

            # 检查命令的退出状态
            if exit_code == 0:
                passed, skipped, failed = read_log(os.path.join(result_dir, f'''{file_name}_origin_test_result.log'''))
            else:
                logging.info(exit_code)
                logging.warning("Test %s exceeded time limit and was terminated.", test_path)
                passed, skipped, failed = 0, 0, 1  # 设置 failed 为 1

            results_df = results_df._append({'test_id': [test_file], 'passed': [passed], 'skipped': [skipped], 'failed': [failed]}, ignore_index=True)
            
            if failed == 0 and (passed > 0.5*(passed + skipped + failed)):
                valid_data = {
                    "test_file": test_file,
                    "origin_file": origin_file,
                    "pytest": {
                        "passed": passed,
                        "skipped": skipped
                    }
                }
                
                with open(valid_mapping_path, 'a') as valid_file:
                    valid_file.write(json.dumps(valid_data) + "\n")
                logging.info("%s is valid", test_file)
            else:
                with open(invalid_mapping_path, 'a') as invalid_file:
                    invalid_file.write(f"{test_file} failed{failed} passed{passed} skipped{skipped}\n")
                logging.info("%s failed:%d passed:%d skipped:%d", test_file, failed, passed, skipped)
