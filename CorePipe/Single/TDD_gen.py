import json
import ast
import textwrap
import re
import os
import CorePipe.utils as utils
import argparse
import shutil
import subprocess
import CorePipe.config as config
import tempfile

LINE_NUM_LIMIT = 50
LINE_NUM_MIN = 4

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo_name', type=str, default='', help='name of repo')
    args = parser.parse_args()
    repo_name = args.repo_name
    args.output_dir = os.path.join(config.workspace, args.repo_name)
    args.func_call_root_dir = os.path.join(args.output_dir, 'func_call_trees')
    args.repo_args = utils.get_repo_args(args.repo_name)
    args.repo_path = args.repo_args["repo_path"]
    return args


def find_function_code_ast(file_path, class_name, function_name):
    with open(file_path, 'r') as file:
        code = file.read()
   
    # 解析代码为AST
    tree = ast.parse(code)
    if class_name is None or class_name == '':

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                function_start_line = node.lineno
                function_end_line = node.end_lineno if hasattr(node, 'end_lineno') else None
                # 提取函数代码
                code_lines = code.splitlines()
                function_code = "\n".join(code_lines[function_start_line-1:function_end_line])
                return (1, len(code.splitlines())), (function_start_line, function_end_line), function_code
    else:
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
        return None, None, f"未找到 {class_name} 中的函数 {function_name}"

def generate_code_blocks_dict(func_name, code):
    """
    分析 Python 代码块并生成字典，key 为 '#startlineno#endlineno' 的格式，
    value 为包含行号、节点类型和代码片段的字典。
    """
    # 解析代码为 AST
    
    code = textwrap.dedent(code)
    tree = ast.parse(code)

    # 结果字典
    blocks_dict = {}

    def analyze_block(node, code_lines):
        """
        递归分析一个节点，生成字典项。
        """
        start_line = getattr(node, 'lineno', None)  # 起始行号
        end_line = getattr(node, 'end_lineno', None)  # 结束行号
        block_type = type(node).__name__  # 节点类型
        # print(block_type, start_line, end_line)
        # 函数头的部分不保存
        if block_type == 'arg':
            return
        # 如果节点有行号信息，提取代码片段
        
        if start_line and end_line:
            block_code = "\n".join(code_lines[start_line - 1:end_line])
            # 构造 key
            key = f"{func_name}#{start_line}#{end_line}"
            # 存储 block 信息
            blocks_dict[key] = {
                "block_type": block_type,
                "start_line": start_line,
                "end_line": end_line,
                "code": block_code,
            }
        # 递归分析子节点
        
        for child in ast.iter_child_nodes(node):
            analyze_block(child, code_lines)

    # 分析整棵 AST 树
    code_lines = code.splitlines()
    analyze_block(tree, code_lines)
    return blocks_dict

