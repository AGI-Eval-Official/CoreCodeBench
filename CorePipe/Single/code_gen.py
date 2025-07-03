# -*- coding: utf-8 -*-
import re
import ast
import textwrap
import json
import os
import argparse
from CorePipe.Single.variable_tracker import extract_lvalues_and_rvalues, extract_lvalues_new
import CorePipe.utils as utils
import argparse
import sys
import shutil
import CorePipe.config as config
import logging

def get_eval_function_list(origin_code, test_code, model):
    chat_message=f'''请你分析目标代码，对于其中的重要函数进行筛选。输出一个python list，每一项是一个字符，写成类名::函数名的形式，如果不属于任何类，则只写函数名即可。
输出样例：
```python
['class1::func1', 'class2::func2', 'func3']
```
目标代码：
{origin_code}
    '''
    test_function_list_text = utils.get_response(chat_message, model=model)

    match = re.search(r'```python(.*?)```', test_function_list_text, re.S)
    if match:
        test_function_list_code = match.group(1).strip()
    else:
        test_function_list_code = test_function_list_text.strip()
    try:
        test_function_list = eval(test_function_list_code)
        if not isinstance(test_function_list, list):
            raise ValueError("The output is not a list")
    except Exception as e:
        print(test_function_list)
        print("Error in parsing the list", e)
        return get_eval_function_list(origin_code, test_code, model)
    return test_function_list

def find_function_code_ast(file_path, target):
    if "::" in target:
        class_name, function_name = target.split("::")
    else:
        class_name, function_name = None, target

    with open(file_path, 'r') as file:
        code = file.read()

    tree = ast.parse(code)
    if class_name is None:
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                function_start_line = node.lineno
                function_end_line = node.end_lineno if hasattr(node, 'end_lineno') else None
                code_lines = code.splitlines()
                function_code = "\n".join(code_lines[function_start_line-1:function_end_line])
                return (1, len(code.splitlines())), (function_start_line, function_end_line), function_code
    else:
        logging.info(f'''find {class_name}::{function_name}''')
        # Traverse the AST to find the target class and function
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Get the definition line range of the class
                class_start_line = node.lineno
                class_end_line = max(
                    (child.end_lineno if hasattr(child, 'end_lineno') else child.lineno)
                    for child in node.body
                ) if hasattr(node, 'body') and node.body else node.lineno

                # Extract the class code
                code_lines = code.splitlines()
                class_code = "\n".join(code_lines[class_start_line-1:class_end_line])

                # Traverse the child nodes of the class to find the function definition
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == function_name:
                        # Get the definition line range of the function
                        function_start_line = child.lineno
                        function_end_line = child.end_lineno if hasattr(child, 'end_lineno') else None
                        # Extract the function code
                        function_code = "\n".join(code_lines[function_start_line-1:function_end_line])

                        return (class_start_line, class_end_line), (function_start_line, function_end_line), function_code

            # If the function is not found, return the start and end line of the class, but the function information is empty
                return (class_start_line, class_end_line), None, f"The function {function_name} in the class {class_name} is not found"

    # If the class is not found, return the error information
        return None, None, f"The class {target} is not found"

def generate_code_blocks_dict(func_name, code):
    """
    Analyze Python code blocks and generate a dictionary, with the key in the format '#startlineno#endlineno',
    and the value being a dictionary containing line number, node type, and code snippet.
    """
    code = textwrap.dedent(code)
    tree = ast.parse(code)
    blocks_dict = {}

    def analyze_block(node, code_lines):
        """
        Recursively analyze a node and generate a dictionary item.
        """
        start_line = getattr(node, 'lineno', None) 
        end_line = getattr(node, 'end_lineno', None) 
        block_type = type(node).__name__

        if block_type == 'arg':
            return

        if start_line and end_line:
            block_code = "\n".join(code_lines[start_line - 1:end_line])

            key = f"{func_name}#{start_line}#{end_line}"

            blocks_dict[key] = {
                "block_type": block_type,
                "start_line": start_line,
                "end_line": end_line,
                "code": block_code,
            }

        
        for child in ast.iter_child_nodes(node):
            analyze_block(child, code_lines)

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
        print(chosen_block)
        print(f'Failed to select the function {func}')
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
            if max(endline, end_line_no) - min(start_line, start_line_no) > config.LINE_NUM_LIMIT:
                continue
            start_line_no = min(start_line, start_line_no)
            end_line_no = max(endline, end_line_no)
                 
        except Exception as e:
            print('ERROR', e)
            continue
    
    if start_line_no == 1e9 or end_line_no == 0:
        # The block is not found
        return find_key_block(func, code, recur = block_list)
    
    start_line_no = 2 if start_line_no == 1 else start_line_no # Ensure the function header至少保留一行
    logging.info(f'''The keyblocks of function {func} are {blocks}, and the selected line numbers are [{start_line_no},{end_line_no}]''')
    return start_line_no, end_line_no, block_list

