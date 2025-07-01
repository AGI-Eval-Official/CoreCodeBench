import subprocess
import re
import ast
import textwrap  # 用于移除额外的缩进
import json
import os
import argparse
import sys
import utils
import pandas as pd
import argparse

import traceback
from tqdm import tqdm
from config import testcase_path, root_path, multi_testcases_path, single_testcases_path, func_empty_testcases_path

parser = argparse.ArgumentParser()
parser.add_argument('--model', type=str, default='gpt4o', help='args.model')
parser.add_argument('--output_dir', type=str, default='/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/CoreCodeBench/', help='Output directory for results')
parser.add_argument('--type', type=str, nargs='+', default=['Development', "TDD", "BugFix"], help='Specify types, e.g., Development, TDD, BugFixx')

args = parser.parse_args()

if type(args.type) is list:
    args.type = ' '.join(args.type)

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

def extract_code_blocks(text):
    pattern = r'<id>(.*?)</id>\s*```python(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if not matches:
        pattern2 = r'<id>(.*?)</id>\s*```(.*?)```'
        matches = re.findall(pattern2, text, re.DOTALL)
    code_dict = {match[0].strip(): match[1].lstrip('\n') for match in matches if match[0].strip() and "\n" not in match[0].strip()}
    return code_dict

def complete_code(idq_list, not_idq_list, model, problem_type, test_path_list, repo_path):
    code_seg = ""
    if not_idq_list:
        code_seg += """<related code>
"""
    for not_idq in not_idq_list:
        temp = '\n'.join(not_idq_list[not_idq])
        code_seg += f"""
<id>{not_idq}</id>
```python 
{temp}
```
"""
    code_seg += "\n\n<complete following code>"
    
    for idq in idq_list:
        temp = '\n'.join(idq_list[idq])
        code_seg += f"""
<id>{idq}</id>
```python 
{temp}
```
"""
    if problem_type == "Development":
        chat_message = f'''
If you were a code completion agent, I would provide you with a snippet of code, and you would need to return the completed code segment. 
the code after <ralated code> is used while calling the code to be completed. 
You need to completechat_message code blocks after <complete following code> by predicting the codes after <complete code here>, <id> label wraps the position of the code.
Your output should include the <id></id> label, followed by the completed code snippet enclosed within triple backticks ```, ensuring clarity and proper formatting.
{code_seg}
'''
    elif problem_type == "BugFix":
        chat_message = f'''
In the following code snippet, the code between <buggy code begin> and <buggy code end> contains bugs, <id> label wraps the position of the code. Please analyze the provided context and rewrite the faulty code segment.
the code after <ralated code> is used while calling the code to be rewrited. 
Your output should include the <id></id> label, followed by the new code snippet enclosed within triple backticks ```, ensuring clarity and proper formatting.
{code_seg}
'''
    elif problem_type == "TDD":
        test_codes = ""
        for test_file in test_path_list:
            test_file = os.path.join(repo_path, test_file)
            with open(test_file, "r") as test_file:
                test_code = test_file.read()
                test_codes += test_code
        chat_message = f'''
If you were a code completion agent, I would provide you with a snippet of code, and you would need to return the completed code segment. 
the code after <ralated code> is used while calling the code to be completed. 
You need to complete code blocks after <complete following code> by predicting the codes after <complete code here>, <id> label wraps the position of the code.
Please analyze the provided file context and the unit test information of the file, and generate an appropriate code block at the position marked <complete code here>.
Your output should include the <id></id> label, followed by the completed code snippet enclosed within triple backticks ```, ensuring clarity and proper formatting.
Note: Please ensure that the code block you provide as a completion matches the indentation of the surrounding context, i.e., you need to preserve the original code's indentation.
{code_seg}


The unit test information:

{test_codes}
'''
    # print(chat_message)
    res = utils.get_response(chat_message, model=model)
    return extract_code_blocks(res), res, chat_message

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
            if json.loads(line)['repo_name'] == repo_name:
                generated.add(json.loads(line)['ID'])
    return generated

# def generate_id_code(problem_type, result_dir, id, origin_file, prob_info, node):
def test_func(problem_type, repo_name, testcase):
    id = testcase["id"]
    origin_file = testcase["origin_file"]
    prob_info = testcase["prob_info"]
    node = testcase["node"]

    result_dir = os.path.join(args.output_dir, 'results', args.model)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
    generated = load_jsonl(os.path.join(result_dir, f'multi_response.jsonl'), repo_name)
    
    ID = problem_type + '-' + '-'.join(id)
    if ID in generated:
        return 
    repo_args = utils.get_repo_args(repo_name)
    find_path = repo_args["find_path"]
    repo_path = repo_args["repo_path"]
    repo_running_path = repo_args["repo_running_path"]
    
    
    idq_list = {}
    not_idq_list = {}
    source_code_path_list = []
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
        source_code_path = os.path.join(repo_path, file_path, f'{file_name}.py')
        source_code_path_list.append(source_code_path)
        with open(source_code_path, 'r') as f:
            source_code = f.read().splitlines()  
        if problem_id in set(id):
            # TODO: better, need change in evaluate
            testcases = get_testcases(problem_id, repo_name, problem_type)
            func_name = func_file.replace(".py", "")
            for func, item in testcases.items():
                if func != func_name:
                    continue
                test_id, single_testcase = item
                idq_list[name] = single_testcase['new_func_code'].splitlines()
        else:
            func_start_lineno, func_end_lineno = prob_info[index]["func_start_lineno"], prob_info[index]["func_end_lineno"]
            code = source_code[func_start_lineno:func_end_lineno]
            not_idq_list[name] = code
    completed_key_block_dict, response, chat_message = complete_code(idq_list, not_idq_list, args.model, problem_type, testcase["test_list"], repo_path)
    # save_dict = {"id": "-".join(["+".join(single_id.split(".")[-2:]) for single_id in id]), "project": repo_name, "raw_response": response, "type": problem_type, "response": completed_key_block_dict}
    save_dict = {
        'ID': ID,
        'repo_name': repo_name,
        'prompt': chat_message,
        'response': completed_key_block_dict,
        'key_block_start_lineno': [prob_info[index]["func_start_lineno"] for index in range(len(prob_info))],
        'key_block_end_lineno': [prob_info[index]["func_end_lineno"] for index in range(len(prob_info))],
        'origin_file': origin_file,
        "source_file": source_code_path_list,
    }
    # save_dict["response"] = completed_key_block_dict
    # save_dict["raw_response"] = response
    # save_dict["chat_message"] = chat_message
    with open(os.path.join(result_dir,f'multi_response.jsonl'),'a') as f:
        json_line = json.dumps(save_dict, ensure_ascii=False)
        f.write(json_line + "\n")

with open(multi_testcases_path, 'r', encoding='utf-8') as file:
    for line in file:
        testcase = json.loads(line)
        if testcase["type"] not in args.type:
            continue
        repo_name = testcase["project"]
        problem_type = testcase["type"]

        test_func(problem_type, repo_name, testcase)  
        # print(repo_name, problem_type, testcase["id"], "done")