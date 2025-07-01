import os
root_path = '/workspace'
repo_info_path= os.path.join(root_path, 'repo_info.json')
testcase_path = os.path.join(root_path, "CoreCodeBench")
single_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Single.jsonl")
multi_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Multi.jsonl")
func_empty_testcases_path = os.path.join(testcase_path, "CoreCodeBench_Function_Empty.jsonl")
repo_list = ['d3rlpy', 'finam', 'inference', 'langchain', 'open-iris', 'rdt', 'skfolio', 'UniRef', 'transformers', 'langchain_core', 'datachain', 'haystack', 'cloudnetpy']