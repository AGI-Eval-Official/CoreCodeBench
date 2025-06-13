import subprocess
import re
import ast
import textwrap  # 用于移除额外的缩进
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

# TODO: 删去了repo_name需要判断project，删去了if_comments需要读取type字段判断，删去mode

parser = argparse.ArgumentParser()
parser.add_argument('--type', type=str, nargs='+', default=['Development', "TDD", "BugFix"], help='Specify types, e.g., Development, TDD, BugFixx')
parser.add_argument('--model', type=str, default='gpt4o', help='args.model')
parser.add_argument('--output_dir', type=str, default=root_path, help='Output directory for results')
parser.add_argument('--repo_name', type=str, default='langchain', help='Repository name') # transformers, langchain

args = parser.parse_args()

# FIXME: 临时文件路径问题
repo_args = utils.get_repo_info(args.repo_name)
temp_dir = os.path.join(root_path, 'tmp_source')
os.makedirs(temp_dir, exist_ok=True)
temp_copy_path = tempfile.mkdtemp(prefix=f'SINGLE_EVAL_{args.repo_name}', dir=temp_dir)
shutil.copytree(repo_args['repo_path'], temp_copy_path, dirs_exist_ok=True)
if not temp_copy_path.endswith(os.sep):
    temp_copy_path += os.sep

def remove_common_prefix(str1, str2):
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
    
    # 计算第一行的前导空格数
    first_line = lines[0]
    indent_len = len(first_line) - len(first_line.lstrip(' '))
    processed = []
    for line in lines:
        # 计算实际可移除的空格数（取最小值，避免超出当前行长度）
        remove_count = min(indent_len, len(line) - len(line.lstrip(' ')))
        processed.append(line[remove_count:])
    
    return '\n'.join(processed)


def get_testcases(id, repo_name, problem_type):
    testcases = {}
    # TODO:, highlight fixed
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
            if json.loads(line)['project'] == repo_name:
                generated.add(json.loads(line)['id']+json.loads(line)['type'])
    return generated

def load_response(file_path, repo_name, testcase_id, problem_type):
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r') as file:
        for line in file:
            data = json.loads(line)
            if data['project'] == repo_name and data["id"] = testcase_id and data["type"] == problem_type:
                return data[response]
    return {}

# FIXME: tmp_repo_path和repo_path需要统一
def test_func(problem_type, repo_name, testcase, tmp_repo_path):
    # FIXME: test_path_list, remove copy_path, output_dir
    repo_args = utils.get_repo_args(repo_name)
    repo_path, repo_running_path, find_path = repo_args["repo_path"], repo_args["repo_running_path"], repo_args["find_path"]
    running_path = repo_running_path.replace(repo_path, tmp_repo_path)
    
    id = testcase["id"]
    origin_file = testcase["origin_file"]
    prob_info = testcase["prob_info"]
    node = testcase["node"]
    pytest_info = testcase["pytest_info"]
    
    generated = load_jsonl(os.path.join(result_dir, f'multi_scores.jsonl'), repo_name)
    testcase_id = "-".join(["+".join(single_id.split(".")[-2:]) for single_id in id])
    if testcase_id+problem_type in generated:
        return 
    
    result_dir = os.path.join(args.output_dir, 'results', args.model)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        
    completed_key_block_dict = load_response(os.path.join(result_dir, f'multi_response.jsonl'), repo_name, testcase_id, problem_type)
    
        
    for index, name in enumerate(node):
        if name not in completed_key_block_dict:
            continue
        path = origin_file[index]
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
        with open(source_code_path, 'r') as f:
            source_code = f.read().splitlines()
        testcases = get_testcases(problem_id, repo_name, problem_type)
        func_name = func_file.replace(".py", "")
        # save_dir = os.path.join(result_dir,f'''{file_path.replace("/", "-")}-{file_name}_completed_{args.model}.py''')
        save_dir = source_code_path.replace(repo_running_path, running_path)
        for func, item in testcases.items():
            if func != func_name:
                continue
            test_id, testcase = item
            with open(save_dir, 'r') as save_file:
                save_code = save_file.read()
            prefix = source_code[:testcase['key_block_start_lineno'] -1]
            suffix = source_code[testcase['key_block_end_lineno']:]
            completed_key_block = completed_key_block_dict[name]
            completed_code = remove_common_prefix(remove_common_indent(completed_key_block),remove_common_indent('\n'.join(str(x) for x in source_code[testcase['func_start_lineno']-1:testcase['key_block_start_lineno']-1])))
            indented_completed_key_block = utils.align_indent(completed_code.splitlines(), source_code[testcase['key_block_start_lineno']-1:testcase['key_block_end_lineno']], prefix, suffix )
            compeletd_code = prefix + indented_completed_key_block + suffix
            replaced_code = '\n'.join(source_code[testcase['key_block_start_lineno']-1:testcase['key_block_end_lineno']])
            new_save_code = save_code.replace(replaced_code, '\n'.join(indented_completed_key_block))
            with open(save_dir, "w") as save_file
                save_file.write(new_save_code)
            
    # Test, Done
    os.chdir(running_path)
    result_dict = {"id": testcase_id, "type": problem_type, "project": repo_name, "passed": 0, "skipped": 0, "failed": 0, "pass_rate": 0, "pass_all": 0}
    for idx, test_path in enumerate(test_path_list):
        # tmp_test_path = test_path.replace(copy_path, tmp_repo_path)
        tmp_test_path = os.path.join(tmp_repo_path, test_path)
        test_file = test_path.split("/")[-1].replace(".py", "")
        #TODO: result_dir, here, find_path and repo_path，breakpoint
        result_log_dir = os.path.join(result_dir, "logs", "multi")
        if not os.path.exists(result_log_dir):
            os.makedirs(result_log_dir)
        log_dir = os.path.join(result_log_dir, f"{problem_type}_{testcase_id}_{test_path.replace("/", "-")}.log")
        BASH = f'''PYTHONPATH={running_path} timeout 600 pytest {tmp_test_path} --tb=long > {log_dir} 2>&1'''
        os.system(BASH)
        if os.path.exists(log_dir):
            passed, skipped, failed = read_log(log_dir)
        else:
            passed, skipped, failed = 0, 0, 0
        # passall = (passed == pytest_info['total_num'])
        result_dict["passed"] += passed
        result_dict["skipped"] += skipped
        result_dict["failed"] += failed
    result_dict["pass_rate"] = max(0, (result_dict["passed"]-pytest_info['base_passed_num'])/(pytest_info['total_num']-pytest_info['base_passed_num']))
    result_dict["pass_all"] = int(result_dict["passed"][0] == pytest_info['total_num'])
    
        
    #TODO: 复原
    for index, name in enumerate(node):
        path = origin_file[index]
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
        # shutil.copy(source_code_path, source_code_path.replace(source_code_path, source_code_path.replace(repo_running_path, running_path))) # 复原文件
        shutil.copy(source_code_path, source_code_path.replace(repo_running_path, running_path)) # 复原文件
    with open(os.path.join(result_dir,f'multi_scores.jsonl'),'a') as f:
        json_line = json.dumps(result_dict, ensure_ascii=False)
        f.write(json_line + "\n")

with open(func_testcases_info_path, 'r', encoding='utf-8') as file:
    for line in file:
        testcase = json.loads(line)
        repo_name = testcase["project"]
        if repo_name != args.repo_name:
            continue
        problem_type = testcase["type"]  

        result_df = test_func(problem_type, repo_name, testcase, temp_copy_path)
        

    print("-" * 40)
shutil.rmtree(temp_copy_path)
  