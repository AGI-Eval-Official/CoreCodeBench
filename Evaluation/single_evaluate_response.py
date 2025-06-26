# -*- coding: utf-8 -*-
import json
import os
import sys
import shutil
import argparse
import pandas as pd
import utils
import time
from tqdm import tqdm
import config


def setup_args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='gpt4o', help='model to evaluate')
    parser.add_argument('--model_ip', type=str, default="None", help='args.model_ip')
    parser.add_argument('--output_dir', type=str, default='/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/CoreCodeBench', help='Output directory for results')
    parser.add_argument('--regenerate', action='store_true', help='regenerate/reevaluate everything')
    parser.add_argument('--type', type=str, nargs='+', default=['Development', "TDD", "BugFix"], help='Specify types, choose one or more from  ["Development", "TDD", "BugFix"]')
    return parser
     
def get_token_length(text):
    return len(text) / 4.18

def complete_code_dev(new_code):
    chat_message = f'''下面是一段包含占位符 `<complete code here>` 的代码片段。请分析提供的上下文和缺失代码的描述，在 `<complete code here>`处生成适当的代码块。
请使用markdown格式(```python```)输出你补全的代码块。
**注意**：请确保你补全的代码块符合上下文代码的缩进，也就是说，需要保留原来代码的缩进。
代码片段:
```python
{new_code}
```
请使用markdown格式(```python```)输出你补全的代码块。需要保留<complete code here>前后原来代码的缩进。
'''
    return chat_message

def complete_code_TDD(new_code, test_file, file_name):
    chat_message = f'''Below is a code file {file_name} containing a placeholder `<complete code here>`.Please analyze the provided file context and unit test information, and generate appropriate code at the `<complete code here>` location. Please output your completed code block in markdown format (```python```). The code block should only include the code at the `<completed code here>` location, without the surrounding context.
**Note**: Please ensure that your completed code block maintains the indentation of the surrounding code, meaning you need to preserve the original code's indentation.

Code file {file_name} to be completed:
```python
{new_code}
```
Corresponding unit test:
```python
{test_file}
```
'''
    return chat_message

def complete_code_bugfix_with_log(new_code, log, test_code):
    chat_message = f'''In the following code snippet, there is a buggy code section between `<buggy code begin>` and `<buggy code end>`. I've provided the corresponding unit test file and pytest error messages. Please analyze the given context and rewrite the erroneous code segment.
Please format the rewritten function block in markdown (```python```), including only the rewritten content between `<buggy code begin>` and `<buggy code end>`, without including the `<buggy code begin>` and `<buggy code end>` tags.
**Note**: Please ensure that your completed code block maintains the indentation of the original code context.

Code snippet:
```python
{new_code}
```
Unit test code:
```python
{test_code}
```
Test error log：
```
{log}
```
'''
    return chat_message
    
def complete_code_bugfix(new_code):
    chat_message = f'''
In the following code snippet, there is a buggy code section between `<buggy code begin>` and `<buggy code end>`.  Please analyze the given context and rewrite the erroneous code segment.
Please format the rewritten function block in markdown (```python```), including only the rewritten content between `<buggy code begin>` and `<buggy code end>`, without including the `<buggy code begin>` and `<buggy code end>` tags.
**Note**: Please ensure that your completed code block maintains the indentation of the original code context.
Code snippet:
```python
{new_code}
```
'''
    return chat_message

def complet_code_bugfix_short(new_code):
    print('Complete code bugfix short')
    start = new_code.find('<buggy code begin>')
    end = new_code.find('<buggy code end>') + len('<buggy code end>')
    
    lines = new_code.splitlines()
    class_start = -1
    class_end = -1
    for i, line in enumerate(lines):
        if 'class ' in line and class_start == -1:
            # 找到类的开头和结尾
            indent = len(line) - len(line.lstrip())
            class_start = i
            for j in range(i + 1, len(lines)):
                if j == len(lines) - 1 or (len(lines[j].strip()) > 0 and len(lines[j]) - len(lines[j].lstrip()) <= indent):
                    class_end = j
                    break
            
            # 检查这个类是否包含buggy code
            class_content = '\n'.join(lines[class_start:class_end])
            if '<buggy code begin>' not in class_content:
                class_start = -1
                class_end = -1
                continue
            else:
                break

    if class_start != -1:
        # 如果buggy code在类中，返回整个类
        short_code = '\n'.join(lines[class_start:class_end])  
    else:
        # 否则只返回buggy code部分
        short_code = new_code[start:end]
        
    chat_message=f'''
In the following code snippet, there is a buggy code section between `<buggy code begin>` and `<buggy code end>`. I've provided the corresponding unit test file and pytest error messages. Please analyze the given context and rewrite the erroneous code segment.
Please format the rewritten function block in markdown (```python```), including only the rewritten content between `<buggy code begin>` and `<buggy code end>`, without including the `<buggy code begin>` and `<buggy code end>` tags.
**Note**: Please ensure that your completed code block maintains the indentation of the original code context.
Code snippet:
```python
{short_code}
```
Unit test code:
```python
{test_code}
```
Test error log：
```
{log}
```
''' 
    if get_token_length(chat_message) > 56000:
       chat_message=f'''
In the following code snippet, there is a buggy code section between `<buggy code begin>` and `<buggy code end>`.  Please analyze the given context and rewrite the erroneous code segment.
Please format the rewritten function block in markdown (```python```), including only the rewritten content between `<buggy code begin>` and `<buggy code end>`, without including the `<buggy code begin>` and `<buggy code end>` tags.
**Note**: Please ensure that your completed code block maintains the indentation of the original code context.
Code snippet:
```python
{short_code}
```
'''  
    return chat_message

