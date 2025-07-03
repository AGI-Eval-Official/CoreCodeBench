import subprocess
import re
import ast
import textwrap
import json
import os
import argparse
import CorePipe.utils as utils
import traceback
import CorePipe.config as config
import tempfile
import shutil
from CorePipe.Single.function_tracker import track_function
import logging

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo_name', type=str, default='', help='Repository name')
    args = parser.parse_args()
    repo_args = utils.get_repo_args(args.repo_name)
    args.mapping_path = os.path.join(config.workspace, args.repo_name, "output_testcase_mapping_valid.jsonl")
    args.output_dir = os.path.join(config.workspace, args.repo_name)
    args.repo_path = repo_args["repo_path"]
    args.repo_running_path = repo_args['repo_running_path']
    args.import_name = repo_args["import_name"]
    args.repo_args = repo_args
    return args


if __name__ == "__main__":
    args = parse_args()
    args.func_call_root_dir = os.path.join(args.output_dir, 'func_call_trees')
    args.test_case_root_dir = os.path.join(args.output_dir, 'testcases')
    if not os.path.exists(args.test_case_root_dir):
        os.makedirs(args.test_case_root_dir)
    
    # copy temp test file
    temp_dir = os.path.join(config.root_path, 'tmp_source')
    os.makedirs(temp_dir, exist_ok=True)
    temp_copy_path = tempfile.mkdtemp(prefix=f'GEN_TREE_{args.repo_name}_', dir=temp_dir)
    shutil.copytree(args.repo_path, temp_copy_path, dirs_exist_ok=True)
    if not temp_copy_path.endswith(os.sep):
        temp_copy_path += os.sep
    
    try:
        with open(args.mapping_path, 'r', encoding='utf-8') as file:
            testcase_infos = []
            tested_files = []
            for line_num, line in enumerate(file):
                data = json.loads(line.strip())
                test_file = data.get("test_file", "")
                origin_file = data.get("origin_file", "")

                file_name = origin_file.split('/')[-1].replace('.py', '')
                tree_path = os.path.join(args.func_call_root_dir, test_file.replace(".py", "") )
                if not os.path.exists(tree_path):
                    os.makedirs(tree_path)
                   
                return_code = track_function(args, test_file, tree_path, temp_copy_path)
                if return_code == False:
                    raise Exception(f"{test_file} encountered error in function tracker\n")
    
    except Exception as e:
        logging.error(f"Function tree generator error: {e}")
        traceback.print_exc()
        exit(1)
    finally:
        shutil.rmtree(temp_copy_path)
             
