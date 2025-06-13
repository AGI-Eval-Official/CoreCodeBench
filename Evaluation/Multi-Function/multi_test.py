# -*- coding: utf-8 -*-
from server import LocalClient
import json
import os
import shutil
from utils import generate_xlsx, read_log, extract_code
import argparse
import pandas as pd
import utils
import time
import re


parser = argparse.ArgumentParser()
parser.add_argument('--if_comments', type=str, default='empty', help='empty or full')
parser.add_argument('--mode', type=str, default='generate', help='generate or evaluate')
parser.add_argument('--model', type=str, default='llama', help='args.model')

parser.add_argument('--repo_name', type=str, default='transformers', help='Repository name')
parser.add_argument('--test_path', type=str, default='/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/Source_Copy/transformers/tests/utils/test_audio_utils.py', help='Output directory for results')
parser.add_argument('--output_dir', type=str, default='/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/', help='Output directory for results')
parser.add_argument('--temp_copy_path', type=str, default='', help='Output directory for results')
parser.add_argument('--regenerate', action='store_true', help='regenerate/reevaluate everything')

args = parser.parse_args()


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
    # print("#"*40)
    # print(code_dict)
    return code_dict


def complete_code(idq_list, not_idq_list, model):
    if model == "retest":
        response = ""
        for idq in idq_list:
            response += "<id>" + idq + "</id>\n```python\n" + "_ = 1\n```\n"
        return extract_code_blocks(response), response, response
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
    chat_message = f'''
If you were a code completion agent, I would provide you with a snippet of code, and you would need to return the completed code segment. 
the code after <ralated code> is used while calling the code to be completed. 
You need to complete code blocks after <complete following code> by predicting the codes after <complete code here>, <id> label wraps the position of the code.
Your output should include the <id></id> label, followed by the completed code snippet enclosed within triple backticks ```, ensuring clarity and proper formatting.
{code_seg}
'''
    # print(chat_message)
    res = utils.get_response(chat_message, model=model)
    # print("~"*40)

    return extract_code_blocks(res), res, chat_message

def get_testcases(id):
    testcases = {}
    if args.if_comments == "full" or args.if_comments == "sub":
        testcase_file_dir = os.path.join(args.output_dir, 'func_testcases', args.repo_name, f'{args.repo_name}.jsonl')
    elif args.if_comments == "tdd":
        testcase_file_dir = f"/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/TDD_results/{args.repo_name}/{args.repo_name}.jsonl"
    with open (testcase_file_dir, "r") as testcase_file:
        for line in testcase_file:
            data = json.loads(line)
            if data['id'] == id:
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


