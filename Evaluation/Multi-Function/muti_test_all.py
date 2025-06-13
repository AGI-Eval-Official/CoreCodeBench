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
# TODO: 删去了repo_name需要判断project，删去了if_comments需要读取type字段判断

parser = argparse.ArgumentParser()
# parser.add_argument('--if_comments', type=str, default='full', help='empty or full')
parser.add_argument('--mode', type=str, default='generate', help='generate or evaluate')#transformers,langchain,datachain
parser.add_argument('--model', type=str, default='gpt4o', help='args.model')
parser.add_argument('--output_dir', type=str, default='/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/', help='Output directory for results')
parser.add_argument('--regenerate', action='store_true')
# parser.add_argument('--repo_name', type=str, default='langchain', help='Repository name') # transformers, langchain

args = parser.parse_args()

# repo_name = args.repo_name
# output_dir = args.output_dir
# repo_args = utils.get_repo_args(args.repo_name)
# repo_path = repo_args["repo_path"]
# copy_path = repo_args["copy_path"]
# mapping_path = repo_args["test_mapping_path"]
# find_path = repo_args["find_path"]

func_testcases_info_path = os.path.join(args.output_dir, "CoreCodeBench", "CoreCodeBench_Multi.jsonl")
# if args.if_comments == "full":
#     func_testcases_info_path = os.path.join(func_testcase_dir, repo_name, "func_testcases_info.jsonl")
#     func_testcases_valid_info_path = os.path.join(func_testcase_dir, repo_name, "func_testcases_valid_info.jsonl")
#     func_testcases_combine_info_path = os.path.join(func_testcase_dir, repo_name, "func_testcases_combine_info.jsonl")
# else:
#     func_testcases_info_path = os.path.join(func_testcase_dir, repo_name, f"func_{args.if_comments}_testcases_info.jsonl")
#     func_testcases_valid_info_path = os.path.join(func_testcase_dir, repo_name, f"func_{args.if_comments}_testcases_valid_info.jsonl")
#     func_testcases_combine_info_path = os.path.join(func_testcase_dir, repo_name, f"func_{args.if_comments}_testcases_combine_info.jsonl")

# if not args.model == "retest":
#     func_testcases_info_path = func_testcases_combine_info_path
# else:
#     if os.path.exists(func_testcases_valid_info_path):
#         os.remove(func_testcases_valid_info_path)

# print(f"testing repo {repo_name}, \nrepo_path {repo_path}, \ncopy_path {copy_path}, \nmapping_path {mapping_path} \n")



# 创建临时文件
# TODO: if_comments 改为type

# FIXME: 临时文件路径问题
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

with open(func_testcases_info_path, 'r', encoding='utf-8') as file:
    combined_results_df = []
    for line in file:
        testcase = json.loads(line)

        repo_name = testcase["project"]
        problem_type = testcase["type"]
        args.repo_name = repo_name
        args.problem_type = problem_type        
        repo_log_dir = os.path.join(args.output_dir, "logs", args.mode)
        if not os.path.exists(repo_log_dir):
            os.makedirs(repo_log_dir)

        from multi_test import test_func
        try: 
            result_df = test_func(problem_type, args.mode, args.model, repo_name, testcase, temp_copy_path, args.regenerate, args.output_dir)
        except Exception as e:
            log_dir = os.path.join(args.output_dir, "logs", args.mode)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            command = [
                'python3', 'function_test.py',
                '--problem_type', args.problem_type,
                '--mode', args.mode,
                '--model', args.model,
                '--repo_name', repo_name,
                '--temp_copy_path', temp_copy_path,
            ]
            if args.regenerate:
                command += '--regenerate'
            with open (os.path.join(log_dir, f"{args.problem_type}_{args.model}_{"-".join(["+".join(single_id.split(".")[-2:]) for single_id in testcase["id"]])[:250].log}"), "w") as output_file:
                traceback.print_exc(file=output_file)
                output_file.write(f"An exception occurred: {e.__class__.__name__}: {e}\n")
                output_file.write("command: " + ' '.join(command))

    print("-" * 40)
if args.mode == 'evaluate' and temp_copy_path:
    shutil.rmtree(temp_copy_path)
  