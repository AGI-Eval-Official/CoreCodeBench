import subprocess
import re
import ast
import textwrap 
import json
import os
import argparse
import utils
import pandas as pd
import argparse
import traceback
from tqdm import tqdm
import tempfile
import shutil
from config import testcase_path, root_path, multi_testcases_path, single_testcases_path, func_empty_testcases_path
import logging
import subprocess

logger = logging.getLogger(__name__)

TIMEOUT = 120

parser = argparse.ArgumentParser()
parser.add_argument('--type', type=str, nargs='+', default=['Development', "TDD", "BugFix"], help='Specify types, e.g., Development, TDD, BugFixx')
parser.add_argument('--model', type=str, default='gpt4o', help='args.model')
parser.add_argument('--output_dir', type=str, default=root_path, help='Output directory for results')
parser.add_argument('--repo_name', type=str, default='langchain', help='Repository name')

args = parser.parse_args()

if type(args.type) == list:
    args.type = ' '.join(args.type)

if args.model.startswith("void"):
    TIMEOUT = 0.1
else:
    TIMEOUT = 120


repo_args = utils.get_repo_args(args.repo_name)
temp_dir = os.path.join(root_path, 'tmp_source')
os.makedirs(temp_dir, exist_ok=True)
temp_copy_path = tempfile.mkdtemp(prefix=f'MULTI_EVAL_{args.repo_name}', dir=temp_dir)
shutil.copytree(repo_args['repo_path'], temp_copy_path, dirs_exist_ok=True)
if not temp_copy_path.endswith(os.sep):
    temp_copy_path += os.sep

logger.info("copy_finished, temp_copy_path: ", temp_copy_path)

print(f"temp_copy_path: {temp_copy_path}")

def set_max_memory():
    import resource
    # 限制最大内存为10GB
    limit = 10 * 1024 * 1024 * 1024  # 10GB in bytes
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

def remove_common_prefix(str1, str2):
    if len(str1) == 0 or len(str2) == 0:
        return str1
    if str1.startswith(str2):
        if str1[len(str2)] == '\n':
            return str1[len(str2)+1:]
        else:
            return str1[len(str2):]
    else:
        return str1

def remove_common_indent(text):
    """
    移除所有行与第一行相同长度的前导空格
    示例：
    输入：
        Line1
            Line2
          Line3
    输出：
    Line1
        Line2
      Line3
    """
    lines = text.splitlines(keepends=False)
    if not lines:
        return text
    
    first_line = lines[0]
    indent_len = len(first_line) - len(first_line.lstrip(' '))
    processed = []
    for line in lines:
        remove_count = min(indent_len, len(line) - len(line.lstrip(' ')))
        processed.append(line[remove_count:])
    
    return '\n'.join(processed)


def get_testcases(id, repo_name, problem_type):
    testcases = {}
    with open (single_testcases_path, "r") as testcase_file:
        for line in testcase_file:
            data = json.loads(line)
            if data['id'] == id and data['type'] == problem_type and data['project'] == repo_name:
                data['code'] = {
                    'func_start_lineno': data['prob_info']['func_start_lineno'],
                    'func_end_lineno': data['prob_info']['func_end_lineno'],
                    'key_block_start_lineno': data['prob_info']['key_block_start_lineno'],
                    'key_block_end_lineno': data['prob_info']['key_block_end_lineno'],
                    'new_func_code': data['prob_info']['new_func_code'],
                }
                testcases[data['func']] = (data['id'], data['code'])
                return testcases

    with open (func_empty_testcases_path, "r") as testcase_file:
        for line in testcase_file:
            data = json.loads(line)
            if data['id'] == id and data['project'] == repo_name:
                data['code'] = {
                    'func_start_lineno': data['prob_info']['func_start_lineno'],
                    'func_end_lineno': data['prob_info']['func_end_lineno'],
                    'key_block_start_lineno': data['prob_info']['key_block_start_lineno'],
                    'key_block_end_lineno': data['prob_info']['key_block_end_lineno'],
                    'new_func_code': data['prob_info']['new_func_code'],
                }
                testcases[data['func']] = (data['id'], data['code'])
                return testcases
    return testcases