def find_key_block(func, code, recur = None):
    if recur:
        chat_message = f'''关键代码块定义为：实现函数主要功能的代码部分，直接决定函数是否能完成预期目标；执行效率显著影响函数性能的代码部分。
请你根据函数{func}的代码，找到block {recur}中的关键代码块，输出其子关键代码块的block_id。要求选出来的代码块总行数不超过60行，所以请谨慎选择，确保选择的是最为重要的部分。
输出格式：
你可以选择多个**连续**的block，这时请输出block_id的列表：
```python 
blocks = ["blockid1", "blockid2", ...]
```
如果实现的函数比较简单，仅仅包含初始化或者返回值，则说明该函数不存在关键代码块，这时请输出
```python 
blocks = None
```
请不要在代码段中输出额外的注释说明，只输出blockid。
    请在{recur}代码块的子代码块中选择关键代码块。
    函数代码：
    {code['func_code']}
    函数block信息：
    {code['block_info']}
    '''
    else:
        chat_message = f'''关键代码块定义为：实现函数主要功能的代码部分，直接决定函数是否能完成预期目标；执行效率显著影响函数性能的代码部分。
请你根据函数{func}的代码，找到其实现过程中的关键代码块，输出关键block的block_id。要求选出来的代码块总行数不超过60行，所以请谨慎选择，确保选择的是最为重要的部分。
输出格式：
你可以选择多个**连续**的block，这时请输出block_id的列表：
```python 
blocks = ["blockid1", "blockid2", ...]
```
如果实现的函数比较简单，仅仅包含初始化或者返回值，则说明该函数不存在关键代码块，这时请输出
```python 
blocks = None
```
请不要在代码段中输出额外的注释说明，只输出blockid。
函数代码：
{code['func_code']}
函数block信息：
{code['block_info']}
    '''
    chosen_block = utils.get_response(chat_message, model='gpt4o')
    if 'None' in  chosen_block:
       return 1e9, 0, None

    match = re.search(r'blocks\s*=\s*\[(.*?)\]', chosen_block, re.S)
    if match:
        block_content= match.group(1).strip()
    else:
        # print(chosen_block)
        print(f'函数{func}选择失败')
        return 1e9, 0, None

    blocks = block_content.split(',')
    block_list = []
    for block in blocks:
        block_list.append(block.strip().strip('"').strip())
    
    
    start_line_no = 1e9
    end_line_no = 0
    if block_list is None:
        return 1e9, 0, None
    
    for block in block_list:
        try:
            start_line, endline = code['block_info'][block]['start_line'], code['block_info'][block]['end_line']
            if max(endline, end_line_no) - min(start_line, start_line_no) > LINE_NUM_LIMIT:
                continue
            start_line_no = min(start_line, start_line_no)
            end_line_no = max(endline, end_line_no)
                 
        except Exception as e:
            print('ERROR', e)
            continue
    
    if start_line_no == 1e9 or end_line_no == 0:
        # 说明没有找到合适的block
        return find_key_block(func, code, recur = block_list)
    
    start_line_no = 2 if start_line_no == 1 else start_line_no # 保证函数头至少保留一行
    return start_line_no, end_line_no, block_list

def generate_new_code(func, code, class_code, class_start_lineno, start_line_no, end_line_no, model, score_model='claude3.5'):
    lines = code['func_code'].splitlines()
    import_code = code['import_code']
    # print('FUNC:', func)
    if start_line_no < 1 or end_line_no > len(lines) or start_line_no > end_line_no:
        raise ValueError("Invalid line range specified.")
    res = lines[:start_line_no-1] + ['<complete code here>']+ lines[end_line_no:]

    return "\n".join(res), scores




