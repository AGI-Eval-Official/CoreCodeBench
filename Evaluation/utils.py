 # -*- coding: utf-8 -*-
import os
import csv
import re
import pandas as pd
import xlsxwriter
import json
import ast
from tqdm import tqdm
import time
import config
import sys

def get_repo_args(repo_name):
    repo_info_path = config.repo_info_path

    with open(repo_info_path, 'r') as file:
        repo_info = json.load(file)

    repo_data = repo_info[repo_name]
    import_name = repo_data.get('import_name', '')
    repo_name_real = repo_data.get('repo_name', '')
    repo_path = os.path.join(config.root_path, repo_data.get('repo_path', ''))
    running_path_relative = repo_data.get('_running_path', '').lstrip('/')
    src_path_relative = repo_data.get('_src_path', '').lstrip('/')
    test_path_relative = repo_data.get('_test_path', '').lstrip('/')
    repo_running_path = os.path.join(repo_path, running_path_relative)
    src_path = os.path.join(repo_path, src_path_relative)
    test_path = os.path.join(repo_path, test_path_relative)

    repo = {
        "repo_name_real": repo_name_real,
        "import_name": import_name,
        "find_path": f"Source_Copy/{repo_name_real}/",
        "repo_path": repo_path, #source_copy
        "repo_running_path": repo_running_path,
        "relative_running_path": running_path_relative,
        "relative_test_path": test_path_relative,
        "src_path": src_path,
        "test_path": test_path
    }
    return repo


def extract_code(content):
    """
    Extract code from a string that is wrapped in ``` or ```python ```.

    Args:
        content (str): The input string containing code blocks.

    Returns:
        str: The extracted code without the enclosing backticks or language identifiers.
    """
    import re

    # Match the code block with or without the "python" identifier
    pattern = r"```(?:python\s)?([\s\S]*?)```"

    # Search for code blocks and extract the content inside
    match = re.search(pattern, content)
    if match:
        return match.group(1)  # Extract and return the code inside the backticks
    else:
        pattern = r"```([\s\S]*?)```"
        match = re.search(pattern, content)
        if match:
            return match.group(1)
        else:
            return content  # If no code block, return the original string stripped of whitespace

def extract_code_loose(content):
    """
    Extract code from a string that is wrapped in ``` or ```python ```.

    Args:
        content (str): The input string containing code blocks.

    Returns:
        str: The extracted code without the enclosing backticks or language identifiers.
    """
    import re

    # Match the code block with or without the "python" identifier
    pattern = r"```(?:python\s)?([\s\S]*?)```"

    # Search for code blocks and extract the content inside
    match = re.search(pattern, content)
    if match:
        return match.group(1)  # Extract and return the code inside the backticks
    else:
        pattern = r"```([\s\S]*?)```"
        match = re.search(pattern, content)
        if match:
            return match.group(1)
        elif "```python" in content:
        # 找到最后一个未闭合的 ``` 位置
            last_opener = content.rfind("```") + 10  # 跳过开头的 ```python\n
            return content[last_opener:]
        elif "```" in content:
        # 找到最后一个未闭合的 ``` 位置
            last_opener = content.rfind("```") + 4  # 跳过开头的 ```\n
            return content[last_opener:]
        else:
            return content  # If no code block, return the original string stripped of whitespace

def get_response(chat_message, model, gen_kwargs=None):
    from openai import OpenAI
    client = OpenAI(api_key="sk-2134105ebd374660963d161470cee3d4", base_url="https://api.deepseek.com/v1")


    if model == 'empty':
        return ''
    elif model == 'deepseek-chat':
        gen_kwargs = {'max_length': 8000, 'temperature': 0.0, 'top_p': 0.01, 'stream': False}
        raw_response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": chat_message}],
                max_tokens=gen_kwargs['max_length'],
                temperature=gen_kwargs['temperature'],
                top_p=gen_kwargs['top_p'],
                stream=False
        )
        return raw_response.choices[0].message.content
    elif model == 'llama3.1-70b-instruct':
        gen_kwargs = gen_kwargs = {'temperature': 0.0, 'top_k': 1, 'top_p': 0.0, 'do_sample': False, 'max_length': 8000}
        customize_inference_ip = '10.166.89.66'
        import requests
        import json
        import time

        class LocalClient():
            def __init__(self):
                pass
            def generate(self, ip, prompt, wait=False, **gen_kwargs):
                url = f"http://{ip}:8080"
                data = {
                    "prompt": prompt,
                    "max_new_tokens": gen_kwargs["max_length"],
                    "do_sample": gen_kwargs["do_sample"],
                }
                if gen_kwargs["do_sample"]:
                    if "temperature" in gen_kwargs:
                        data["temperature"] = gen_kwargs["temperature"]
                    if "top_k" in gen_kwargs:
                        data["top_k"] = gen_kwargs["top_k"]
                    if "top_p" in gen_kwargs:
                        data["top_p"] = gen_kwargs["top_p"]
                payload = json.dumps(data)
                headers = {
                    'Content-Type': 'application/json'
                }
                cnt = 0
                total = 1
                if wait:
                    total = 20
                while True:
                    try:
                        response = requests.request("POST", url, headers=headers, data=payload)
                        response = response.json()
                        if "completions" in response and response["completions"] is not None:
                            return response["completions"]
                        else:
                            return response["result"]
                    except Exception as e:
                        print(e)
                        cnt = cnt + 1
                        if cnt < total:
                            print(f"服务器ip: {ip}未返回结果或异常，若这是第一条请求，可能是服务还没启动成功.等待10秒后重试... 已重试次数:{cnt}/{total}", flush=True)
                            time.sleep(10)  # 等待5秒
                            continue
                        raise e
        raw_response = LocalClient().generate(customize_inference_ip, chat_message, wait=True, **gen_kwargs)
        return raw_response[0]["text"]
        
    else:
        gen_kwargs = {'max_length': 8000, 'temperature': 0.0, 'top_p': 0.00, 'stream': False}
        raw_response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": chat_message}],
                max_tokens=gen_kwargs['max_length'],
                temperature=gen_kwargs['temperature'],
                top_p=gen_kwargs['top_p'],
                stream=False
        )
        return raw_response.choices[0].message.content
        
   

