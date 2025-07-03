# -*- coding: utf-8 -*-
import re
import os
import sys
import ast
import textwrap  # 用于移除额外的缩进
import json
import argparse
import subprocess
import CorePipe.utils as utils 
import CorePipe.config as config
import argparse
import random
from tqdm import tqdm

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gen_model', default='mix', help='Repository name')
    parser.add_argument('--rewrite_model', default='mix', help='rewrite model')
    parser.add_argument('--repo_name', default='open-iris', help='Repository name')
    args = parser.parse_args()
    args.output_dir = os.path.join(config.workspace, args.repo_name)
    args.rewrite_models = config.rewrite_models
    args.gen_models = config.gen_models
    args.repo_args = utils.get_repo_args(args.repo_name)
    args.mapping_path = os.path.join(config.workspace, args.repo_name, "output_testcase_mapping_valid.jsonl")
    args.output_dir = os.path.join(config.workspace, args.repo_name)
    args.repo_path = args.repo_args["repo_path"]
    
    args.debug_dir = os.path.join(args.output_dir, 'DEBUG')
    if not os.path.exists(args.debug_dir):
        os.makedirs(args.debug_dir)
    args.buggy_retest_dir = os.path.join(args.output_dir, 'DEBUG', 'BUGGY_retest')
    return args




def complete_code(prompt, model):
    chat_message = f'''下面是一段包含占位符 `<complete code here>` 的代码片段。请根据缺失代码的描述，在 `<complete code here>`处生成适当的代码块。
请使用markdown格式(```python```)输出你补全的代码块。
**注意**：请确保你补全的代码块符合上下文代码的缩进，也就是说，需要保留原来代码的缩进。
代码片段:
```python
{prompt}
```
请使用markdown格式(```python```)输出你补全的代码块。需要保留<complete code here>前后原来代码的缩进。
'''
    res = utils.get_response(chat_message, model=model)
    return utils.extract_code(res), res


def generate_buggy_code(testcase, problem, buggy_logic_response):
    def extract_buggy_logic(string):
        pattern = r"```(.*?)```"
        matches = re.findall(pattern, string, re.DOTALL)

        for content in matches:
            content = content.strip()
            if content.startswith("2. **逻辑**"):
                return content
        return None
    buggy_logic =  extract_buggy_logic(buggy_logic_response)
    if not buggy_logic:
        return False
    buggy_logic = "\n".join("# " + line for line in buggy_logic.splitlines())

    if buggy_logic:
        pattern = r"(#2\. \*\*逻辑\*\*.*?)(?=#3\. \*\*异常\*\*)"
        try:
            modified_problem = re.sub(pattern, buggy_logic, problem, flags=re.DOTALL)
        except:
            return None

        source_code_path = os.path.join(repo_args['repo_running_path'], testcase['origin_file']) 
        with open(source_code_path, 'r') as f:
            source_code = f.read().splitlines()
        prompt = '\n'.join(source_code[:testcase["prob_info"]['key_block_start_lineno'] - 1]) \
                            + modified_problem + \
                '\n'.join(source_code[testcase["prob_info"]['key_block_end_lineno']:])
        if args.gen_model == 'mix':
            gen_model = random.choice(gen_models)
        else:
            gen_model = args.gen_model
        buggy_code, response = complete_code(prompt, gen_model)
        
        buggy_func_code = '\n'.join(source_code[testcase["prob_info"]['func_start_lineno'] - 1:testcase["prob_info"]['key_block_start_lineno'] - 1]) \
                                 + '\n<buggy_code_start_here>\n' +  buggy_code + '\n<buggy_code_end_here>\n' \
                                   + '\n'.join(source_code[testcase["prob_info"]['key_block_end_lineno']:testcase["prob_info"]['func_end_lineno']])
        new_testcase = testcase.copy()
        new_testcase['prob_info']= {
            'func_start_lineno': testcase['prob_info']['func_start_lineno'],
            'func_end_lineno': testcase['prob_info']['func_end_lineno'],
            'new_func_code': buggy_func_code
        }
        new_testcase['IG_base'] = None
        new_testcase['score'] = None
        new_testcase['LLM_score'] = None
        new_testcase['pytest_info'] = {
            'total_num': testcase['pytest_info']['total_num']
        }
        
        new_testcase['model_info'] = {
            'gen_model': testcase['model_info']['gen_model'] if 'gen_model' in testcase['model_info'] else 'gpt4o',
            'rewrite_model': testcase['model_info']['rewrite_model'],
            'debug_gen_model': gen_model
        }
        
        new_testcase['type'] = 'debug'
        return new_testcase

    return None



