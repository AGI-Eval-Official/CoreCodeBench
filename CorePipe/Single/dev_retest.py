import subprocess
import re
import ast
import textwrap 
import json
import os
import argparse
import CorePipe.utils as utils
import shutil
import argparse
import traceback
from tqdm import tqdm
import CorePipe.config as config
import tempfile

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo_name', type=str, default='', help='Repository name') # transformers, langchain
    root_path = config.root_path
    
    args = parser.parse_args()
    repo_name = args.repo_name
    args.output_dir = os.path.join(config.workspace, args.repo_name)
    args.repo_args = utils.get_repo_args(args.repo_name)
    args.repo_path = args.repo_args["repo_path"]

    args.mapping_path = os.path.join(config.workspace, args.repo_name, "output_testcase_mapping_valid.jsonl")
    
    return args



def retest_code(args, testcase, file_path, file_name, test_path, log_file):
    test_id, func_start_lineno, func_end_lineno = testcase['id'], testcase['prob_info']['func_start_lineno'], testcase['prob_info']['func_end_lineno']
    new_func_code = testcase['prob_info']['new_func_code']
    repo_args = args.repo_args
    repo_path = args.repo_path
    temp_repo_path = args.tmp_repo_path
    
    source_code_path = os.path.join(repo_args['repo_running_path'], file_path, f'{file_name}.py')
    tmp_source_code_path = source_code_path.replace(repo_path, temp_repo_path)
    tmp_running_path = repo_args['repo_running_path'].replace(repo_path, temp_repo_path)
    
    with open(source_code_path, 'r') as f:
        source_code = f.read().splitlines()

    
    
    prefix = '\n'.join(source_code[:func_start_lineno-1])
    suffix = '\n'.join(source_code[func_end_lineno:])
    new_func_code = '\n'.join([line for line in new_func_code.splitlines() if not line.strip().startswith('#')])
    new_func_code = new_func_code.replace('<complete code here>', '')
    new_code = prefix + '\n' + new_func_code + '\n' + suffix
    with open(tmp_source_code_path, 'w') as f:
        f.write(new_code)
    os.chdir(tmp_running_path)

    BASH = f'''PYTHONPATH={tmp_running_path} timeout 120 pytest {test_path} --tb=long > {log_file}'''    
    status = os.system(BASH)
    failed = 0
    passed = 0
    if status == 0:
        passed, skipped, failed = utils.read_log(log_file)
    if (status != 0 and status != 1024) or failed != 0:
        return True, passed
    else:
        return False, passed
    
    shutil.copy(tmp_source_code_path, source_code_path)


if __name__ == "__main__":
    args = parse_args()
    # copy temp test file
    temp_dir = os.path.join(config.root_path, 'tmp_source')
    os.makedirs(temp_dir, exist_ok=True)
    temp_copy_path = tempfile.mkdtemp(prefix=f'GEN_RETEST_{args.repo_name}_', dir=temp_dir)
    shutil.copytree(args.repo_path, temp_copy_path, dirs_exist_ok=True)
    if not temp_copy_path.endswith(os.sep):
        temp_copy_path += os.sep
    args.tmp_repo_path = temp_copy_path
    output_file = os.path.join(config.testcases_path, args.repo_name,'single','Development.jsonl')
    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))
    if os.path.exists(output_file):
        os.remove(output_file)
    with open(args.mapping_path, 'r', encoding='utf-8') as file:
        with open(output_file, 'a', encoding='utf-8') as output:
            for line_num, line in tqdm(enumerate(file), desc="Processing lines", unit="line"):
                data = json.loads(line.strip())
                test_file = data.get("test_file", "")
                origin_file = data.get("origin_file", "")
                pytest_info = data.get("pytest", "")
                file_name = origin_file.split('/')[-1].replace('.py', '')
                file_path = os.path.dirname(origin_file)
                
                test_case_dir = os.path.join(args.output_dir, 'testcases', file_path, file_name)
                testcases_info_path = os.path.join(test_case_dir, 'testcases_info.jsonl')
                repo_log_dir = os.path.join(test_case_dir, 'retest_log')
                if not os.path.exists(repo_log_dir):
                    os.makedirs(repo_log_dir)
                testcases_info = []
                test_path = os.path.join(args.tmp_repo_path, test_file)
                with open(testcases_info_path, 'r', encoding='utf-8') as f:
                    for line in f.readlines():
                        testcases_info.append(json.loads(line.strip()))
                for testcase in testcases_info:
                    id = testcase['id']
                    log_file = os.path.join(repo_log_dir, f'{id}_retest.log')
                    retest_res, passed = retest_code(args, testcase, file_path, file_name, test_path, log_file)
                    if retest_res:
                        testcase['pytest_info']['base_passed_num'] = passed
                        output.write(json.dumps(testcase, ensure_ascii=False) + '\n')
               
    shutil.rmtree(temp_copy_path)

