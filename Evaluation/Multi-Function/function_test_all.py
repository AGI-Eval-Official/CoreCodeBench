import subprocess
import re
import ast
import textwrap  # 用于移除额外的缩进
import json
import os
import argparse
from variable_tracker import extract_lvalues_and_rvalues, extract_lvalues_new
import utils
import pandas as pd
import argparse
import traceback
from tqdm import tqdm

parser = argparse.ArgumentParser()
parser.add_argument('--if_comments', type=str, default='full', help='empty or full')
parser.add_argument('--mode', type=str, default='generate', help='generate or evaluate')#transformers,langchain,datachain
parser.add_argument('--model', type=str, default='gpt4o', help='args.model')
parser.add_argument('--output_dir', type=str, default='/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/', help='Output directory for results')
parser.add_argument('--regenerate', action='store_true')
parser.add_argument('--repo_name', type=str, default='langchain', help='Repository name') # transformers, langchain

args = parser.parse_args()

repo_name = args.repo_name
output_dir = args.output_dir
repo_args = utils.get_repo_args(args.repo_name)
repo_path = repo_args["repo_path"]
copy_path = repo_args["copy_path"]
mapping_path = repo_args["test_mapping_path"]
find_path = repo_args["find_path"]

func_testcase_dir = "/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/func_testcases"
if args.if_comments == "full":
    func_testcases_info_path = os.path.join(func_testcase_dir, repo_name, "func_testcases_info.jsonl")
    func_testcases_valid_info_path = os.path.join(func_testcase_dir, repo_name, "func_testcases_valid_info.jsonl")
    func_testcases_combine_info_path = os.path.join(func_testcase_dir, repo_name, "func_testcases_combine_info.jsonl")
else:
    func_testcases_info_path = os.path.join(func_testcase_dir, repo_name, f"func_{args.if_comments}_testcases_info.jsonl")
    func_testcases_valid_info_path = os.path.join(func_testcase_dir, repo_name, f"func_{args.if_comments}_testcases_valid_info.jsonl")
    func_testcases_combine_info_path = os.path.join(func_testcase_dir, repo_name, f"func_{args.if_comments}_testcases_combine_info.jsonl")

if not args.model == "retest":
    func_testcases_info_path = func_testcases_combine_info_path
else:
    if os.path.exists(func_testcases_valid_info_path):
        os.remove(func_testcases_valid_info_path)

print(f"testing repo {repo_name}, \nrepo_path {repo_path}, \ncopy_path {copy_path}, \nmapping_path {mapping_path} \n")



# 创建临时文件
if args.mode == 'evaluate':
    parent_dir = os.path.dirname(repo_args['copy_running_path'].rstrip('/\\'))
    tmp_copy_base = os.path.join(parent_dir, 'tmp')
    os.makedirs(tmp_copy_base, exist_ok=True)
    import tempfile
    import shutil
    temp_copy_path = tempfile.mkdtemp(prefix=f"{repo_name}_{args.model}_", dir=tmp_copy_base)
    print(repo_args['repo_running_path'])
    print(temp_copy_path)
    shutil.copytree(repo_args['repo_path'], temp_copy_path, dirs_exist_ok=True)
    
    if not temp_copy_path.endswith(os.sep):
        temp_copy_path += os.sep
else:
    temp_copy_path = repo_args['copy_path']


# with open(func_testcases_info_path, 'r', encoding='utf-8') as file:
#     data = json.load(file)
    
combined_results_df = []

# for testcase in data:
with open(func_testcases_info_path, 'r', encoding='utf-8') as file:
    for line in file:
        testcase = json.loads(line)

        test_path_list = testcase["test_list"]

        # 打印或使用提取的信息
        print(f"Test Path: {test_path_list}")
        
        repo_log_dir = os.path.join(output_dir, 'func_results', repo_name, "log")
        if not os.path.exists(repo_log_dir):
            os.makedirs(repo_log_dir)

        with open (os.path.join(repo_log_dir, f"test_log_{args.mode}_{args.if_comments}_{args.model}.txt"), "a") as f:
            from function_test import test_func
            try: 
                result_df = test_func(args.if_comments, args.mode, args.model, repo_name, testcase, test_path_list, temp_copy_path, args.regenerate, output_dir)
            except Exception as e:
                log_dir = os.path.join(repo_log_dir, args.if_comments, args.mode, args.model)
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                test_path = ";".join(testcase["id"])
                command = [
                    'python3', 'function_test.py',
                    '--if_comments', args.if_comments,
                    '--mode', args.mode,
                    '--model', args.model,
                    '--testcase', testcase,
                    '--repo_name', repo_name,
                    '--temp_copy_path', temp_copy_path,
                ]
                if args.regenerate:
                    command += '--regenerate'
                with open (os.path.join(log_dir, f"{test_path.replace(copy_path, '').replace('/', '.')}.txt"), "w") as output_file:
                    traceback.print_exc(file=output_file)
                    output_file.write(f"An exception occurred: {e.__class__.__name__}: {e}\n")
                    output_file.write("command: \n" + ' '.join(command))

                f.write(f"Encountered error while testing {test_path}\n")
            else: 
                test_path = ";".join(testcase["id"])
                f.write(f"Tested {test_path}\n")
                
            if args.mode == "evaluate":
                total_num = testcase["pytest_info"]["total_num"]
                if args.model == "retest":
                    base_passed_num = int(result_df["passed"][0])
                    if base_passed_num >= int(total_num):
                        print("-"*20 + "Unqualified!" + "-"*20)
                        continue
                    testcase["pytest_info"]["base_passed_num"] = base_passed_num
                    with open (func_testcases_valid_info_path, "a") as valid_file:
                        # print(testcase)
                        json_line = json.dumps(testcase, ensure_ascii=False)
                        valid_file.write(json_line + "\n")
                    
                combined_results_df.append(result_df)
        print("-" * 40)
if args.mode == "evaluate":
    print("storing data")
    df = pd.concat(combined_results_df, ignore_index=True)
    pass_rate =  df["pass_rate"].mean()
    pass_all = df["pass_all"].mean()
    average = pd.DataFrame({
        'test_id': ["average"],
        'passed': [0],
        'skipped': [0],
        'failed': [0],
        'pass_rate': [pass_rate],
        'pass_all': [pass_all]
    }, index=[0])
    df = pd.concat([df, average], ignore_index=True)
    print(df)
    if args.if_comments == "full":
        df.to_excel(os.path.join("/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/func_testcases", repo_name, f'''{args.model}_results.xlsx'''), index=False)
    else:
        save_path = os.path.join("/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/func_testcases", repo_name, args.if_comments)
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        df.to_excel(os.path.join("/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/func_testcases", repo_name, args.if_comments, f'''{args.model}_results.xlsx'''), index=False)
if args.mode == 'evaluate' and temp_copy_path:
    shutil.rmtree(temp_copy_path)
  