def retest(args, testcase, tmp_repo_path):
    source_path = os.path.join(args.repo_args['repo_running_path'], testcase['origin_file'])
    with open(source_path, 'r') as f:
        source_code = f.read().splitlines()
    prefix = '\n'.join(source_code[:testcase['prob_info']['func_start_lineno'] - 1])
    suffix =  '\n'.join(source_code[testcase['prob_info']['func_end_lineno']:])
    new_code = prefix + testcase['prob_info']['new_func_code'].replace('<buggy_code_start_here>','').replace('<buggy_code_end_here>','') + suffix
    tmp_running_file = source_path.replace(repo_args['repo_path'], tmp_repo_path)
    with open(tmp_running_file, 'w') as f:
        f.write(new_code)
    test_path = os.path.join(tmp_repo_path, testcase['test_list'][0])
    log_path = os.path.join(args.buggy_logic_dir, 'retest_{}.log'.format(testcase['id']))
    env = os.environ.copy()
    running_path = repo_args['repo_running_path'].replace(repo_args['repo_path'], tmp_repo_path)
    env["PYTHONPATH"] =running_path
    env["http_proxy"] = "http://10.229.18.30:8412"
    env["https_proxy"] = "http://10.229.18.30:8412"
    
    pytest_command = f"export PYTHONPATH={running_path} && python -m pytest {test_path} --tb=long > {log_path} 2>&1"
    print(pytest_command)
    try:
        result = subprocess.run(pytest_command, env=env, timeout=120, shell=True)
    except subprocess.TimeoutExpired:
        print("测试超时")
        return False, None
    #恢复文件
    shutil.copy(source_path, tmp_running_file)
    if result.returncode == 0:
        print("所有测试通过或跳过")
        return False, None
    else:
        print("有测试失败或错误发生")
        passed, skipped, failed = utils.read_log(log_path)
        return True, (passed, skipped, failed)
   
def modify_logic(question, rewrite_model):
    prompt = f'''请根据以下代码解释，改写`2. **逻辑**`的部分，在其中引入一些会影响程序正确性的逻辑漏洞。要求逻辑漏洞是合理的，符合人类习惯的。
逻辑漏洞类型包括但不限于边界条件处理不当，循环或者递归条件错误，条件判断错误，变量错误等等。
请输出修改后“逻辑”项，用``` ```框出。注意，请不要显式在逻辑项中写出逻辑漏洞是什么。
待修改的解释文字：```
{question}
```
样例输出：
```
2. **逻辑**
改写后的“逻辑”项。
```
请确保漏洞难以被发现，但能够导致程序在一些情况（例如边界条件、特殊情况）下出现不符合预期的行为。
'''
    return utils.get_response(prompt, rewrite_model)


