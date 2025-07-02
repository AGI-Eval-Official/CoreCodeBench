import os
root_path = '/workspace'
repo_info_path= os.path.join(root_path, 'repo_info.json')
testcase_path = os.path.join(root_path, "CoreCodeBench")
single_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Single.jsonl")
multi_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Multi.jsonl")
function_empty_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Function_Empty.jsonl")
func_empty_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Function_Empty.jsonl")
workspace = os.path.join(root_path, "testcases", "workspace")
repo_path = os.path.join(root_path, "Source_Copy")

LINE_NUM_LIMIT = 50
LINE_NUM_MIN = 4