def extract_third_level_content(args, json_path, mapping, TDD_results_path, temp_copy_path):
    with open(json_path, 'r') as file:
        tree_data = json.load(file)

    third_level_content = []
    seen_names = set() 
    for child in tree_data.get('children', []):
        for sub_child in child.get('children', []):
            name = sub_child.get("name")
            source_dir = sub_child.get("source_dir")
            whole_source_dir = os.path.join(args.repo_args['repo_path'], source_dir)
            if name not in seen_names and mapping['origin_file'] == os.path.relpath(whole_source_dir, args.repo_args['repo_running_path']):
                seen_names.add(name)
                # name = module_name.class_name.func_name or module_name.func_name
                module_name = mapping['origin_file'].replace('/', '.').replace('.py', '')
                func_name = name.split('.')[-1]
                class_name = name.replace(module_name + '.','').replace(func_name, '').replace('.','')
                # (class_start_line, class_end_line), (function_start_line, function_end_line), function_code
                class_info, function_info, function_code = find_function_code_ast(whole_source_dir, class_name, func_name)
                
                if function_info is None:
                    print(f'函数{func_name}在{whole_source_dir}中不存在')
                    continue


                test_file = mapping['test_file']
                origin_file = mapping['origin_file']
            
                code = {
                    "name": name,
                    "func_name": func_name,
                    "source_dir": sub_child.get("source_dir"),
                    'class_start_lineno': class_info[0],
                    'class_end_lineno': class_info[1],
                    'func_start_lineno': function_info[0],
                    'func_end_lineno': function_info[1],
                    'func_code': function_code,
                    'block_info': generate_code_blocks_dict(func_name, function_code),
                }
                start_line_no, end_line_no, block_list= find_key_block(func_name, code)
                if start_line_no == 1e9 or end_line_no == 0 or start_line_no >= end_line_no or end_line_no - start_line_no < LINE_NUM_MIN:
                    continue

                lines = code['func_code'].splitlines()
                prefix = lines[:start_line_no-1]
                suffix = lines[end_line_no:]
                placeholder = ['<complete code here>']
                new_code = '\n'.join(prefix + placeholder + suffix)

                # if new_code is None or scores is None:
                if new_code is None:
                    continue

                LLM_Score = {"readability_score": "", "accuracy_score": "", "completeness_score": ""}

                testcase = {
                    "id": name,
                    "project": args.repo_name,
                    "func": func_name,
                    "origin_file":origin_file,
                    "test_list":[test_file],
                    "prob_info": {
                        "func_start_lineno": function_info[0], 
                        "func_end_lineno": function_info[1], 
                        "key_block_start_lineno": start_line_no+function_info[0]-1, 
                        "key_block_end_lineno": end_line_no+function_info[0]-1, 
                        "new_func_code": new_code
                    },
                    "pytest_info": {
                        "total_num": mapping["pytest"]["passed"], 
                        # "base_passed_num": base_passed unknown before retest
                    }, 
                    "score": {"readability_score": "null", "accuracy_score": "null", "completeness_score": "null"},
                    "LLM_score": {},
                    "type": "TDD", 
                    "language": "Python", 
                    "gen_model": "", 
                    "is_difficult": ""
                }
                
                from CorePipe.Single.dev_retest import retest_code
                file_path = os.path.dirname(origin_file)
                file_name = origin_file.split('/')[-1].replace('.py', '')
                log_file = os.path.join(args.output_dir, 'testcases', args.repo_name, file_path, file_name, 'log.txt')
                if os.path.exists(os.path.dirname(log_file)):
                    os.makedirs(os.path.dirname(log_file), exist_ok=True)
                retest_res, passed = retest_code(args, testcase, file_path, file_name, test_file, log_file)
                if retest_res:
                    testcase['pytest_info']['base_passed_num'] = passed
                    with open(TDD_results_path, 'a') as output:
                        output.write(json.dumps(testcase, ensure_ascii=False) + '\n')

if __name__ == "__main__":
    args = parse_args()
    mapping_jsonl_path =  os.path.join(config.workspace, args.repo_name, "output_testcase_mapping_valid.jsonl")
    func_call_root_dir = os.path.join(args.output_dir, 'func_call_trees')
    output_file = os.path.join(config.testcases_path, args.repo_name,'single','TDD.jsonl')
    # copy temp test file
    temp_dir = os.path.join(config.root_path, 'tmp_source')
    os.makedirs(temp_dir, exist_ok=True)
    temp_copy_path = tempfile.mkdtemp(prefix=f'GEN_TDD_{args.repo_name}_', dir=temp_dir)
    shutil.copytree(args.repo_path, temp_copy_path, dirs_exist_ok=True)
    if not temp_copy_path.endswith(os.sep):
        temp_copy_path += os.sep
    args.tmp_repo_path = temp_copy_path
    
    if os.path.exists(output_file):
        os.remove(output_file)
    with open(mapping_jsonl_path, 'r') as f:
        for line in f.readlines():
            mapping = json.loads(line)
            origin_file = mapping['origin_file']
            origin_file_name = origin_file.split('/')[-1]
            test_file = mapping['test_file']
            tree_path = os.path.join(args.func_call_root_dir, test_file.replace(".py", ""),"funcCallTree.json")
            extract_third_level_content(args,tree_path, mapping, output_file, temp_copy_path)
    
