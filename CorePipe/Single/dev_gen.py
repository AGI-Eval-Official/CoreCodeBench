import json
import os
import argparse
import CorePipe.utils as utils
import CorePipe.config as config
import logging
from tqdm import tqdm
import tempfile
import shutil


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo_name', type=str, default='', help='Repository name')
    parser.add_argument('--model', type=str, default='gpt4o', help='Model name')
    parser.add_argument('--validate_model', type=str, default='claude3.5', help='Model name')
    args = parser.parse_args()
    args.repo_args = utils.get_repo_args(args.repo_name)
    args.mapping_path = os.path.join(config.workspace, args.repo_name, "output_testcase_mapping_valid.jsonl")
    args.output_dir = os.path.join(config.workspace, args.repo_name)
    args.repo_path = args.repo_args["repo_path"]
    args.repo_running_path = args.repo_args["repo_running_path"]
    return args
    

if __name__ == "__main__":
    args = parse_args()
    # copy temp test file
    temp_dir = os.path.join(config.root_path, 'tmp_source')
    os.makedirs(temp_dir, exist_ok=True)
    temp_copy_path = tempfile.mkdtemp(prefix=f'GEN_DEV_{args.repo_name}_', dir=temp_dir)
    shutil.copytree(args.repo_path, temp_copy_path, dirs_exist_ok=True)
    if not temp_copy_path.endswith(os.sep):
        temp_copy_path += os.sep
        
    args.tmp_repo_path = temp_copy_path
    
    with open(args.mapping_path, 'r', encoding='utf-8') as file:
        for line_num, line in enumerate(tqdm(file, desc="Processing lines")):
            data = json.loads(line.strip())
            test_file = data.get("test_file", "")
            origin_file = data.get("origin_file", "")
            pytest_info = data.get("pytest", "")
            file_name = origin_file.split('/')[-1].replace('.py', '')
            
            file_path = os.path.dirname(origin_file)
            test_case_dir = os.path.join(args.output_dir, 'testcases', file_path, file_name)
            testcases_info_path = os.path.join(test_case_dir, 'testcases_info.jsonl')
            
            if os.path.exists(testcases_info_path):
                print(f'{file_path}/{file_name}.py has generated!')
                continue
            elif not os.path.exists(test_case_dir):
                os.makedirs(test_case_dir)

            logging.info(f"Test Path: {test_file}")
            logging.info(f"Origin File: {origin_file}")
            logging.info(f"File Name: {file_name}")
            logging.info(f"File Path: {file_path}\n")

            log_dir = os.path.join(args.output_dir, 'gen_log', file_path, f'{file_name}.log')
            if not os.path.exists(os.path.dirname(log_dir)):
                os.makedirs(os.path.dirname(log_dir))

            from CorePipe.Single.code_gen import gen_comment

            gen_result = gen_comment(args, args.repo_name, file_path, file_name, test_file, pytest_info, args.model, args.validate_model, testcases_info_path)

    shutil.rmtree(temp_copy_path)

            