def generate_new_code(args, test_file, origin_file, func, code, class_code, class_start_lineno, start_line_no, end_line_no, model, validate_model):
    lines = code['func_code'].splitlines()
    import_code = code['import_code']
    if start_line_no < 1 or end_line_no > len(lines) or start_line_no > end_line_no:
        raise ValueError("Invalid line range specified.")
    res = lines[:start_line_no-1] + ['<complete code here>']+ lines[end_line_no:]

    key_block = '\n'.join(lines[start_line_no-1:end_line_no])
    if not utils.is_core_code(key_block, validate_model):
        return None, None
    lhs_var, rhs_var = extract_lvalues_and_rvalues(key_block, '\n'.join(lines[end_line_no:]))
    print(f'lhs_var:{lhs_var}, rhs_var:{rhs_var}')
    lhs_var_2 = extract_lvalues_new(test_file, origin_file, class_start_lineno+start_line_no-1, class_start_lineno+end_line_no-1, args)
    print(f'lhs_var_2:{lhs_var_2}')
    lhs_var = list(set(lhs_var).union(set(lhs_var_2)))
    print(f'LHS:{lhs_var}, RHS: {rhs_var}')
    if lhs_var is None or rhs_var is None:
        return None, None
    variable_list = list(set(lhs_var).intersection(set(rhs_var)))
    variable_list = []

    chat_message = f'''请结合上下文，分析给出的代码块，并以简洁的语言，按照给定的格式输出其功能（不要输出额外的内容）：
1. **目的**
    描述代码块的主要目标和它在整个程序中的作用。特别是其在当前函数中的职责是什么。
2. **逻辑**
    详细阐述代码块的核心逻辑和操作过程。对于所有的条件分支(if语句），需逐一解释。
    如果涉及复杂的变量更新，请使用Markdown格式的公式来表示这些数学计算。
    如果用到了代码块前文的变量，请尽量使用变量名来描述，并用反引号将变量名框出。用到的函数请用反引号将其框出，可以用```函数名(参数)```的形式，或者```函数名```的形式，请不要出现```函数名()```等会引起歧义的形式。
3. **异常**
    如果待分析的代码块中抛出异常，请说明其抛出的异常情况及异常类型。如果代码块中无异常抛出，则此项写“无”。
4. **变量赋值**
    根据给出的变量列表，用列表形式给出代码块中计算该变量的具体意义和作用。
    如果表格中有识别错误的变量（例如后文没有用到），你可以直接删去该变量。如果变量列表中漏掉了某个被修改的变量（特别是`self.blockid_list.append(block)`这样的形式）请在列表中补充。
    变量列表：{variable_list}

    
### 示例输出：
1. **目的**
    解析目标字符串，提取其中的关键信息。目标字符串的格式为``` blocks = ["blockid1", "blockid2", ...]```，此代码块提取所有有效的blockid，生成一个新的字符串列表。
2. **逻辑**
    使用正则表达式(re库)从目标字符串中提取blockid列表，随后遍历该列表，验证每个blockid是否在数据库中存在，并将其转换成整数类型后存入新列表。
3. **异常**
    - `ValueError`： 如果目标字符串的格式不正确，无法提取有效的blockid列表，则抛出该异常。
4. **变量赋值**
    - `self.blockid_list`：存储提取并验证后的blockid  

### 待分析的代码块:
```
{key_block}
```
### 代码块的上下文信息：
```
{class_code}
```
    '''
    explanation = utils.get_response(chat_message, model)
    scores, response = utils.validate_code(explanation, key_block, model=validate_model)
    
    if sum(scores) == 0:
        return None, None
    if sum(scores) < 6:
        modify_prompt = f'''
代码审查员认为生成的代码解释存在以下问题：
```
{response}
```
请根据代码块的内容和审查员的建议，修改当前的代码解释，并按照规定格式输出，**不要输出额外的内容**。
### 待分析的代码块:
```
{key_block}
```
### 当前的代码解释：
{explanation}

### 输出要求：
1. **目的**
    描述代码块的主要目标和它在整个程序中的作用。特别是其在当前函数中的职责是什么。
2. **逻辑**
    详细阐述代码块的核心逻辑和操作过程。对于所有的条件分支(if语句），需逐一解释。
    如果涉及复杂的变量更新，请使用Markdown格式的公式来表示这些数学计算。
    如果用到了代码块前文的变量，请尽量使用变量名来描述，并用反引号将变量名框出。
3. **异常**
    如果待分析的代码块中抛出异常（`raise`语句，不包括`except`语句），请说明其抛出的异常情况及异常类型。如果代码块中无异常抛出，则此项写“无”。
4. **变量赋值**
    根据给出的变量列表，用列表形式给出代码块中计算该变量的具体意义和作用。
    如果有识别错误的变量（例如后文没有用到），你可以直接删去该变量。如果变量列表中漏掉了某个被修改的变量（特别是`self.blockid_list.append(block)`这样的形式）请在列表中补充。


### 示例输出：
1. **目的**
    解析目标字符串，提取其中的关键信息。目标字符串的格式为``` blocks = ["blockid1", "blockid2", ...]```，此代码块提取所有有效的blockid，生成一个新的字符串列表。
2. **逻辑**
    使用正则表达式(re库)从目标字符串中提取blockid列表，随后遍历该列表，验证每个blockid是否在数据库中存在，并将其转换成整数类型后存入新列表。
3. **异常**
    - `ValueError`： 如果目标字符串的格式不正确，无法提取有效的blockid列表，则抛出该异常。
4. **变量赋值**
    - `self.blockid_list`：存储提取并验证后的blockid  

    '''
        new_explanation = utils.get_response(modify_prompt, model)
        scores_new, _ = utils.validate_code(new_explanation, key_block)
    
        explanation = new_explanation if sum(scores_new) > sum(scores) else explanation
        scores = scores_new if sum(scores_new) > sum(scores) else scores
    
    if sum(scores) < 5 or 0 in scores:
        print(f"The generated code explanation still does not meet the requirements, so it is not possible to generate a test case ID for {func}")
        return None, None
    res = lines[:start_line_no-1] + ["# 本段代码的功能解释："] + ['#'+ e for e in explanation.splitlines()] + ['<complete code here>']+ lines[end_line_no:]
    return "\n".join(res), scores

