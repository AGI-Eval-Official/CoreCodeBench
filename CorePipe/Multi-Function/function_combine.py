import json
from collections import defaultdict
import argparse
from CorePipe import utils
import os
import CorePipe.config as config

root_path = config.root_path

parser = argparse.ArgumentParser()
parser.add_argument('--type', type=list, nargs='+', default=["Development", "TDD", "BugFix", "Difficult"], help='Specify types, e.g., Development, TDD, BugFixx')
args = parser.parse_args()

# def merge_jsonl_data(file_path):
#     merged_data = {}

#     # 读取jsonl文件
#     sum = 0
#     with open(file_path, 'r') as infile:
#         for line in infile:
#             sum += 1
#             entry = json.loads(line)
#             ids_tuple = tuple(entry["id"])

#             if ids_tuple not in merged_data:
#                 merged_data[ids_tuple] = {
#                     "project": entry["project"],
#                     "origin_file": [],
#                     "test_list": [],
#                     "prob_info": [],
#                     "type": [],
#                     "node": [],
#                     "test": [],
#                     "language": entry["language"],
#                     "toolfunc_count": 0,
#                     "func_count": 0,
#                     "pytest_info": {"total_num": 0, "base_passed_num": 0}
#                 }
#             else:
#                 print(entry["test_list"][0])

#             # 遍历当前 entry 的数据并合并到结果中
#             for i, node in enumerate(entry["node"]):
#                 if node not in merged_data[ids_tuple]["node"]:
#                     merged_data[ids_tuple]["node"].append(node)
#                     merged_data[ids_tuple]["origin_file"].append(entry["origin_file"][i])
#                     merged_data[ids_tuple]["prob_info"].append(entry["prob_info"][i])
            
#             merged_data[ids_tuple]["test_list"].append(entry["test_list"][0])
            
#             merged_data[ids_tuple]["type"] = entry["type"]
#             merged_data[ids_tuple]["test"].extend(entry["test"])
#             merged_data[ids_tuple]["toolfunc_count"] = entry["toolfunc_count"]
#             merged_data[ids_tuple]["func_count"] = entry["func_count"]
#             merged_data[ids_tuple]["pytest_info"]["total_num"] += entry["pytest_info"]["total_num"]
#             merged_data[ids_tuple]["pytest_info"]["base_passed_num"] += entry["pytest_info"]["base_passed_num"]

#     # 去除 type 和 test 的重复项，保持原有顺序
#     print("!!!Running combine\n\n")
#     print(sum)
#     print(len(merged_data))
#     for ids, info in merged_data.items():
#         info["test"] = list(dict.fromkeys(info["test"]))

#     # 将结果写回jsonl文件
#     if args.if_comments == "full":
#         combine_path = f'/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/func_testcases/{args.repo_name}/func_testcases_combine_info.jsonl'
#     else:
#         combine_path = f'/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/func_testcases/{args.repo_name}/func_{args.if_comments}_testcases_combine_info.jsonl'

#     with open(combine_path, 'w') as outfile:
#         for ids, info in merged_data.items():
#             result_entry = {
#                 "id": list(ids),
#                 "project": info["project"],
#                 "origin_file": info["origin_file"],
#                 "test_list": info["test_list"],
#                 "prob_info": info["prob_info"],
#                 "type": info["type"],
#                 "node": info["node"],
#                 "test": info["test"],
#                 "language": info["language"],
#                 "toolfunc_count": info["toolfunc_count"],
#                 "func_count": info["func_count"],
#                 "pytest_info": {"total_num": info["pytest_info"]["total_num"], "base_passed_num": info["pytest_info"]["base_passed_num"]}
#             }
#             outfile.write(json.dumps(result_entry) + '\n')

def merge_jsonl_data_by_id_project(file_path, output_path):
    merged_data = {}
    sum = 0
    with open(file_path, 'r') as infile:
        for line in infile:
            sum += 1
            entry = json.loads(line)
            ids_tuple = tuple(entry["id"])
            project = entry["project"]
            key = (ids_tuple, project)
            if key not in merged_data:
                merged_data[key] = {
                    "project": entry["project"],
                    "origin_file": [],
                    "test_list": [],
                    "prob_info": [],
                    "type": [],
                    "node": [],
                    "test": [],
                    "language": entry["language"],
                    "toolfunc_count": 0,
                    "func_count": 0,
                    "pytest_info": {"total_num": 0, "base_passed_num": 0}
                }
            # 合并 node 相关
            if entry["test_list"][0] not in merged_data[key]["test_list"]:
                for i, node in enumerate(entry["node"]):
                    if node not in merged_data[key]["node"]:
                        merged_data[key]["node"].append(node)
                        merged_data[key]["origin_file"].append(entry["origin_file"][i])
                        merged_data[key]["prob_info"].append(entry["prob_info"][i])
                merged_data[key]["test_list"].append(entry["test_list"][0])
                merged_data[key]["type"] = entry["type"]
                merged_data[key]["pytest_info"]["total_num"] += entry["pytest_info"]["total_num"]
                merged_data[key]["pytest_info"]["base_passed_num"] += entry["pytest_info"]["base_passed_num"]
            else:
                print(entry["test_list"][0])
                
    for key, info in merged_data.items():
        info["test"] = list(dict.fromkeys(info["test"]))
    with open(output_path, 'w') as outfile:
        for key, info in merged_data.items():
            result_entry = {
                "id": list(key[0]),
                "project": key[1],
                "origin_file": info["origin_file"],
                "test_list": info["test_list"],
                "prob_info": info["prob_info"],
                "type": info["type"],
                "node": info["node"],
                "language": info["language"],
                "pytest_info": {"total_num": info["pytest_info"]["total_num"], "base_passed_num": info["pytest_info"]["base_passed_num"]}
            }
            outfile.write(json.dumps(result_entry) + '\n')


# 新增：处理 multi_{problem_type}_retested.jsonl 合并
for problem_type in args.type:
    print(problem_type)
    retested_path = os.path.join(root_path, 'testcases', f'multi_{problem_type}_retested.jsonl')
    if not os.path.exists(retested_path):
        continue
    retested_combine_path = os.path.join(root_path, 'testcases', f'multi_{problem_type}.jsonl')
    merge_jsonl_data_by_id_project(retested_path, retested_combine_path)