def get_file_content(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def load_jsonl_to_list(file, key_value=None):
    res = []
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                if key_value is None:
                    res.append(json.loads(line.strip()))
                else:
                    line_json = json.loads(line.strip())
                    if line_json[key_value[0]] == key_value[1]:
                        res.append(json.loads(line.strip()))
            except Exception as e:
                print('Error loading JSON to list: ', line)
                print('File:', file)
                print(e)
                sys.exit()
    return res

def load_jsonl_to_set(file, pre_key):
    set_data = set()
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                key = json.loads(line.strip())[pre_key]
                set_data.add(key)
            except Exception as e:
                print('Error  loading JSON to set: ', e)
                sys.exit()
    return set_data


def load_jsonl_to_dict(file, pre_key):
    data_dict = {}
    try:
        with open(file, 'r', encoding='utf-8') as f:
            for line in f:
                # 解析每一行JSON
                json_obj = json.loads(line.strip())
                # 这里假设每个json对象都有一个唯一的 'id' 字段作为键
                key = json_obj.get(pre_key)
                if key is not None:
                    data_dict[key] = json_obj
                else:
                    raise ValueError("JSON object does not contain 'id' field: {}".format(json_obj))
    except FileNotFoundError:
        print(f"The file {file} does not exist.")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

    return data_dict

def align_indent(completed_code_line_list, standard_code_line_list, prefix, suffix):
    # 对齐completed code和标准答案standard_code_line的第一个非空行
    standard_indent = None
    for line in standard_code_line_list:
        if line.strip():  # 忽略空行
            standard_indent = len(line) - len(line.lstrip())
            break

    # 找到完成代码中的第一个非空行及其缩进
    completed_indent = None
    for line in completed_code_line_list:
        if line.strip():  # 忽略空行
            completed_indent = len(line) - len(line.lstrip())
            break
        
        # 计算需要增加的缩进
    if completed_indent is None or standard_indent is None:
        return completed_code_line_list
    additional_indent = standard_indent - completed_indent
    
    adjusted_code_list = [' '* additional_indent + i for i in completed_code_line_list] if additional_indent > 0 else completed_code_line_list
    # 检查是否符合语法
    full_code = '\n'.join(prefix + adjusted_code_list + suffix)
    try:
        ast.parse(full_code)
        return adjusted_code_list
    except SyntaxError as e:
        # 不符合语法，换第二种情况
        min_indent_com = min([len(i) - len(i.lstrip()) for i in completed_code_line_list])
        min_indent_stan = min([len(i) - len(i.lstrip()) for i in standard_code_line_list])
        min_indent = min(min_indent_com, min_indent_stan)
        adjusted_code_list = [' '* additional_indent + i for i in completed_code_line_list] if min_indent > 0 else completed_code_line_list
        # 再次检查语法
        full_code = '\n'.join(prefix + adjusted_code_list + suffix)
        try:
            ast.parse(full_code)
            return adjusted_code_list
        except SyntaxError as e:
            return completed_code_line_list

            
def read_log(log_path):
    """
    读取日志文件并解析其中的测试结果。

    该函数从指定路径读取日志文件内容，解析其中的测试通过、跳过、失败和警告的数量，并返回这些统计结果。

    Args:
        log_path (str): 日志文件的路径。

    Returns:
        tuple: 包含以下四个元素的元组：
            - int: 测试通过的数量（包括警告数量）。
            - int: 测试跳过的数量。
            - int: 测试失败的数量。
    """
    with open(log_path, 'r', encoding='utf-8') as file:
        log = file.read()
    if log == "":
        return 0, 0, 0
    print(log)
    passed_pattern = r'(\d+) passed'
    xpassed_pattern = r'(\d+) xpassed'
    skipped_pattern = r'(\d+) skipped'
    failed_pattern = r'(\d+) failed'
    xfailed_pattern = r'(\d+) xfailed'
    warning_pattern = r'(\d+) warnings?'
    
    # 搜索匹配
    passed_match = re.search(passed_pattern, log)
    xpassed_match = re.search(xpassed_pattern, log)
    skipped_match = re.search(skipped_pattern, log)
    failed_match = re.search(failed_pattern, log)
    xfailed_match = re.search(xfailed_pattern, log)
    warn_match = re.search(warning_pattern, log)
    
    # 提取匹配结果
    passed = int(passed_match.group(1)) if passed_match else 0
    xpassed = int(xpassed_match.group(1)) if xpassed_match else 0
    skipped = int(skipped_match.group(1)) if skipped_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    xfailed = int(xfailed_match.group(1)) if xfailed_match else 0
    warn = int(warn_match.group(1)) if warn_match else 0
    
    return passed, skipped, failed
    


def read_file(file_path):
    """读取文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"无法读取文件 {file_path}: {e}")
        return ""


def find_model_name(func, result_dir):
    """
    根据func从result_dir中任意一个相关文件中提取model_name
    支持文件类型：
        - {func}_completed_{model_name}.py
        - {func}_completed_{model_name}.prompt.py
        - {func}_completed_{model_name}.source.py
    """
    # 定义正则表达式模式，捕获model_name
    pattern = re.compile(rf"^{re.escape(func)}_completed_(.+?)(?:\.prompt|\.source)?\.py$")

    for filename in os.listdir(result_dir):
        match = pattern.match(filename)
        if match:
            return match.group(1)
    return None


def load_func_call_tree(tree_path):
    with open(tree_path, 'r') as f:
        tree_data = json.load(f)
        
    def build_tree(data):
        from pycallgraph.util import CallNode
        if 'call_position' in data:
            node = CallNode(data['name'], data.get('source_dir'), data.get('call_position'))
        else:
            node = CallNode(data['name'], data.get('source_dir'))
        for child_data in data.get('children', []):
            child_node = build_tree(child_data)
            node.add_child(child_node)
        return node
        
    root = build_tree(tree_data)
    return root

def get_code_from_file(file, start, end):
    """
    从文件中提取指定行号范围内的代码
    
    Args:
        file: 文件路径
        start: 起始行号（1-based）
        end: 结束行号（1-based）
    
    Returns:
        list: 提取的代码行列表
    """
    lines = file.splitlines()
    # 确保行号在有效范围内
    start = max(1, min(start, len(lines)))
    end = max(start, min(end, len(lines)))
    
    # 由于行号是1-base的，需要转换为0-base的索引
    return '\n'.join(lines[start-1:end])



def convert_path_to_module(path: str, root_path: str) -> str:
    """将文件路径转换为Python模块导入格式
    
    Args:
        path: 需要转换的文件路径
        root_path: 根路径，用于计算相对路径
        
    Returns:
        str: 转换后的模块导入路径，例如 'module.submodule'
    """
    
    # 获取相对路径
    
    relative_path = path.replace(root_path, '').lstrip('/')
    # 移除.py后缀
    module_path = relative_path.replace('.py', '')
    # 将路径分隔符转换为模块分隔符
    module_name = module_path.replace('/', '.')
    return module_name

def write_list_to_jsonl(file_path, data):
    """
    将一个list写入 JSONL 文件。支持中文字符。
    
    :param file_path: JSONL 文件的路径。
    :param data: 要写入的list。
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in data:
            json_line = json.dumps(item, ensure_ascii=False)
            f.write(json_line + '\n')


def test_path_to_str(test_list, repo_root):
    res = ''
    for test_path in test_list:
        path = os.path.join(repo_root, test_path)
        with open(path,'r') as f:
            test_file = f.read()
        res += f'''# {test_path}\n 
{test_file}'''
    return res 

def remove_common_prefix(str1, str2):
    if len(str1) == 0 or len(str2) == 0:
        return str1
    try:
        if str1.startswith(str2):
            if str1[len(str2)] == '\n':
                return str1[len(str2)+1:]
            else:
                return str1[len(str2):]
        else:
            return str1
    except Exception as e:
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



if __name__ == '__main__':
   
    chat_message = 'Hello'
    print(get_response(chat_message, 'deepseek-chat'))