def get_import_code(whole_file):
    lines = whole_file.splitlines()
    import_code = []
    for line in lines:
        if line.startswith('import') or line.startswith('from'):
            import_code.append(line)
    return '\n'.join(import_code)

def gen_comment(args, repo_name, file_path, file_name, test_path, pytest_info, model, validate_model, testcases_info_path):
    source_code_path = os.path.join(args.repo_running_path, file_path, f'{file_name}.py')

    with open(source_code_path, 'r') as file:
        whole_file = file.read()
    function_list = get_eval_function_list_calltree(args, test_path, model)
    code_dict = {}
    for func in function_list:
        func_info = find_function_code_ast(source_code_path, func)
        if func_info is None:
            continue
        class_lineno, func_lineno, func_code = func_info
        if class_lineno is None or func_lineno is None:
            continue
        import_code = get_import_code(whole_file)
        
        code_dict[func] = {
                'class_start_lineno': class_lineno[0],
                'class_end_lineno': class_lineno[1],
                'func_start_lineno': func_lineno[0],
                'func_end_lineno': func_lineno[1],
                'func_code': func_code,
                'block_info': generate_code_blocks_dict(func, func_code),
                'import_code': import_code
        }

    
    with open(testcases_info_path, 'w', encoding='utf-8') as file:
        for func, code in code_dict.items():
            start_line_no, end_line_no, block_list= find_key_block(func, code)
            if start_line_no == 1e9 or end_line_no == 0 or start_line_no >= end_line_no or end_line_no - start_line_no < config.LINE_NUM_MIN:
                continue
            
            class_code = '\n'.join(whole_file.splitlines()[code['class_start_lineno']-1:code['class_end_lineno']])
            new_code, scores = generate_new_code(args, test_path, source_code_path, func,code, class_code, code['func_start_lineno'], start_line_no, end_line_no, model, validate_model)
            if new_code is None or scores is None:
                continue

            LLM_Score = {"readability_score": scores[0], "accuracy_score": scores[1], "completeness_score": scores[2]}

            testid = '.'.join([repo_name]+ file_path.strip('/').split('/') + [file_name, func])
            print(f'testid:{testid} is generated!')
            print(testcases_info_path)
            json_str = json.dumps({
                'id':testid, 
                 'project': repo_name,
                 'func': func, 
                 'origin_file':os.path.join( file_path, f'{file_name}.py'),
                 'test_list':[test_path],
                 'prob_info':{
                     'func_start_lineno': code['func_start_lineno'],
                     'func_end_lineno': code['func_end_lineno'],
                     'key_block_start_lineno': start_line_no+code['func_start_lineno']-1,
                     'key_block_end_lineno': end_line_no+code['func_start_lineno']-1,
                     'new_func_code': new_code,
                     'gen_model': model
                 },
                 "pytest_info":{'total_num': pytest_info['passed']},
                 "type":'Development',
                 'language':'Python',
                 'LLM_Score':LLM_Score,
                 'model_info':{'gen_model':model, 'rewrite_model':"", "debug_gen_model":""}
                }, ensure_ascii=False) + '\n'
            print(json_str)
            file.write(json_str)