def complete_code(new_code, id, origin_file, model, model_ip, test_path_list, repo_args, mode, return_prompt=False):
    prompt = None
    if mode == "Development":
        prompt = complete_code_dev(new_code)
        res = utils.get_response(prompt, model, model_ip)
    elif mode == "TDD":
        prompt = complete_code_TDD(new_code, utils.test_path_to_str(test_path_list, repo_args['repo_path']), origin_file)
        res = utils.get_response(prompt, model, model_ip)
    elif mode == "BugFix":
        log_path = os.path.join(config.testcase_path, 'DEBUG_logs', 'retest_{}.log'.format(id))
        log_file = utils.read_file(log_path)
        
        test_file_path = [ os.path.join(repo_args['repo_path'], test_path) for test_path in test_path_list]
        test_code = ''
        for test_path in test_file_path:
            with open(test_path, 'r') as f:
                test_code += f.read() + '\n'
        prompt = complete_code_bugfix_with_log(new_code, log_file, test_code)
        if get_token_length(prompt) > 64000:
            prompt = complete_code_bugfix(new_code)
        if get_token_length(prompt) > 64000:
            prompt = complet_code_bugfix_short(new_code, log_file, test_code)
        print(get_token_length(prompt))
        res = utils.get_response(prompt, model, model_ip)
        

    return utils.extract_code_loose(res), res, prompt



def gen_code(id, model, model_ip, repo_name, origin_file, test_path_list, prob_info, jsonl_file_path, mode, testcase):  
    repo_args = utils.get_repo_args(repo_name)
    repo_path = repo_args["repo_path"]
    source_code_path = os.path.join(repo_args['repo_running_path'], origin_file)
    source_code = utils.get_file_content(source_code_path).splitlines()
    
    
    prefix = source_code[:prob_info['key_block_start_lineno'] -1]
    prefix_response = source_code[prob_info['func_start_lineno']-1:prob_info['key_block_start_lineno']-1]
    suffix = source_code[prob_info['key_block_end_lineno']:]
    suffix_response = source_code[prob_info['key_block_end_lineno']:prob_info['func_end_lineno'] ]

    new_code = source_code[:prob_info['func_start_lineno'] -1] + prob_info['new_func_code'].splitlines() + source_code[prob_info['func_end_lineno']:]
    new_code = '\n'.join(new_code)

    completed_code, response, prompt = complete_code(new_code, id, origin_file, model, model_ip, test_path_list, repo_args, mode)
    
    completed_code = utils.remove_common_prefix(utils.remove_common_indent(completed_code),utils.remove_common_indent('\n'.join(str(x) for x in source_code[prob_info['func_start_lineno']-1:prob_info['key_block_start_lineno']-1])))
    indented_completed_key_block = utils.align_indent(completed_code.splitlines(), source_code[prob_info['key_block_start_lineno']-1:prob_info['key_block_end_lineno']], prefix, suffix )
    full_function = '\n'.join(prefix_response + indented_completed_key_block + suffix_response)
    result_data = {
        'ID': f'{testcase["type"]}-{testcase["id"]}',
        'repo_name': repo_name,
        'prompt': prompt,
        'response': full_function,
        'key_block_start_lineno': prob_info['key_block_start_lineno'],
        'key_block_end_lineno': prob_info['key_block_end_lineno'],
        'origin_file': origin_file,
        "source_file": source_code_path
    }


    with open(jsonl_file_path, 'a', encoding='utf-8') as jsonl_file:
        jsonl_file.write(json.dumps(result_data, ensure_ascii=False) + '\n')


if __name__ == "__main__":
    parser = setup_args_parser()
    args = parser.parse_args()
    args.testcase_file = config.single_testcases_path
    if type(args.type) is list:
        args.type = ' '.join(args.type)
    
    if not os.path.exists(args.testcase_file):
        print(f"{args.testcase_file} does not exist")
        sys.exit(1)
    
    # loading testcases
    testcases = utils.load_jsonl_to_list(args.testcase_file)
    results_dir = os.path.join(args.output_dir, 'results', args.model)
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    jsonl_file_path = os.path.join(results_dir, 'single_response.jsonl')
    if args.regenerate and os.path.exists(jsonl_file_path):
            os.remove(jsonl_file_path)

    if not os.path.exists(jsonl_file_path):
       generated_testcases = set()
    else:
        generated_testcases = utils.load_jsonl_to_set(jsonl_file_path, 'ID')
    
    for testcase in tqdm(testcases):
        id, typ, origin_file, test_path_list, prob_info, repo_name = testcase['id'], testcase['type'], testcase['origin_file'], testcase['test_list'], testcase['prob_info'], testcase['project']
        if typ not in args.type:
            continue
        if f'{typ}-{id}' in generated_testcases:
            continue
        gen_code(id, args.model, args.model_ip, repo_name, origin_file, test_path_list, prob_info, jsonl_file_path, typ, testcase)