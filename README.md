# CoreCodeBench


## Overview
[CoreCodeBench](https://huggingface.co/datasets/tubehhh/CoreCodeBench-Single) is a benchmark for evaluating LLMs in real-world software development tasks. It contains *1500+* cases, covering development, bug fix, and TDD scenarios with single-function and multi-function problems.

CorePipe is the pipeline for CoreCodeBench. It contains three stages: preprocess, single-function problem generation, and multi-function problem generation. Given a repository, CorePipe can generate benchmark cases for different scenarios.




## Quick Start
First, clone the repository and download the dataset.
```
git clone https://github.com/fulingyue/CoreCodeBench.git
cd CoreCodeBench
```
<!-- Download the Source Copy Code of Repositories from [HuggingFace](https://huggingface.co/datasets/tubehhh/CoreCodeBench-Single)). -->


### Evaluation for CoreCodeBench
### Environment Setup
1. create conda environments
```
cd environments
source ./all_env_create.sh
```
2. check the environment


### Generation
#### Preprocess
```
conda activate {repo_name_env}
./Generation/Single-Function/Preprocess.sh {repo_name}
```
#### Single Function Problem Generation
1. Development
    ```
    conda activate {repo_name_env}
    ./Generation/Single-Function/Development_generate.sh {repo_name}
    ./Generation/Single-Function/Filter.sh {repo_name} {model_name}
    ```
2. TDD
    ```
    conda activate {repo_name_env}
    ./Generation/Single-Function/TDD_generate.sh {repo_name}

    ```
3. Debug
    ```
    conda activate {repo_name_env}
    ./Generation/Single-Function/BugFix_generate.sh {repo_name} {gen_model} {rewrite_model}
    ```
#### Multi-Function Problem Generation
1. Development
    ```
    conda activate {repo_name_env}
    ./Generation/Multi-Function/function_generate.sh {repo_name}
    ```
2. TDD
    ```
    conda activate {repo_name_env}
    ./Generation/Multi-Function/function_generate_tdd.sh {repo_name}
    ```
3. BugFix
    ```
    conda activate {repo_name_env}
    ./Generation/Multi-Function/function_generate_debug.sh {repo_name}
    ```
4. Difficult
    ```
    conda activate {repo_name_env}
    ./Generation/Multi-Function/function_generate_difficult.sh {repo_name}
    ```

### Evaluation
#### Single Function Problem Evaluation
1. Development
    ```
    conda activate {repo_name_env}
    ./Evaluation/Single-Function/Development_evaluate.sh
    ```
2. BugFix
    ```
    conda activate {repo_name_env}
    ./Evaluation/Single-Function/Debug_evaluate.sh
    ```
3. TDD
    ```
    conda activate {repo_name_env}
    ./Evaluate/Single-Function/TDD_evaluate.sh
    ```
#### Multi Function Problem Evaluation
1. Development
    ```
    conda activate {repo_name_env}
    ./Evaluation/Multi-Function/function_test_run.sh {repo_name} {model_name}
    ```
2. TDD
    ```
    conda activate {repo_name_env}
    ./Evaluation/Multi-Function/function_test_tdd_run.sh {repo_name} {model_name}
    ```
3. BugFix
    ```
    conda activate {repo_name_env}
    ./Evaluation/Multi-Function/function_test_debug_run.sh {repo_name} {model_name}
    ```
4. Difficult
    ```
    conda activate {repo_name_env}
    ./Evaluation/Multi-Function/function_test_difficult_run.sh {repo_name} {model_name}
    ```

## License
This project is licensed under the MIT License.

## Contact
For questions or feedback, please open an issue or contact fulingyue@sjtu.edu.cn.