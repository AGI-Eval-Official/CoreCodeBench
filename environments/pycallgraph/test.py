# -*- coding: utf-8 -*-
class A(object):
    def __init__(self):
        self.preprocess()
    
    def preprocess(self):
        self.a = 10
    

class B(A):
    def __call__(self,b):
        print(self.a * b)



if __name__ == "__main__":
    from pycallgraph import PyCallGraph, Config
    from pycallgraph import GlobbingFilter
    from pycallgraph.output import GraphvizOutput

    from pycallgraph.util import CallNode, CallNodeEncoder
    import os
    import sys
    import json
    import unittest

    config = Config(project_root='/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/pycallgraph')
    config.trace_filter = GlobbingFilter(
        exclude=[
            'pycallgraph.*', # 排除 pycallgraph 自身
            'os.*',          # 排除 os 模块
            'sys.*',         # 排除 sys 模块
            '*.<listcomp>*','*.<dictcomp>*','*.<setcomp>*','*.<genexpr>*','*.<module>*','*.<locals>*','*.<lambda>*'
        ]
    )

    # 使用 PyCallGraph 进行调用跟踪
    with PyCallGraph(output=GraphvizOutput(),config=config) as pycg:
        object_B = B()
        object_B(2)
    
    # 获取调用树
    call_tree = pycg.get_call_tree()
    
    def serialize_tree(node, depth):
        if depth == 6:
            return None
        return {{
            'name': node.name,
            'source_dir': node.source_dir,
            'call_position': node.call_position,
            'children': [serialize_tree(child, depth+1) for child in node.children],
        }}

    def merge_trees(root):
        # 使用字典存储合并后的节点
        node_dict = {{}}
        def merge_node(node):
            if node.name not in node_dict:
                # 如果节点名称不存在，则创建一个新的节点并添加到字典中
                new_node = CallNode(node.name, node.source_dir, node.call_position)
                node_dict[node.name] = new_node
            else:
                # 如果节点名称已经存在，则获取现有节点
                new_node = node_dict[node.name]
            
            for child in node.children:
                merged_child = merge_node(child)
                # 检查子节点是否已经存在于当前节点的子节点列表中
                if merged_child not in new_node.children and merged_child.name != new_node.name:
                    new_node.add_child(merged_child)

            return new_node
        # 从根节点开始合并
        new_root = merge_node(root)
        return new_root
    

    merged_tree = merge_trees(call_tree)

    
    with open(('funcCallTree_new.json'), 'w') as output_file:
        json.dump(serialize_tree(merged_tree, 0), output_file, indent=4)