import os
import CorePipe.utils as utils
import CorePipe.config as config
import argparse
import json
import logging


def find_origin_files(test_path, src_path, result_path):
    result = []
    if not os.path.exists(result_path):
        os.makedirs(result_path)
    with open(os.path.join(result_path, 'testcase_mapping.jsonl'), 'a') as f:
        # Traverse files under test_path directory
        for root, _, files in os.walk(test_path):
            for test_file in files:
                if test_file.endswith('.py') and test_file != '__init__.py':
                    # Remove the 'test_' prefix
                    if test_file.startswith('test_'):
                        candidate_file = test_file[5:]
                    else:
                        continue

                    # Get the directory structure of the test file
                    test_dir = os.path.relpath(root, test_path)

                    # Traverse files under src_path directory
                    for src_root, _, src_files in os.walk(src_path):
                        for src_file in src_files:
                            if src_file == candidate_file:
                                # Get the directory structure of the source file
                                src_dir = os.path.relpath(src_root, src_path)

                                # Check if the folder names are the same
                                if test_dir == src_dir:
                                    # Match successfully, record the result
                                    json.dump({
                                        'test_file': os.path.join(root, test_file),
                                        'origin_file': os.path.join(src_root, src_file)
                                    }, f)
                                    f.write('\n')
                                    break  # Exit the inner loop after finding a match
                        else:
                            continue
                        break  # Exit the outer loop after finding a match

def generate_directory_structure(root_dir):
    """
    Recursively traverse the directory and generate a directory structure.
    Only include directories that contain '__init__.py' or have files starting with 'test_'.
    """
    directory_structure = []
    for root, dirs, files in os.walk(root_dir):
        # Check if the current directory contains an '__init__.py' file
        has_init = any(file == '__init__.py' for file in files)
        # Check if the current directory contains a '.py' file starting with 'test_'
        has_test_files = any(file.startswith('test_') and file.endswith('.py') for file in files)
        # Get the relative path of the current directory
        relative_path = os.path.relpath(root, root_dir)
        # Check if the path contains 'tmp'
        if 'tmp' in relative_path.split(os.sep):
            continue
        
        # If any condition is met, add the current directory to the structure
        if has_init or has_test_files:
            directory_structure.append(os.path.relpath(root, root_dir))
    return directory_structure

def generate_prompt(repo_dir, file_structure):
    """
    Generate a prompt based on the file structure of the project directory.
    """
    prompt = "下面是某代码仓库的文件树：\n"
    for file_path in file_structure:
        prompt += f"- {file_path}\n"
    prompt += """
请你对于给出的文件名及其路径，分析出源代码和测试文件（重点关注到/test/下的/unit/、/unittest/字样）的路径对应关系，并给出一个json格式的输出。
注意，给出的对应关系必须是根路径的对应关系（例如transformers/test/repo/ 和transformers/test/utils/同时存在对应关系，就选择transformers/test/），若存在单测，则具体到单测文件夹（unit），对应关系中可以有文件的缺漏，只要文件之间大致对应即可。如果没有类似的对应关系，请你输出空的json即可。
样例输入：
```
- mlflow/gateway.py
- mlflow/gateway/providers.py
- mlflow/gateway/schemas.py
- mlflow/gemini.py
- mlflow/groq.py
- tests/test_gateway.py
- tests/gateway/test_providers.py
- tests/gateway/test_schemas.py
- mlflow/core/pipeline.py
- mlflow/core/pipeline/graph.py
- core_tests/pipeline.py
- core_tests/pipeline/graph.py
```
样例输出：
```
{
    "repo_name": "mlflow",
    "testcase_dir_mapping":{
        "mlflow/": "tests/",
        "mlflow/core/": "core_tests/",
    },
}
```

注意对于获得的mapping再进行检查，对于上级目录重复出现的路径，进行合并；并删除非核心代码部分的路径（如cli, community, _sdk, _cli/等等）；对于可以合并的情况合并路径。例如：

```
{
    "repo_name": "langchain",
    "testcase_dir_mapping": {
        "libs/cli/langchain_cli/": "libs/cli/tests/unit_tests/",
        "libs/community/langchain_community/": "libs/community/tests/unit_tests/",
        "libs/core/langchain_core/": "libs/core/tests/unit_tests/",
        "libs/langchain/langchain/": "libs/langchain/tests/unit_tests/",
        "libs/partners/anthropic/langchain_anthropic/": "libs/partners/anthropic/tests/unit_tests/",
        "libs/partners/chroma/langchain_chroma/": "libs/partners/chroma/tests/unit_tests/",
        "libs/partners/exa/langchain_exa/": "libs/partners/exa/tests/unit_tests/",
        "src/transformers/": "tests/",
        "src/transformers/models/": "tests/models/",
        "src/transformers/benchmark/": "tests/benchmark/",
        "inference_sdk/": "tests/inference_sdk/unit_tests/",

        "inference/core/": "tests/inference/unit_tests/core/",
        "inference/enterprise/": "tests/inference/unit_tests/enterprise/", 
        "inference/models/": "tests/inference/unit_tests/models/",
        "inference/core/workflows/": "tests/workflows/unit_tests/"
    }
}
```
无需解释，最终使用json格式并用``` ```输出：

```
{
    "repo_name": "langchain",
    "testcase_dir_mapping": {
        "libs/core/langchain_core/": "libs/core/tests/unit_tests/",
        "libs/langchain/langchain/": "libs/langchain/tests/unit_tests/",
        "src/transformers/": "tests/",
        "inference/": "tests/inference/unit_tests/"
    }
}
```

"""
    return prompt

