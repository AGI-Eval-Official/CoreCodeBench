import subprocess
import re
import ast
import textwrap  # 用于移除额外的缩进
import json
import os
import argparse
import traceback
from tqdm import tqdm
import CorePipe.utils as utils
import CorePipe.config as config

parser = argparse.ArgumentParser()
parser.add_argument('--repo_name', type=str, default='d3rlpy', help='Repository name')
parser.add_argument('--v', type=int, default=7, help='hyper-parameter')
parser.add_argument('--d', type=int, default=3, help='depth')

root_path = config.root_path
args = parser.parse_args()
repo_name = args.repo_name


repo_args = utils.get_repo_args(args.repo_name)
mapping_path = os.path.join(config.workspace, args.repo_name, "output_testcase_mapping_valid.jsonl")
find_path = repo_args["find_path"]
repo_path = repo_args["repo_path"]
args.func_call_root_dir = os.path.join(config.workspace, args.repo_name, 'func_call_trees')

ids = set()
gen_ids = set()
with open(config.single_testcases_path, 'r', encoding='utf-8') as f:
    for line in f:
        # 每行是一个 JSON 对象，读取并解析
        data = json.loads(line)
        # 获取 'id' 并添加到集合中
        id_value = data.get('id')
        if id_value is not None and data.get("project") == args.repo_name and data.get("type") == "Development":
            ids.add(id_value)
            gen_ids.add(id_value)
with open(config.function_empty_testcases_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        id_value = data.get('id')
        if id_value is not None and data.get("project") == args.repo_name and data.get("type") == "Function_Empty":
            ids.add(id_value)

def find_function_code_ast(file_path, target):
    # 提取类名和函数名
    if "::" in target:
        class_name, function_name = target.split("::")
    else:
        class_name, function_name = None, target

    with open(file_path, 'r') as file:
        code = file.read()

        
    # 解析代码为AST
    tree = ast.parse(code)
    if class_name is None:
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                function_start_line = node.lineno
                function_end_line = node.end_lineno if hasattr(node, 'end_lineno') else None
                # 提取函数代码
                code_lines = code.splitlines()
                function_code = "\n".join(code_lines[function_start_line-1:function_end_line])
                return (1, len(code.splitlines())), (function_start_line, function_end_line), function_code
    else:
        # print(f'''find {class_name}::{function_name}''')
        # 遍历AST，寻找目标类和函数
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # 获取类的定义行范围
                class_start_line = node.lineno
                class_end_line = max(
                    (child.end_lineno if hasattr(child, 'end_lineno') else child.lineno)
                    for child in node.body
                ) if hasattr(node, 'body') and node.body else node.lineno

                # 提取类代码
                code_lines = code.splitlines()
                class_code = "\n".join(code_lines[class_start_line-1:class_end_line])

                # 遍历类的子节点，寻找函数定义
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == function_name:
                        # 获取函数的定义行范围
                        function_start_line = child.lineno
                        function_end_line = child.end_lineno if hasattr(child, 'end_lineno') else None
                        # 提取函数代码
                        function_code = "\n".join(code_lines[function_start_line-1:function_end_line])

                        return (class_start_line, class_end_line), (function_start_line, function_end_line), function_code

            # 如果找不到函数，返回整个类的起止行号，但函数信息为空
                return (class_start_line, class_end_line), None, f"未找到类 {class_name} 中的函数 {function_name}"

    # 如果找不到类，返回错误信息
        return None, None, f"未找到 {target}"

def func_problem(node, testcase_info, depth, count):
    if depth == args.d+1:
        return 0
    if node == None:
        return 0
    name = node["name"]
    path = node["source_dir"]
    origin_path = path
    func_file = ""
    prune = False
    prune_count = 0 # 我和我之下的id的个数
    # 递归处理孩子
    children = node["children"]
    id = None
    temp_dict = {}
    if path and "__init__" in path:
        return 0
    if path != None:
        path = os.path.join(repo_path, path)
        file_name = path.split('/')[-1].replace('.py', '')
        src_transformers_index = path.find(find_path)
        file_path = path[src_transformers_index + len(find_path):path.rfind('/')]

        if name.split(".")[-2] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-1]+".py"
        elif len(name.split(".")) >= 3 and name.split(".")[-3] == path.split("/")[-1].split(".")[0]:
            func_file = name.split(".")[-2] + "::" + name.split(".")[-1] + ".py"

        source_code_path = os.path.join(repo_path, file_path, f'{file_name}.py')
        temp = find_function_code_ast(source_code_path, func_file.replace(".py", ""))
        id = os.path.join(repo_name, file_path, file_name, func_file).replace(".py", "").replace("/", ".")
        if id in ids:
            prune = True
            
        
        if temp is None:
            return prune_count
            
        if temp is not None :
            class_lineno, func_lineno, func_code = temp            
            temp_dict = {
                'class_start_lineno': class_lineno[0] if class_lineno is not None else None,
                'class_end_lineno': class_lineno[1] if class_lineno is not None else None,
                'func_start_lineno': func_lineno[0] if func_lineno is not None else None,
                'func_end_lineno': func_lineno[1] if func_lineno is not None else None, 
                'func_code': func_code,
            }
            
            if func_lineno is None:
                temp_dict = {}
                    
    
    if prune == True:
        for child in children:
            prune_count = max(prune_count, func_problem(child, testcase_info, depth+1, count+1))
        prune_count += 1
    else: 
        for child in children:
            prune_count = max(prune_count, func_problem(child, testcase_info, depth+1, count))
    if prune_count == 0:
        return prune_count
    if prune_count + count > 1 and path != None:
        print(prune_count, count)
        if id in ids and id not in set(testcase_info["id"]) and len(testcase_info["id"]) < args.v:
            
            testcase_info["id"].append(os.path.join(repo_name, file_path, file_name, func_file).replace(".py", "").replace("/", "."))
            
        if name not in set(testcase_info["node"]):
            testcase_info["origin_file"].append(origin_path)
            testcase_info["prob_info"].append(temp_dict)
            testcase_info["node"].append(name)
            

    return prune_count