def generate_id_code(if_comments, result_dir, id, origin_file, prob_info, node):
    idq_list = {}
    not_idq_list = {}
    # id_node_mapping = {}
    for index, name in enumerate(node):
        path = origin_file[index]
        file_name = path.split('/')[-1].replace('.py', '')
        src_transformers_index = path.find(args.find_path)
        file_path = path[src_transformers_index + len(args.find_path):path.rfind('/')]
        if name.split(".")[-2] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-1]+".py"
        elif name.split(".")[-3] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-2] + "::" + name.split(".")[-1] + ".py"
        problem_id = os.path.join(args.repo_name, file_path, file_name, func_file).replace(".py", "").replace("/", ".")
        source_code_path = os.path.join(args.repo_path, file_path, f'{file_name}.py')
        with open(source_code_path, 'r') as f:
            source_code = f.read().splitlines()  
        if problem_id in set(id):
            print(problem_id)
            testcases = get_testcases(problem_id)
            # print(testcases)
            func_name = func_file.replace(".py", "")
            for func, item in testcases.items():
                if func != func_name:
                    continue
                test_id, testcase = item
                # prompt = ""
                # print(testcase['func_start_lineno'])
                # if args.if_comments == 'full':
                    # idq_list[name] = source_code[:testcase['func_start_lineno'] -1] + testcase['new_func_code'].splitlines() + source_code[testcase['func_end_lineno']:]
                idq_list[name] = testcase['new_func_code'].splitlines()
                # elif args.if_comments == "empty":
                #     new_func_lines = testcase['new_func_code'].splitlines()
                #     updated_func_lines = []
                #     inside_placeholder = False

                #     for line in new_func_lines:
                #         if "# 本段代码的功能解释：" in line:
                #             inside_placeholder = True
                #         elif "<complete code here>" in line:
                #             inside_placeholder = False
                #             updated_func_lines.append("<complete code here>")
                #         elif not inside_placeholder:
                #             updated_func_lines.append(line)

                #     # idq_list[name] = source_code[:testcase['func_start_lineno'] - 1] + updated_func_lines + source_code[testcase['func_end_lineno']:]
                #     idq_list[name] = updated_func_lines

                print('FUNC',func)
        else:
            # print(len(prob_info))
            func_start_lineno, func_end_lineno = prob_info[index]["func_start_lineno"], prob_info[index]["func_end_lineno"]
            code = source_code[func_start_lineno:func_end_lineno]
            not_idq_list[name] = code
        save_dir = os.path.join(result_dir,f'''{file_path.replace("/", "-")}-{file_name}_completed_{args.model}.py''')
        if os.path.exists(save_dir) and args.regenerate:
            # print("!!!!!!removing")
            os.remove(save_dir)
    # file_exists = os.path.exists(os.path.join(result_dir,f'''{func}_completed_{args.model}.py'''))
    # if file_exists and not args.regenerate:
    #     return
    completed_key_block_dict, response, chat_message = complete_code(idq_list, not_idq_list, args.model)
    # print(completed_key_block_dict)
    # 对齐缩进
    with open(os.path.join(result_dir,f'''response_{args.model}.txt'''),'w') as f:
        f.write(response)
    with open(os.path.join(result_dir,f'''prompt_{args.model}.txt'''),'w') as f:
        f.write(chat_message)
    with open(os.path.join(result_dir,f'''completed_key_block_dict_{args.model}.txt'''),'w') as f:
        f.write(str(completed_key_block_dict))
    # 保存
    for idname in completed_key_block_dict:
        print(idname)
        index = node.index(idname)
        path = origin_file[index]
        file_name = path.split('/')[-1].replace('.py', '')
        src_transformers_index = path.find(args.find_path)
        file_path = path[src_transformers_index + len(args.find_path):path.rfind('/')]
        
        if idname.split(".")[-2] == path.split("/")[-1].split(".")[0]:
            func_file = idname.split(".")[-1]+".py"
        elif idname.split(".")[-3] == path.split("/")[-1].split(".")[0]:
            func_file = idname.split(".")[-2] + "::" + idname.split(".")[-1] + ".py"
        problem_id = os.path.join(args.repo_name, file_path, file_name, func_file).replace(".py", "").replace("/", ".")
        
        source_code_path = os.path.join(args.repo_path, file_path, f'{file_name}.py')
        with open(source_code_path, 'r') as f:
            source_code = f.read().splitlines()
        test_case_dir = os.path.join(args.output_dir, 'testcases', args.repo_name,  file_path, file_name)
        testcases = get_testcases(problem_id)
        func_name = func_file.replace(".py", "")
        save_dir = os.path.join(result_dir,f'''{file_path.replace("/", "-")}-{file_name}_completed_{args.model}.py''')
        print(func_name)
        for func, item in testcases.items():
            if func != func_name:
                print(func)
                continue
            test_id, testcase = item
            if os.path.exists(save_dir):
                with open(save_dir, 'r') as save_file:
                    save_code = save_file.read()
            else:
                save_code = '\n'.join(source_code)
            


            prefix = source_code[:testcase['key_block_start_lineno'] -1]
            suffix = source_code[testcase['key_block_end_lineno']:]
            completed_key_block = completed_key_block_dict[idname]
            # print("completed_key_block")
            print(completed_key_block)

            completed_code = remove_common_prefix(remove_common_indent(completed_key_block),remove_common_indent('\n'.join(str(x) for x in source_code[testcase['func_start_lineno']-1:testcase['key_block_start_lineno']-1])))

            indented_completed_key_block = utils.align_indent(completed_code.splitlines(), source_code[testcase['key_block_start_lineno']-1:testcase['key_block_end_lineno']], prefix, suffix )
            # print("indented_completed_key_block")
            # print('\n'.join(indented_completed_key_block))
            # print("replaced_code")
            compeletd_code = prefix + indented_completed_key_block + suffix
            
            replaced_code = '\n'.join(source_code[testcase['key_block_start_lineno']-1:testcase['key_block_end_lineno']])
            # print(replaced_code)
            new_save_code = save_code.replace(replaced_code, '\n'.join(indented_completed_key_block))
            print(os.path.join(result_dir,f'''completed_{args.model}.py'''))
            with open(os.path.join(result_dir,f'''{func}_completed_{args.model}.py'''),'w') as f:
                f.write('#test_copy\n' + '\n'.join(compeletd_code))
            with open(os.path.join(result_dir, f'''{file_path.replace("/", "-")}-{file_name}.source.py'''),'w') as f:
                f.write('\n'.join(source_code))
            with open(save_dir, "w") as save_file:
                save_file.write(new_save_code)
            
    
