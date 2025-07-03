import os
root_path = '/workspace'
repo_info_path= os.path.join(root_path, 'repo_info.json')
testcase_path = os.path.join(root_path, "CoreCodeBench")
single_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Single.jsonl")
multi_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Multi.jsonl")
function_empty_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Function_Empty.jsonl")
func_empty_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Function_Empty.jsonl")
workspace = os.path.join(root_path, "testcases", "workspace")
testcases_path = os.path.join(root_path, "testcases")
repo_path = os.path.join(root_path, "Source_Copy")

LINE_NUM_LIMIT = 50
LINE_NUM_MIN = 4

rewrite_models = ['gpt4o', 'claude3.5', 'qwen-plus-latest', 'doubao']
gen_models = [ 'qwen2.5-7B-Coder',   'longcat-large-32K','deepseek-16B-Coder','gpt4o-mini']