def extract_names_and_sources(node,func_name):
    """Recursively extract name and source_dir from each node. 
    Do not add if the name already exists."""
    names_and_sources = {}

    def process_node(node):
        if node is None:
            return
        if "name" in node and "source_dir" in node:
            if node["name"] not in names_and_sources and node["source_dir"]:
                if func_name in node["source_dir"]:
                    names_and_sources[node["name"]] = node["source_dir"]
        if "children" in node:
            for child in node["children"]:
                process_node(child)
    
    process_node(node)
    return names_and_sources

def get_eval_function_list_calltree(args, test_path, model):
    funcCalltree_path = args.func_call_root_dir = os.path.join(args.output_dir, 'func_call_trees', test_path.replace(".py",""), "funcCallTree.json" )
    with open(funcCalltree_path, 'r') as file:
        json_data = json.load(file)
    func = test_path.split('/')[-1]
    match = re.search(r'test_(.*?)\.py', func)
    if match:
        file_name = match.group(1)
    
    result = extract_names_and_sources(json_data, file_name)

    new_result = {}
    test_function_list = []
    for name, source_dir in result.items():
        last_slash_index = source_dir.rfind('/')
        py_index = source_dir.find('.py')
        if last_slash_index != -1 and py_index != -1:
            node_source = source_dir[last_slash_index + 1:py_index]

        start_index = name.find(node_source)
        remaining_part = name[start_index + len(node_source):]
        dot_count = remaining_part.count('.')
        if dot_count == 1:
            node_name = remaining_part.split('.')[-1]
        elif dot_count > 1:
            parts = remaining_part.rsplit('.', 2)
            node_name = parts[-2] + '::' + parts[-1]
        test_function_list.append(node_name)
        new_result[node_name] = node_source

    return test_function_list


if __name__ == '__main__':
    # default_repo_name = 'transformers'
    # repo_args = utils.get_repo_args(default_repo_name)
    # root_path = repo_args["root_path"]

    # source_code_path = root_path + "Source_Copy/skfolio/src/skfolio/cluster/_hierarchical.py"
    # test_path = root_path + "Source_Copy/skfolio/tests/test_cluster/test_hierarchical.py"
    # with open(source_code_path, 'r') as file:
    #     origin_code = file.read()
    # with open(test_path, 'r') as file:
    #     test_code = file.read()