def evaluate_code(test_path, result_dir, id, origin_file, prob_info, node, running_path, tmp_test_path, pytest_info):
    test_file = test_path.split("/")[-1].replace(".py", "")
    if os.path.exists(os.path.join(result_dir, f'''{args.model}_{test_file}_results.xlsx''')) and not args.regenerate:
        print("Results already exist, skipping evaluation.")
        return pd.read_excel(os.path.join(result_dir, f'''{args.model}_{test_file}_results.xlsx'''))
    results_df = pd.DataFrame(columns=['test_id', 'passed', 'skipped', 'failed', 'pass_rate', 'pass_all'])
    # if not args.regenerate and os.path.exists(os.path.join(result_dir, f'''{args.model}_results.xlsx''')):
    #     return 
    for index, name in enumerate(node):
        path = origin_file[index]
        file_name = path.split('/')[-1].replace('.py', '')
        src_transformers_index = path.find(args.find_path)
        file_path = path[src_transformers_index + len(args.find_path):path.rfind('/')]
        if name.split(".")[-2] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-1]+".py"
        elif name.split(".")[-3] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-2] + "::" + name.split(".")[-1] + ".py"
        problem_id = os.path.join(args.repo_name, file_path, file_name, func_file).replace(".py", "").replace("/", ".")
        source_code_path = os.path.join(args.repo_path, file_path, f'{file_name}.py')
        with open(source_code_path, 'r') as f:
            source_code = f.read().splitlines()  
        if problem_id in set(id):
            testcases = get_testcases(problem_id)
            func_name = func_file.replace(".py", "")
            print(func_name)
            for func, item in testcases.items():
                if func != func_name:
                    continue
                if not os.path.exists(os.path.join(result_dir,f'''{file_path.replace("/", "-")}-{file_name}_completed_{args.model}.py''')):
                    print("No completed code found, skipping evaluation.")
                    return results_df._append({'test_id': "-".join(["+".join(single_id.split(".")[-2:]) for single_id in id]), 'passed': 0, 'skipped': 0, 'failed': 0, 'pass_rate': 0, 'pass_all': 0}, ignore_index=True)
                shutil.copy(os.path.join(result_dir,f'''{file_path.replace("/", "-")}-{file_name}_completed_{args.model}.py'''), source_code_path.replace(args.repo_running_path, running_path))
    os.chdir(args.running_path)

    BASH = f'''PYTHONPATH={args.running_path} timeout 600 pytest {tmp_test_path} --tb=long > {result_dir}/{args.model}_{test_file}_result.log 2>&1'''
    print(BASH) 
    os.system(BASH)
    if os.path.exists(os.path.join(result_dir, f'''{args.model}_{test_file}_result.log''')):
        passed, skipped, failed = read_log(os.path.join(result_dir, f'''{args.model}_{test_file}_result.log'''))
    else:
        passed, skipped, failed = 0, 0, 0
    if args.model != "retest":
        pass_rate = max(0, (passed-pytest_info['base_passed_num'])/(pytest_info['total_num']-pytest_info['base_passed_num']))
        pass_all = int(passed == pytest_info['total_num'])
    else:
        pass_rate, pass_all = 0, 0
    # passall = (passed == pytest_info['total_num'])
    results_df = results_df._append({'test_id': "-".join(["+".join(single_id.split(".")[-2:]) for single_id in id]), 'passed': passed, 'skipped': skipped, 'failed': failed, 'pass_rate':pass_rate, "pass_all": pass_all}, ignore_index=True)
    for index, name in enumerate(node):
        path = origin_file[index]
        file_name = path.split('/')[-1].replace('.py', '')
        src_transformers_index = path.find(args.find_path)
        file_path = path[src_transformers_index + len(args.find_path):path.rfind('/')]
        if name.split(".")[-2] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-1]+".py"
        elif name.split(".")[-3] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-2] + "::" + name.split(".")[-1] + ".py"
        problem_id = os.path.join(args.repo_name, file_path, file_name, func_file).replace(".py", "").replace("/", ".")
        source_code_path = os.path.join(args.repo_path, file_path, f'{file_name}.py')
        shutil.copy(source_code_path, source_code_path.replace(source_code_path, source_code_path.replace(args.repo_running_path, args.running_path))) # 复原文件
    results_df.to_excel(os.path.join(result_dir, f'''{args.model}_{test_file}_results.xlsx'''), index=False)
    return results_df
    
   