if __name__ == '__main__':
    args = parse_args()
    args.dev_path = os.path.join(config.testcases_path, args.repo_name,'single','Development.jsonl')
    
    # 生成错误逻辑（rewrite）
    if not os.path.exists(os.path.join(args.debug_dir, 'buggy_logic.jsonl')):
        generated_buggy_testcases = []
    else: 
        buggy_logical_testcase = utils.load_jsonl_to_dict(os.path.join(args.debug_dir, 'buggy_logic.jsonl'), 'id')
        generated_buggy_testcases = list(buggy_logical_testcase.keys())
    
    test_file_jsonl = utils.load_jsonl_to_dict(args.dev_path, 'id')
    
    with open(os.path.join(args.debug_dir, 'buggy_logic.jsonl'), 'a', encoding='utf-8') as f:
        for id, testcase in tqdm(test_file_jsonl.items()):
            if id in generated_buggy_testcases:
                continue
            
            code_block = testcase['prob_info']['new_func_code']
                
            pattern = r"# 本段代码的功能解释：(.*?)<complete code here>"
            match = re.search(pattern, code_block, re.DOTALL)
            if match:
                problem = match.group(1).strip()
            else:
                problem = None
                continue
            
            if problem:
                if args.rewrite_model =='mix':
                    rewrite_model = random.choice(args.rewrite_models)
                    buggy_logic_response = modify_logic(problem, rewrite_model)
                else:
                    rewrite_model = args.rewrite_model
                    buggy_logic_response = modify_logic(problem, args.rewrite_model)
                
                print(f'True logic:\n {problem}')
                print(f'Buggy Logic:\n {buggy_logic_response}')
                generated_buggy_testcases.append(id)
                buggy_testcase = testcase.copy()
                buggy_testcase['model_info'] = {
                    'rewrite_model':rewrite_model
                }
                buggy_testcase['buggy_logic_response'] = buggy_logic_response
                buggy_testcase['problem'] = problem
                f.write(json.dumps(buggy_testcase, ensure_ascii=False) + '\n')
                
                   
    assert os.path.exists(os.path.join(args.buggy_logic_dir, 'buggy_logic.jsonl'))

    print('Generate model test passed!')
    print('Generating buggy code....')
    buggy_testcases = utils.load_jsonl_to_dict(os.path.join(args.debug_dir, 'buggy_logic.jsonl'), 'id')
    if os.path.exists(os.path.join(args.debug_dir, 'first_gen_testcases.jsonl')):
        os.remove(os.path.join(args.debug_dir, 'first_gen_testcases.jsonl'))
        
    with open(os.path.join(args.debug_dir, 'first_gen_testcases.jsonl'),  'a', encoding='utf-8') as f:
        for id, testcase in buggy_testcases.items():
            problem = testcase['problem']
            buggy_logic_response = testcase['buggy_logic_response']
            buggy_testcase = generate_buggy_code(testcase, problem, buggy_logic_response)
            if buggy_testcase:
                json_line = json.dumps(buggy_testcase, ensure_ascii=False)
                f.write(json_line + '\n')
                print(buggy_testcase['id'])
    
    print('Retesting....')
    
    # copy temp test file
    temp_dir = os.path.join(config.root_path, 'tmp_source')
    os.makedirs(temp_dir, exist_ok=True)
    temp_copy_path = tempfile.mkdtemp(prefix=f'GEN_RETEST_{args.repo_name}_', dir=temp_dir)
    shutil.copytree(args.repo_path, temp_copy_path, dirs_exist_ok=True)
    if not temp_copy_path.endswith(os.sep):
        temp_copy_path += os.sep
    
    
    # retest
    testcase_jsonl = utils.load_jsonl_to_dict(os.path.join(args.buggy_logic_dir, 'first_gen_testcases.jsonl'), 'id') 
    valid_buggy_testcases = []
    try:
        for id, testcase in testcase_jsonl.items():
            retest_flag, scores = retest(testcase, temp_copy_path)
            if retest_flag:
                testcase['pytest_info']['base_passed_num'] = scores[0]
                valid_buggy_testcases.append(testcase)
        utils.write_list_to_jsonl(os.path.join(config.testcases_path, args.repo_name,'single','BugFix.jsonl'), valid_buggy_testcases)
    finally:
        if temp_copy_path:
            shutil.rmtree(temp_copy_path)
