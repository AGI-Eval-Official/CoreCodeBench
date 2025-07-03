import os
import shutil
import subprocess
import json
import unittest
import pycallgraph
import argparse
import CorePipe.utils as utils
import tempfile
import re
import logging
import CorePipe.config as config

def copy_and_modify_test_file(args, original_file, output_dir, tmp_repo_path):
    copy_file = original_file.replace(".py", "_copy.py")
    shutil.copyfile(original_file, copy_file)
    with open(copy_file, "r") as cfile:
        code = cfile.read()
    
    # remove unittest main entry
    code = re.sub(r"if __name__ ?== ?[\'\"]__main__[\'\"]:\s*unittest\.main\(\)", "", code)
    with open(copy_file, "w") as cfile:
        cfile.write(code)

    import_code = ""
    run_code = ""
    if 'import unittest' in code:
        import_code = "import unittest"
        run_code = "unittest.main(exit=False)"
    else:
        import_code = "import pytest"
        run_code = "pytest.main([__file__, '-s'])"
        
    if args.import_name == "":
        assert False, "import_name is empty"
        import_line = ""
        project_root = f"\"{args.copy_running_path}\""
    else:
        import_line = f"import {args.import_name}"
        project_root = f"os.path.dirname(os.path.dirname({args.import_name}.__file__))"
    
    ban_code = ""
    if args.repo_name == "langchain_core":
        ban_code = f"""from blockbuster import BlockBuster
    BlockBuster.deactivate
"""
    
    # insert code into the copied file
    with open(copy_file, 'a') as f:
        f.write(f'''\n
if __name__ == "__main__":
    # 事先要设置PYTHONPATH = runningpath 的路径
    from pycallgraph import PyCallGraph, Config
    from pycallgraph import GlobbingFilter
    from pycallgraph.output import GraphvizOutput

    from pycallgraph.util import CallNode, CallNodeEncoder
    import os
    import sys
    import json
    {import_line}
    {import_code}
    {ban_code}

    # 定义要测试的文件路径
    project_root = {project_root}
    sys.path.append(project_root)

    config = Config(project_root=project_root)
    config.trace_filter = GlobbingFilter(
        include=[
            '{args.repo_name}.*',   # 包括项目中的所有模块
            '{args.import_name}.*',
        ],
        exclude=[
            'pycallgraph.*', # 排除 pycallgraph 自身
            'os.*',          # 排除 os 模块
            'sys.*',         # 排除 sys 模块
            '*.<listcomp>*','*.<dictcomp>*','*.<setcomp>*','*.<genexpr>*','*.<module>*','*.<locals>*','*.<lambda>*'
        ]
    )

    # 使用 PyCallGraph 进行调用跟踪
    with PyCallGraph(output=GraphvizOutput(),config=config) as pycg:
        {run_code}
    
    # 获取调用树
    call_tree = pycg.get_call_tree()
    
    def serialize_tree(node, depth):
        if depth == 6:
            return None
        return {{
            'name': node.name,
            'source_dir': node.source_dir,   #os.path.relpath(node.source_dir, '{tmp_repo_path}'),
            'call_position': node.call_position,
            'children': [serialize_tree(child, depth+1) for child in node.children],
        }}

    def merge_trees(root):
        node_dict = {{}}
        def merge_node(node):
            if node.name not in node_dict:
                new_node = CallNode(node.name, node.source_dir, node.call_position)
                node_dict[node.name] = new_node
            else:
                # 如果节点名称已经存在，则获取现有节点
                new_node = node_dict[node.name]
            
            for child in node.children:
                merged_child = merge_node(child)
                if merged_child not in new_node.children and merged_child.name != new_node.name:
                    new_node.add_child(merged_child)

            return new_node

        new_root = merge_node(root)
        return new_root
    
    def get_2level_tree(root, level):
        if level == 2:
            root.children = []
            return
        else:
            # level = 0/1
            for child in root.children:
                get_2level_tree(child, level+1)


    merged_tree = merge_trees(call_tree)
    get_2level_tree(call_tree, 0)
    
    
    with open('{os.path.join(output_dir, 'funcCallTree.json')}', 'w') as output_file:
        json.dump(serialize_tree(merged_tree, 0), output_file, indent=4)
    
    with open('{os.path.join(output_dir, 'funcCallTree2level.json')}', 'w') as output_file:
        json.dump(call_tree, output_file, cls=CallNodeEncoder, indent=4)
''')
    return copy_file

def track_function(args, test_path, output_dir, tmp_repo_path):
    repo_test_path = args.repo_args["test_path"]
    init_path = os.path.join(repo_test_path, "__init__.py")
    
    test_case_dir = output_dir
    test_path_whole = os.path.join(tmp_repo_path, test_path)
    
    # copy and modify test file
    copy_file = copy_and_modify_test_file(args, test_path_whole, output_dir, tmp_repo_path)
    env = os.environ.copy()
    env["PYTHONPATH"] = args.repo_running_path.replace(args.repo_path, tmp_repo_path)
    module_name = test_path.replace('.py','').replace('/','.')+'_copy'
    log_file = os.path.join(output_dir, 'gen_func_tree.log')
    
    with open(log_file, "w") as output_file:
        try:
            if os.path.exists(init_path):
                command = [
                    f'PYTHONPATH=\"{env["PYTHONPATH"]}\"', 'python', '-m', f'{module_name}'
                ]
                print(' '.join(command))
                subprocess.run(['python', '-m', module_name], cwd=tmp_repo_path, env=env, stdout=output_file, stderr = output_file)
            else:
                command = [
                        f'PYTHONPATH=\"{env["PYTHONPATH"]}\"', 'python', f'{copy_file}'
                ]
                print(' '.join(command))
                subprocess.run(['python', copy_file], cwd=tmp_repo_path, env=env, stdout=output_file, stderr = output_file)
        
        except Exception as e:
            logging.error(f"Function tracker_function error: {e}")
            return False
    
    # rewrite source_dir to relative path
    if os.path.exists(os.path.join(output_dir, 'funcCallTree.json')):
        with open(os.path.join(output_dir, 'funcCallTree.json'), 'r') as f:
            data = json.load(f)
        def rewrite_source_dir(node):
            if node is None:
                return
            if node['source_dir'] is not None:
                node['source_dir'] = os.path.relpath(node['source_dir'], tmp_repo_path)
            for child in node['children']:
                rewrite_source_dir(child)
        rewrite_source_dir(data)
        with open(os.path.join(output_dir, 'funcCallTree.json'), 'w') as f:
            json.dump(data, f, indent=4)
        return True  
    else:
        return False

