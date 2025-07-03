import ast
from collections import defaultdict
import textwrap
import os
import shutil
import subprocess


class EnhancedLValueTracker(ast.NodeVisitor):
    """
    跟踪 key_block 中的所有左值（被赋值的变量）。
    包含对 Assign, AugAssign, AnnAssign 以及特定方法调用修改的对象的检测。
    """
    def __init__(self):
        self.lvalues = set()
        # 默认的可扩展的 mutator 方法集合
        self.mutator_methods =  {'add', 'append', 'extend', 'update', 'remove', 'clear', 'delete'}

    def visit_Assign(self, node):
        for target in node.targets:
            self._process_target(target)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self._process_target(node.target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        """
        处理带类型注解的赋值，例如 x: int = 5
        """
        self._process_target(node.target)
        self.generic_visit(node)

    def visit_Call(self, node):
        """
        仅当方法名在 mutator_methods 列表中时，认为此方法调用会修改对象状态。
        """
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in self.mutator_methods:
                base_obj = self._get_base_name(node.func.value)
                if base_obj:
                    self.lvalues.add(base_obj)
        self.generic_visit(node)

    def _process_target(self, target):
        if isinstance(target, ast.Name):
            self.lvalues.add(target.id)
        elif isinstance(target, ast.Attribute):
            if isinstance(target.value, ast.Name) and target.value.id == 'self':
                self.lvalues.add(f'self.{target.attr}')
            else:
                full_attr = self._get_full_attribute_name(target)
                if full_attr:
                    self.lvalues.add(full_attr)
        elif isinstance(target, ast.Subscript):
            base = self._get_base_name(target.value)
            if base:
                self.lvalues.add(base)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._process_target(elt)
        # 可以根据需要添加更多类型的目标处理

    def _get_base_name(self, node):
        """
        递归获取节点的基变量名，例如：self.a.b -> self.a
        """
        if isinstance(node, ast.Subscript):
            return self._get_base_name(node.value)
        elif isinstance(node, ast.Attribute):
            return self._get_full_attribute_name(node)
        elif isinstance(node, ast.Name):
            return node.id
        return None

    def _get_full_attribute_name(self, node):
        """
        递归获取完整的属性名，例如 self.a.b -> self.a.b
        """
        attrs = []
        while isinstance(node, ast.Attribute):
            attrs.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            attrs.append(node.id)
            return '.'.join(reversed(attrs))
        return None

class EnhancedRValueTracker(ast.NodeVisitor):
    """
    跟踪 suffix_code 中的所有右值（被引用的变量）。
    排除作为函数或方法调用一部分的变量（如 UserDict 和 view）。
    """
    def __init__(self):
        self.rvalues = set()
        self.parent_stack = []
        # 名单中包含了需排除的名称（如模块名、类名等）
        self.excluded_names = ('torch','torch.nn')

    def visit(self, node):
        self.parent_stack.append(node)
        super().visit(node)
        self.parent_stack.pop()

    def visit_Name(self, node):
        # 排除作为函数调用一部分的变量
        if not self._is_inside_call(node):
            if node.id not in self.excluded_names:
                self.rvalues.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # 排除作为方法调用一部分的属性
        if not self._is_inside_call(node):
            # 仅添加完整的属性名，如 self.num_beam_hyps_to_keep
            full_attr = self._get_full_attribute_name(node)
            if full_attr and full_attr not in self.excluded_names:
                self.rvalues.add(full_attr)
        self.generic_visit(node)

    def visit_Subscript(self, node):
        base = self._get_base_name(node.value)
        if base and base not in self.excluded_names:
            self.rvalues.add(base)
        self.generic_visit(node)

    def _is_inside_call(self, node):
        """
        检查当前节点是否是一个函数或方法调用的一部分。
        """
        if len(self.parent_stack) < 2:
            return False
        parent = self.parent_stack[-2]
        if isinstance(parent, ast.Call) and parent.func is node:
            return True
        return False

    def _get_base_name(self, node):
        """
        递归获取 Subscript 节点的基变量名。
        """
        if isinstance(node, ast.Subscript):
            return self._get_base_name(node.value)
        elif isinstance(node, ast.Attribute):
            return self._get_full_attribute_name(node)
        elif isinstance(node, ast.Name):
            return node.id
        return None

    def _get_full_attribute_name(self, node):
        """
        递归获取完整的属性名，例如 self.a.b -> self.a.b
        """
        attrs = []
        while isinstance(node, ast.Attribute):
            attrs.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            attrs.append(node.id)
            return '.'.join(reversed(attrs))
        return None

def remove_indentation(code: str) -> str:
    """移除代码的缩进"""
    return textwrap.dedent(code)



def extract_lvalues_new(test_file, origin_file, key_block_start, key_block_end, args):
    tmp_running_path = args.tmp_repo_path
    tmp_origin_file = origin_file.replace(args.repo_path, tmp_running_path)
    temp_file = os.path.join(tmp_running_path, os.path.dirname(test_file), 'lhs.tmp')
    test_path = os.path.join(tmp_running_path, test_file)
    copy_copy_test_path = test_path.replace('.py', '_copy.py')
    shutil.copyfile(test_path, copy_copy_test_path)
    
    with open(copy_copy_test_path, 'r') as f:
        code = f.read()
    
    TIMEOUT=120
    if 'import unittest' in code:
        # 用unittest进行变量追踪
        prefix_code= f'''import sys
import torch
import copy
from deepdiff import DeepDiff

template_file = '{temp_file}'
class VariableTracker:
    def __init__(self, start_line, end_line, target_file):
        self.start_line = start_line
        self.end_line = end_line
        self.target_file = target_file
        self.previous_locals = {{}}
        
        with open(template_file, 'w') as f:
            f.write('')

    def safe_compare(self, var_name, current_value, previous_value):
        """Safely compare two values, returning True if they differ."""
        try:
            # 首先检查内存地址
            if id(current_value) == id(previous_value):
                return False
            
            # 使用 DeepDiff 进行深度比较
            diff = DeepDiff(current_value, previous_value, ignore_order=True)
            
            # 如果有差异，返回 True
            return bool(diff)
        except Exception as e:
            print(f"Comparison failed for variable '{{var_name}}': {{e}}")
            return True

    def trace_func(self, frame, event, arg):
        if (event == "line" and
            frame.f_code.co_filename.endswith(self.target_file) and
            self.start_line <= frame.f_lineno <= self.end_line):
            
            current_locals = copy.deepcopy(frame.f_locals)

            # 初始化时记录所有变量
            if not self.previous_locals:
                self.previous_locals = current_locals

            # 检查哪些变量发生了变化
            changed_vars = {{
                var: current_locals[var]
                for var in current_locals
                if (var not in self.previous_locals or
                    self.safe_compare(var, current_locals[var], self.previous_locals[var]))
            }}

            # 更新之前的局部变量状态
            self.previous_locals = current_locals

            if changed_vars:
                print('line: ', frame.f_lineno, 'changed_vars: ', changed_vars)
                with open(template_file, 'a') as f:
                    f.write('\\n'.join(list(changed_vars.keys())))
                    f.write('\\n')

        return self.trace_func

    def track_variable_changes(self, func):
        def wrapper(*args, **kwargs):
            sys.settrace(self.trace_func)
            try:
                return func(*args, **kwargs)
            finally:
                sys.settrace(None)
        return wrapper

# 设置行号范围
tracker = VariableTracker(start_line={key_block_start}, end_line={key_block_end}, target_file='{tmp_origin_file}')

# 设置全局跟踪函数
sys.settrace(tracker.trace_func)

'''
        suffix_code = '''
if  __name__ == "__main__":
    unittest.main()
# 取消跟踪
sys.settrace(None)'''
        new_code = prefix_code + code + suffix_code
        with open(copy_copy_test_path, 'w') as f:
            f.write(new_code)    
        # print('UNITESTING LHS....')
        env = os.environ.copy()
        env["PYTHONPATH"] = args.repo_running_path.replace(args.repo_path, tmp_running_path)
        module_name = copy_copy_test_path.replace(tmp_running_path,'').replace('.py','').replace('/','.')
        
        try:
            subprocess.run(['python', '-m', module_name], cwd=tmp_running_path, env=env, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"Unittest {module_name} exceeded time limit and was terminated.")
        
    else:
        prefix_code= f'''import sys
import torch
import copy
from deepdiff import DeepDiff
import pytest
import os
def pytest_addoption(parser):
    parser.addoption(
        "--only-extended",
        action="store_true",
        default=False,
        help="Run only extended tests (dummy fix)"
    )
template_file = '{temp_file}'
class VariableTracker:
    def __init__(self, start_line, end_line, target_file):
        self.start_line = start_line
        self.end_line = end_line
        self.target_file = target_file
        self.previous_locals = {{}}
        
        with open(template_file, 'w') as f:
            f.write('')

    def safe_compare(self, var_name, current_value, previous_value):
        """Safely compare two values, returning True if they differ."""
        try:
            # 首先检查内存地址
            if id(current_value) == id(previous_value):
                return False
            
            # 使用 DeepDiff 进行深度比较
            diff = DeepDiff(current_value, previous_value, ignore_order=True)
            
            # 如果有差异，返回 True
            return bool(diff)
        except Exception as e:
            print(f"Comparison failed for variable '{{var_name}}': {{e}}")
            return True

    def trace_func(self, frame, event, arg):
        
        if (event == "line" and
             frame.f_code.co_filename.endswith(self.target_file)  and
            self.start_line <= frame.f_lineno <= self.end_line):
            
            current_locals = copy.deepcopy(frame.f_locals)

            # 初始化时记录所有变量
            if not self.previous_locals:
                self.previous_locals = current_locals

            # 检查哪些变量发生了变化
            changed_vars = {{
                var: current_locals[var]
                for var in current_locals
                if (var not in self.previous_locals or
                    self.safe_compare(var, current_locals[var], self.previous_locals[var]))
            }}

            # 更新之前的局部变量状态
            self.previous_locals = current_locals

            if changed_vars:
                print('line: ', frame.f_lineno, 'changed_vars: ', changed_vars)
                with open(template_file, 'a') as f:
                    f.write('\\n'.join(list(changed_vars.keys())))
                    f.write('\\n')

        return self.trace_func

    
@pytest.fixture(scope="module", autouse=True)
def tracker():
    # Initialize the tracker
    tracker = VariableTracker(start_line={key_block_start}, end_line={key_block_end}, target_file='{tmp_origin_file}')
    sys.settrace(tracker.trace_func)
    yield tracker
    # Cleanup the tracker
    sys.settrace(None)
'''

        suffix_code = '''
if __name__ == "__main__":
    pytest.main([__file__])'''
        
        new_code = prefix_code + code + suffix_code
        with open(copy_copy_test_path, 'w') as f:
            f.write(new_code)   
        # print('PYTESTING LHS....') 
        
        env = os.environ.copy()
        env["PYTHONPATH"] = tmp_running_path
        module_name = copy_copy_test_path.replace(tmp_running_path,'').replace('.py','').replace('/','.')
        # print(f"modulename:{module_name}")
        # print(f"copy_path:{copy_copy_test_path}")
        # print(f"copy_running_path:{tmp_running_path}")
        # print(f"cwd: {tmp_running_path}")
        try:
            subprocess.run(['python', '-m', module_name], cwd=tmp_running_path, env=env, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"Unittest {module_name} exceeded time limit and was terminated.")
        
    try:       
        with open(temp_file, 'r') as f:
            lvalues = f.read().split('\n')
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return None
    # 把lhs.tmp删除
    os.remove(temp_file)

    return lvalues

def extract_lvalues_and_rvalues(key_block: str, suffix_code: str):
    """
    提取 key_block 中的左值和 suffix_code 中的右值。

    Args:
        key_block (str): 需要分析的代码块，其左值将被提取。
        suffix_code (str): 需要分析的代码块，其右值将被提取。
        mutator_methods (Set[str], optional): 认为是修改对象状态的方法名集合。默认为 {'add', 'append', 'extend', 'update', 'remove', 'clear'}

    Returns:
        Dict[str, List[str]]: 包含 'lvalues' 和 'rvalues' 的字典。
    """
    # Remove indentation
    dedented_key_block = remove_indentation(key_block)
    dedented_suffix_code = remove_indentation(suffix_code)

    # Parse left-hand values from key_block
    lvalue_tracker = EnhancedLValueTracker()
    try:
        lvalue_tracker.visit(ast.parse(dedented_key_block))
    except SyntaxError as e:
        print(f"Error parsing key_block: {dedented_key_block}")
        return [], []
    lvalues = sorted(lvalue_tracker.lvalues)

    # Parse right-hand values from suffix_code
    rvalue_tracker = EnhancedRValueTracker()
    try:
        rvalue_tracker.visit(ast.parse(dedented_suffix_code))
    except SyntaxError as e:
        print(f"Error parsing suffix_code: {dedented_suffix_code}")
        rvalue_tracker.rvalues = set()
    rvalues = sorted(rvalue_tracker.rvalues)
    return  lvalues,  rvalues


if __name__ == '__main__':
    key_block = '''
                for beam_token_rank, (next_token, next_score, next_index) in enumerate(
                    zip(next_tokens[batch_idx], next_scores[batch_idx], next_indices[batch_idx])
                ):
                    batch_beam_idx = batch_idx * self.group_size + next_index
                    # add to generated hypotheses if end of sentence
                    if (eos_token_id is not None) and (next_token.item() in eos_token_id):
                        # if beam_token does not belong to top num_beams tokens, it should not be added
                        is_beam_token_worse_than_top_num_beams = beam_token_rank >= self.group_size
                        if is_beam_token_worse_than_top_num_beams:
                            continue
                        if beam_indices is not None:
                            beam_index = beam_indices[batch_beam_idx]
                            beam_index = beam_index + (batch_beam_idx,)
                        else:
                            beam_index = None

                        self._beam_hyps[batch_group_idx].add(
                            input_ids[batch_beam_idx].clone(),
                            next_score.item(),
                            beam_indices=beam_index,
                            generated_len=cur_len - decoder_prompt_len,
                        )
                    else:
                        # add next predicted token since it is not eos_token
                        next_beam_scores[batch_idx, beam_idx] = next_score
                        next_beam_tokens[batch_idx, beam_idx] = next_token
                        next_beam_indices[batch_idx, beam_idx] = batch_beam_idx
                        beam_idx += 1

                    # once the beam for next step is full, don't add more tokens to it.
                    if beam_idx == self.group_size:
                        break

                if beam_idx < self.group_size:
                    raise ValueError(
                        f"At most {self.group_size} tokens in {next_tokens[batch_idx]} can be equal to `eos_token_id:"
                        f" {eos_token_id}`. Make sure {next_tokens[batch_idx]} are corrected."
                    )

                # Check if we are done so that we can save a pad step if all(done)
                self._done[batch_group_idx] = self._done[batch_group_idx] or self._beam_hyps[batch_group_idx].is_done(
                    next_scores[batch_idx].max().item(), cur_len, decoder_prompt_len
                )
    '''
    suffix_code = '''
            sent_lengths = input_ids.new(batch_size * self.num_beam_hyps_to_keep)
            best = []
            best_indices = []
            best_scores = torch.zeros(batch_size * self.num_beam_hyps_to_keep, device=self.device, dtype=torch.float32)

            # retrieve best hypotheses
            for i, beam_hyp in enumerate(self._beam_hyps):
                sorted_hyps = sorted(beam_hyp.beams, key=lambda x: x[0])
                for j in range(self.num_beam_hyps_to_keep):
                    best_hyp_tuple = sorted_hyps.pop()
                    best_score = best_hyp_tuple[0]
                    best_hyp = best_hyp_tuple[1]
                    best_index = best_hyp_tuple[2]
                    sent_lengths[self.num_beam_hyps_to_keep * i + j] = len(best_hyp)

                    # append to lists
                    best.append(best_hyp)

                    # append indices to list
                    best_indices.append(best_index)

                    best_scores[i * self.num_beam_hyps_to_keep + j] = best_score

            # prepare for adding eos
            sent_lengths_max = sent_lengths.max().item() + 1

            sent_max_len = min(sent_lengths_max, max_length) if max_length is not None else sent_lengths_max
            decoded: torch.LongTensor = input_ids.new(batch_size * self.num_beam_hyps_to_keep, sent_max_len)

            if len(best_indices) > 0 and best_indices[0] is not None:
                indices: torch.LongTensor = input_ids.new(batch_size * self.num_beam_hyps_to_keep, sent_max_len)
            else:
                indices = None

            # shorter batches are padded if needed
            if sent_lengths.min().item() != sent_lengths.max().item():
                if pad_token_id is None:
                    raise ValueError("`pad_token_id` has to be defined")
                decoded.fill_(pad_token_id)

            if indices is not None:
                indices.fill_(-1)

            # fill with hypotheses and eos_token_id if the latter fits in
            for i, (hypo, best_idx) in enumerate(zip(best, best_indices)):
                decoded[i, : sent_lengths[i]] = hypo

                if indices is not None:
                    indices[i, : len(best_idx)] = torch.tensor(best_idx)

                if sent_lengths[i] < sent_max_len:
                    # inserting only the first eos_token_id
                    decoded[i, sent_lengths[i]] = eos_token_id[0]

            return UserDict(
                {
                    "sequences": decoded,
                    "sequence_scores": best_scores,
                    "beam_indices": indices,
                }
            )
    '''
    result = extract_lvalues_and_rvalues(key_block, suffix_code)