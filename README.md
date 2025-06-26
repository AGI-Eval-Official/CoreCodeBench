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
Second, download the CoreCodeBench from HuggingFace [Single](https://huggingface.co/datasets/tubehhh/CoreCodeBench-Single)/ [Multi](https://huggingface.co/datasets/tubehhh/CoreCodeBench-Multi), and move jsonl files to `./CoreCodeBench/` folder.

Then, download the source code files from [here](https://huggingface.co/datasets/tubehhh/CoreCodeBench-Single/resolve/main/source_code.zip) to the repo directory and extract them as Source_Copy folder.
% TODO

Now, the file tree should be:
<pre>
<code>
CoreCodeBench/
├── CoreCodeBench/
│   ├── CoreCodeBench_Multi.jsonl/
│   └── COreCodeBench_Single.jsonl/
├── Source_Copy/
│   ├── cloudnetpy/
│   ├── d3rlpy/
│   └── ...
├── README.md
├── LICENSE
└── ...
</code>
</pre>


### Environment Setup
We strongly recommend using Docker to get a stable environment and reliable experimental results. Follow the instructions in the [Docker setup guide](https://docs.docker.com/engine/install/) to install Docker on your machine.

#### Docker Environment Setup
1. Run `environments/all_env_create_docker.sh` to pull dockers from Docker Hub.
2. Check docker environment
   - Run the check script: `bash environments/check_env_docker.sh`
   - This will verify docker images availability, environment configuration, and basic setup

#### Conda Environment Setup
We also provide conda version environment setup. However, to prevent incompatibility issues across different operating systems, we still strongly recommend using Docker.

1. Run `environments/all_env_create_conda.sh` to create conda environments.
2. Run `environments/chec_env_conda.sh` amd check conda environments.

### Evaluation for CoreCodeBench




### Generation of CorePipe
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

## Citation
If you find our work helpful,

## Contact
For questions or feedback, please open an issue or contact fulingyue@sjtu.edu.cn.