def test_func(if_comments, mode, model, repo_name, testcase, tmp_repo_path, regenerate, output_dir = "/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/"):
    # FIXME: test_path_list
    args.if_comments = if_comments
    args.mode = mode
    args.model = model
    args.repo_name = repo_name
    args.testcase = testcase
    args.test_path_list = test_path_list
    args.output_dir = output_dir
    repo_args = utils.get_repo_args(args.repo_name)
    running_path = repo_args['repo_running_path'].replace(repo_args['repo_path'], tmp_repo_path)
    args.running_path = running_path
    args.regenerate = regenerate
    repo_path, copy_path, repo_running_path = repo_args["repo_path"], repo_args["copy_path"], repo_args["repo_running_path"]
    
    find_path = repo_args["find_path"]
    args.repo_path, args.copy_path, args.find_path, args.repo_running_path = repo_path, copy_path, find_path, repo_running_path

    id = testcase["id"]
    origin_file = testcase["origin_file"]
    prob_info = testcase["prob_info"]
    node = testcase["node"]
    pytest_info = testcase["pytest_info"]


    func_test_case_dir = os.path.join(output_dir, 'func_testcases', repo_name)
    print(f"testing repo {repo_name}")
    print(f"model {model}, mode {mode}, regenerate {args.regenerate}")
    print(f"test path list: {test_path_list}")

    if args.if_comments == "full":
        result_dir = os.path.join(output_dir, 'func_results', repo_name, "-".join(["+".join(single_id.split(".")[-2:]) for single_id in id])[:250], args.if_comments)
    # result_dir = os.path.join(output_dir, 'func_results', repo_name, test_path.replace(copy_path, "").replace(".py", ""), args.if_comments)
    else:
        result_dir = os.path.join(output_dir, 'func_results', repo_name, args.if_comments, "-".join(["+".join(single_id.split(".")[-2:]) for single_id in id])[:250])
    
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    if args.mode == "generate":
        generate_id_code(args.if_comments, result_dir, id, origin_file, prob_info, node)

    elif args.mode == "evaluate":
        result = pd.DataFrame(columns=['test_id', 'passed', 'skipped', 'failed', 'pass_rate', 'pass_all'])
        for idx, test_path in enumerate(test_path_list):
            tmp_test_path = test_path.replace(copy_path, tmp_repo_path)
            result_df = evaluate_code(test_path, result_dir, id, origin_file, prob_info, node, running_path, tmp_test_path, pytest_info)
            if idx == 0:
                result = result_df
            else:
                result = result.add(result_df, fill_value=0)
                # result["test_id"][0] = result_df["test_id"][0]  
        if args.model != "retest":
            result["pass_rate"][0] = max(0, (result["passed"][0]-pytest_info['base_passed_num'])/(pytest_info['total_num']-pytest_info['base_passed_num']))
            result["pass_all"][0] = int(result["passed"][0] == pytest_info['total_num'])
        print(result)
        return result


if __name__ == "__main__":
    repo_args = utils.get_repo_args(args.repo_name)
    repo_path, copy_path, repo_running_path = repo_args["repo_path"], repo_args["copy_path"], repo_args["repo_running_path"]
    test_case_dir = os.path.join(args.output_dir, 'func_testcases', args.repo_name, args.test_path.replace(copy_path, "").replace(".py", ""))

    with open(os.path.join(test_case_dir, 'func_testcases_info.json'), "r") as testcase_file:
        args.testcase = json.load(testcase_file)
    test_func(args.if_comments, args.mode, args.model, args.repo_name, args.testcase, args.test_path, args.running_path, args.regenerate, args.output_dir)
    