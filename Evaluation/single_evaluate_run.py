# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys
import argparse
import pandas as pd
import utils
import time
from tqdm import tqdm
import tempfile
import config
import subprocess
import logging
import re


def set_max_memory():
    import resource
    # 限制最大内存为10GB
    limit = 10 * 1024 * 1024 * 1024  # 10GB in bytes
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

global TIMEOUT
TIMEOUT = 120

def setup_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='gpt4o', help='model to evaluate')
    parser.add_argument('--output_dir', type=str, default='/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/CoreCodeBench', help='Output directory for results')
    parser.add_argument('--regenerate', action='store_true')
    parser.add_argument('--type', type=str, nargs='+', default=['Development', "TDD", "BugFix"], help='Specify types, choose one or more from  ["Development", "TDD", "BugFix"]')
    parser.add_argument('--repo_name', type=str, default='langchain', help='Repository name')
    return parser
          

def evaluate_gen_code(id, pytest_info, repo_name, origin_file, test_path_list, tmp_repo_path, response_line, log_dir, score_dir, model):
    repo_args = utils.get_repo_args(repo_name)
    tmp_running_path = repo_args['repo_running_path'].replace(repo_args['repo_path'], tmp_repo_path)

    # preprocess
    source_code_path = os.path.join(repo_args['repo_running_path'], origin_file)
    source_code_bak = utils.get_file_content(source_code_path)
    source_code_lines = source_code_bak.splitlines()
    prefix = source_code_lines[:prob_info['func_start_lineno']-1]
    suffix = source_code_lines[prob_info['func_end_lineno']:]
    
    # generate completed code file
    completed_code_string = '\n'.join(prefix + response_line['response'].splitlines() + suffix)

    # test code file substitute
    test_code_path = os.path.join(tmp_running_path, origin_file)
    with open(test_code_path, 'w') as f:
        f.write(completed_code_string)

    passed_list, skipped_list, failed_list = [], [], []
    log_file = os.path.join(log_dir, f'''{response_line['ID']}.log''')
    for test_path in test_path_list:
        test_file_path = os.path.join(tmp_repo_path, test_path)    
        cmd = ['timeout', str(TIMEOUT), 'pytest', test_file_path, '--tb=long']
        env = os.environ.copy()
        env['PYTHONPATH'] = tmp_running_path
        with open(log_file, 'w') as f:
            try:
                subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=TIMEOUT, preexec_fn=set_max_memory)
            except subprocess.TimeoutExpired:
                f.write(f"Timeout: {TIMEOUT}s\n")
            except Exception as e:
                f.write(f"Error: {e}\n")
        passed, skipped, failed = utils.read_log(log_file)
        passed_list.append(passed) 
        skipped_list.append(skipped)
        failed_list.append(failed)
    
    passed = sum(passed_list)
    skipped = sum(skipped_list)
    failed = sum(failed_list)
    pass_rate = max(0, (passed-pytest_info['base_passed_num'])/(pytest_info['total_num']-pytest_info['base_passed_num']))
    pass_all = int(passed == pytest_info['total_num'])
    
    res = {
        'ID': response_line['ID'],
        'repo_name': repo_name,
        'model': model,
        'passed': passed,
        'skipped': skipped,
        'failed': failed,
        'pass_all': pass_all,
        'pass_rate': pass_rate,
        'base_passed_num': pytest_info['base_passed_num'],
        'total_num': pytest_info['total_num']
    }
    
    logging.info(res)
    
    # 如果CSV文件不存在,创建并写入表头
    if not os.path.exists(score_dir):
        print('Write to score_dir')
        df = pd.DataFrame([res])
        df.to_csv(score_dir, index=False)
    else:
        # 如果已存在,追加写入
        print('Append to score_dir')
        df = pd.DataFrame([res])
        df.to_csv(score_dir, mode='a', header=False, index=False)

    # restore file
    shutil.copy(os.path.join(repo_args['repo_running_path'], origin_file), test_code_path)
    

        
if __name__ == "__main__":
    parser = setup_arg_parser()
    args = parser.parse_args()
    if type(args.type) == list:
        args.type = ' '.join(args.type)

    if args.model.startswith("void"):
        TIMEOUT = 0.1
    else:
        TIMEOUT = 120

    repo_args = utils.get_repo_args(args.repo_name)
    args.testcase_file = config.single_testcases_path
    repo_path = repo_args["repo_path"]
    if not os.path.exists(args.testcase_file):
        logging.error(f"{args.testcasefile} does not exist")
        sys.exit(1)

    # load testcases of target repo
    testcases = utils.load_jsonl_to_list(args.testcase_file, ['project', args.repo_name])    
    
    results_dir = os.path.join(args.output_dir, 'results', args.model)
    response_dir = os.path.join(results_dir, 'single_response.jsonl')
    if not os.path.exists(response_dir):
        logging.error(f"Response does not exist in {response_dir}!!!")
        sys.exit(1)
    
    # load response results of the repo
    result_dict = {'Development':{}, 'TDD':{}, 'BugFix':{}}
    with open(response_dir, 'r') as f:
        for line in f.readlines():
            line = json.loads(line)
            match = re.match(r'^(Development|TDD|BugFix)-(.+)$', line["ID"])
            if match:
                typ = match.group(1)
                id = match.group(2)
            else:
                logging.error(f"Invalid line ID: {line['ID']}")
                sys.exit(1)
            if typ in args.type and line['repo_name'] == args.repo_name:
                result_dict[typ][id] = line
                
    score_dir = os.path.join(results_dir, 'single_scores.csv')
    log_dir = os.path.join(results_dir, 'logs', 'single')
    os.makedirs(log_dir, exist_ok=True)
    if args.regenerate and os.path.exists(score_dir):
        os.remove(score_dir)
        
    if not os.path.exists(score_dir):
        generated_testcases = set()
    else:
        # 从CSV文件中读取已生成的测试用例
        df = pd.read_csv(score_dir)
        generated_testcases = set(df['ID'])

    # copy temp test file
    temp_dir = os.path.join(config.root_path, 'tmp_source')
    os.makedirs(temp_dir, exist_ok=True)
    temp_copy_path = tempfile.mkdtemp(prefix=f'SINGLE_EVAL_{args.repo_name}_', dir=temp_dir)
    shutil.copytree(repo_args['repo_path'], temp_copy_path, dirs_exist_ok=True)
    if not temp_copy_path.endswith(os.sep):
        temp_copy_path += os.sep
    
    try:
        for testcase in tqdm(testcases):
            if testcase['type'] not in args.type:
                continue
            try:
                response_line = result_dict[testcase['type']][testcase['id']]
            except:
                logging.error(f'REPO : {args.repo_name}, TYPE: {testcase["type"]}, ID: {testcase["id"]} does not have a response result!!!')
                sys.exit(1)
            
            id, typ, origin_file, test_path_list, prob_info = testcase['id'], testcase['type'], testcase['origin_file'], testcase['test_list'],testcase['prob_info']
            pytest_info = testcase['pytest_info']
            if f'{typ}-{id}' in generated_testcases:
                continue
            evaluate_gen_code(id, pytest_info, args.repo_name, origin_file, test_path_list, temp_copy_path, response_line, log_dir, score_dir, args.model)
        logging.info(f"Evaluation for {args.repo_name}-{args.type} is finished!")
    
    finally:
        if temp_copy_path:
            try:
                shutil.rmtree(temp_copy_path)   
            except Exception as e:
                logging.error(f"Error occurred while removing temporary directory: {e}")