def determine_test_file_locations(repo_dir):
    """
    Determine the test file locations using the GPT model via get_response.
    """
    # Step 1: Generate file structure
    file_structure = generate_directory_structure(repo_dir)
    
    # Step 2: Create prompt
    prompt = generate_prompt(repo_dir, file_structure)
    
    # Step 3: Call the model with the generated prompt
    response = utils.get_response(prompt, model='claude3.5')
    
    return response

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('--repo_name', type=str, default='', help='name of repo')
    args = parser.parse_args()
    repo_name = args.repo_name
    repo_dir = os.path.join(config.repo_path, args.repo_name)

    repo_info_path = config.repo_info_path
    result_path = os.path.join(config.workspace, args.repo_name)
    with open(repo_info_path, 'r') as file:
        repo_info = json.load(file)

    if repo_name not in repo_info:
        logging.warning("Repository '%s' not found in the JSON file.", repo_name)
        exit(1)

    repo_data = repo_info[repo_name]
    repo_path = os.path.join(config.repo_path, args.repo_name)

    if '_src_path' in repo_data and '_test_path' in repo_data:
        # Use predefined paths from config
        src_path = os.path.join(repo_path, repo_data['_src_path'].lstrip('/'))
        test_path = os.path.join(repo_path, repo_data['_test_path'].lstrip('/'))
        logging.info("Using predefined paths from config")
        logging.info("src_path: %s", src_path)
        logging.info("test_path: %s", test_path)
        find_origin_files(test_path, src_path, result_path)
    else:
        # Use GPT to determine paths
        test_file_locations_response = determine_test_file_locations(repo_dir)

        if test_file_locations_response.startswith("```") and test_file_locations_response.endswith("```"):
            if test_file_locations_response.startswith("```json"):
                test_file_locations_response = test_file_locations_response[7:-3].strip()
            else:
                test_file_locations_response = test_file_locations_response[3:-3].strip()

        logging.info(test_file_locations_response)

        data = json.loads(test_file_locations_response)
        testcase_dir_mapping = data["testcase_dir_mapping"]

        for src_path_relative, test_path_relative in testcase_dir_mapping.items():
            test_path = os.path.join(repo_path, test_path_relative)
            src_path = os.path.join(repo_path, src_path_relative)
            logging.info("src_path: %s", src_path)
            logging.info("test_path: %s", test_path)
            find_origin_files(test_path, src_path, result_path)

    logging.info("result_path: %s", result_path)