test_case_root_dir = os.path.join(root_path, 'testcases')



with open(mapping_path, 'r', encoding='utf-8') as file:
    testcase_infos = []
    testcase_test_file = []
    for line_num, line in tqdm(enumerate(file)):
        
        origin_data = json.loads(line.strip())
        test_file = origin_data.get("test_file", "")
        origin_file = origin_data.get("origin_file", "")
        test_path = test_file
        if test_path in testcase_test_file:
            continue
        file_name = origin_file.split('/')[-1].replace('.py', '')
        
        src_transformers_index = origin_file.find(find_path)
        file_path = origin_file[src_transformers_index + len(find_path):origin_file.rfind('/')]
        tree_path = os.path.join(args.func_call_root_dir, test_file.replace(".py", ""), "funcCallTree.json")    
        print(tree_path)    

        if not os.path.exists(tree_path):
            continue              
        with open(tree_path, "r") as tree_file:
            data = json.load(tree_file)
            
            testcase_info = {
                "id": [],
                "project": repo_name,
                "origin_file": [],
                "test_list":[test_path],
                "prob_info": [],
                "type": "",
                "node": [],
                "language": "Python"
            }
            testcase_test_file.append(test_path)
            func_problem(data, testcase_info, 0, 0)
            if len(testcase_info["id"]) > 1:
                testcase_info["type"] = "Development"
            testcase_info["pytest_info"] = {"total_num": origin_data["pytest"]["passed"]}
            
            flag = False
            if len(testcase_info["id"]) > 1:
                flag = True
                for pos in testcase_info["prob_info"]:
                    if pos == {}:
                        flag = False
            if flag:
                testcase_info["pytest_info"] = {"total_num": origin_data["pytest"]["passed"]}
                testcase_infos.append(testcase_info)
                
    
    with open (os.path.join(root_path, 'testcases', 'multi_Development_raw.jsonl' ), "a") as save_file:
        for testcase_info in testcase_infos:
            json_line = json.dumps(testcase_info, ensure_ascii=False)
            save_file.write(json_line + "\n")
    