def load_jsonl(file_path, repo_name):
    generated = set()
    if not os.path.exists(file_path):
        return generated
    with open(file_path, 'r') as file:
        for line in file:
            data = json.loads(line)
            if data['project'] == repo_name:
                generated.add(data['ID'])
    return generated

def load_response(file_path, repo_name, testcase_id, problem_type):
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r') as file:
        for line in file:
            data = json.loads(line)
            if data['repo_name'] == repo_name and data["ID"] == f"{problem_type}-" + "-".join(testcase_id):
                return data["response"]
    return {}

def test_func(problem_type, repo_name, testcase, tmp_repo_path):
    repo_args = utils.get_repo_args(repo_name)
    repo_path, repo_running_path, find_path = repo_args["repo_path"], repo_args["repo_running_path"], repo_args["find_path"]
    running_path = repo_running_path.replace(repo_path, tmp_repo_path)
    
    id = testcase["id"]
    origin_file = testcase["origin_file"]
    prob_info = testcase["prob_info"]
    node = testcase["node"]
    pytest_info = testcase["pytest_info"]
    result_dir = os.path.join(args.output_dir, 'results', args.model)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        
    score_file = os.path.join(result_dir, 'multi_scores.csv')
    if not os.path.exists(score_file):
        generated = set()
    else:
        df = pd.read_csv(score_file)
        generated = set(df['ID'])
        
    ID = problem_type + '-' + "-".join(id)
    if ID in generated:
        return
    
    completed_key_block_dict = load_response(os.path.join(result_dir, f'multi_response.jsonl'), repo_name, id, problem_type)    
    flag = True
        
    for index, name in enumerate(node):
        path = origin_file[index]
        path = os.path.join(repo_running_path, path)
        file_name = path.split('/')[-1].replace('.py', '')
        src_transformers_index = path.find(find_path)
        file_path = path[src_transformers_index + len(find_path):path.rfind('/')]
        
        if name.split(".")[-2] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-1]+".py"
        elif name.split(".")[-3] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-2] + "::" + name.split(".")[-1] + ".py"
        problem_id = os.path.join(repo_name, file_path, file_name, func_file).replace(".py", "").replace("/", ".")
        if problem_id not in set(id):
            continue
        if name not in completed_key_block_dict:
            flag = False
            break


        source_code_path = os.path.join(repo_path, file_path, f'{file_name}.py')
        with open(source_code_path, 'r') as f:
            source_code = f.read().splitlines()
        testcases = get_testcases(problem_id, repo_name, problem_type)
        func_name = func_file.replace(".py", "")
        save_dir = source_code_path.replace(repo_running_path, running_path)

        for func, item in testcases.items():
            if func != func_name:
                continue
            test_id, single_testcase = item
            with open(save_dir, 'r') as save_file:
                save_code = save_file.read()
            prefix = source_code[:single_testcase['key_block_start_lineno'] -1]
            suffix = source_code[single_testcase['key_block_end_lineno']:]
            completed_key_block = completed_key_block_dict[name]
            completed_code = remove_common_prefix(remove_common_indent(completed_key_block),remove_common_indent('\n'.join(str(x) for x in source_code[single_testcase['func_start_lineno']-1:single_testcase['key_block_start_lineno']-1])))
            indented_completed_key_block = utils.align_indent(completed_code.splitlines(), source_code[single_testcase['key_block_start_lineno']-1:single_testcase['key_block_end_lineno']], prefix, suffix )
            compeletd_code = prefix + indented_completed_key_block + suffix
            replaced_code = '\n'.join(source_code[single_testcase['key_block_start_lineno']-1:single_testcase['key_block_end_lineno']])
            new_save_code = save_code.replace(replaced_code, '\n'.join(indented_completed_key_block))
            with open(save_dir, "w") as save_file:
                save_file.write(new_save_code)
            
    # Test, Done
    os.chdir(running_path)
    passed_cnt, skipped_cnt, failed_cnt = 0, 0, 0
    if flag:
        test_path_list = testcase["test_list"]
        for idx, test_path in enumerate(test_path_list):
            tmp_test_path = os.path.join(tmp_repo_path, test_path)
            test_file = test_path.split("/")[-1].replace(".py", "")
            result_log_dir = os.path.join(result_dir, "logs", "multi")
            if not os.path.exists(result_log_dir):
                os.makedirs(result_log_dir)
            test_file_path = test_path.replace("/", "-")
            log_name = problem_type + "-" + ID.replace(".", "_")[:200]+'_'+str(idx)
            log_dir = os.path.join(result_log_dir, f"{log_name}.log")
            cmd = ['pytest', tmp_test_path, '--tb=long']
            env = os.environ.copy()
            env['PYTHONPATH'] = running_path
            with open(log_dir, 'w') as f:
                try:
                    subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, preexec_fn=set_max_memory, timeout=TIMEOUT)
                except subprocess.TimeoutExpired:
                    f.write(f"Timeout: {TIMEOUT}s\n")
                except Exception as e:
                    f.write(f"Error: {e}\n")
            if os.path.exists(log_dir):
                passed, skipped, failed = utils.read_log(log_dir)
                # print(passed, skipped, failed)
            else:
                passed, skipped, failed = 0, 0, 0
            
            passed_cnt += passed
            skipped_cnt += skipped
            failed_cnt += failed
            
        result_dict = {
            "ID": ID,
            "repo_name": repo_name,
            "model": args.model,
            "passed": passed_cnt,
            "skipped": skipped_cnt,
            "failed": failed_cnt,
            "pass_all": int(passed_cnt == pytest_info['total_num']),
            "pass_rate": max(0, (passed_cnt-pytest_info['base_passed_num'])/(pytest_info['total_num']-pytest_info['base_passed_num'])),
            "base_passed_num": pytest_info['base_passed_num'],
            "total_num": pytest_info['total_num']
        }

    else:
        result_dict = {
            "ID": ID,
            "repo_name": repo_name,
            "model": args.model,
            "passed": 0,
            "skipped": 0,
            "failed": 0,
            "pass_all": 0,
            "pass_rate": 0,
            "base_passed_num": pytest_info['base_passed_num'],
            "total_num": pytest_info['total_num']
        }
    
        
    # 复原
    for index, name in enumerate(node):
        path = origin_file[index]
        path = os.path.join(repo_running_path, path)
        file_name = path.split('/')[-1].replace('.py', '')
        src_transformers_index = path.find(find_path)
        file_path = path[src_transformers_index + len(find_path):path.rfind('/')]
        if name.split(".")[-2] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-1]+".py"
        elif name.split(".")[-3] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-2] + "::" + name.split(".")[-1] + ".py"
        problem_id = os.path.join(repo_name, file_path, file_name, func_file).replace(".py", "").replace("/", ".")
        if problem_id not in set(id):
            continue
        source_code_path = os.path.join(repo_path, file_path, f'{file_name}.py')
        shutil.copy(source_code_path, source_code_path.replace(repo_running_path, running_path)) 
    # shutil.copytree(repo_path, tmp_repo_path, dirs_exist_ok=True)
    
    score_file = os.path.join(result_dir, 'multi_scores.csv')
    if not os.path.exists(score_file):
        df = pd.DataFrame([result_dict])
        df.to_csv(score_file, index=False)
    else:
        df = pd.DataFrame([result_dict])
        df.to_csv(score_file, mode='a', header=False, index=False)

with open(multi_testcases_path, 'r', encoding='utf-8') as file:
    for line in file:
        testcase = json.loads(line)
        repo_name = testcase["project"]
        problem_type = testcase["type"] 
        if repo_name != args.repo_name or problem_type not in args.type:
            continue 

        result_df = test_func(problem_type, repo_name, testcase, temp_copy_path)
        
shutil.rmtree(temp_copy_path)