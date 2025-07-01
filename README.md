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

Then, download the source code files from [here](https://huggingface.co/datasets/meituan/CoreCodeBench-Source_Copy) to the repo directory and extract them as Source_Copy folder.

Now, the file tree should be:
<pre>
<code>
CoreCodeBench/
├── CoreCodeBench/
│   ├── CoreCodeBench_Multi.jsonl/
│   └── CoreCodeBench_Single.jsonl/
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
1. Run `docker pull fulingyue/corecodebench:all` to pull docker from Docker Hub.
2. Activate docker interactive environment with:
```
docker run -it -v /path/to/CoreCodeBench/:/workspace fulingyue/corecodebench:all /bin/bash
```

3. To check docker environment, run the script
```
bash /workspace/environments/check_env_conda.sh
```
This will verify docker images availability, environment configuration, and basic setup.

#### Conda Environment Setup
We also provide conda version environment setup. However, to prevent incompatibility issues across different operating systems, we still strongly recommend using Docker.

1. Run `environments/all_env_create_conda.sh` to create conda environments.
2. Run `environments/chec_env_conda.sh` and check conda environments.


> **Note**: If you encounter errors when checking the langchain environment, it may be due to outdated pytest snapshots. In this case, you'll need to update the snapshots by running `pytest --snapshot-update /workspace/path/to/failing/test/file` inside the Docker container.


### Evaluation for CoreCodeBench
The evaluation scripts are the same whether you use Docker or Conda environments. Before running the evaluation, please ensure you have successfully executed and passed the environment checks (`check_env_docker.sh` or `check_env_conda.sh`).

#### Model Setup
Before running evaluation, you need to implement how to get responses from your model in `Evaluation/utils.py`. Specifically:

1. Add your model's response generation logic in the `get_response()` function.
2. The function should take the following parameters:
   - chat_message: Input prompt text
   - model: Name of your model
   - gen_kwargs: Generation parameters dictionary (optional)
3. Return the model's text completion as a string

The example implementation for OpenAI API is already provided in the get_response() function in utils.py.

#### Single-Function Evaluation
For single-function problems, run
```
bash single_evaluate_conda.sh --model=model_name --types=Development,TDD,BugFix --output_dir=/workspace
```
Supported problem types: Development, BugFix, TDD.
You can run evaluation for a single problem type, for example:
```
bash single_evaluate_conda.sh --model=model_name --types=Development --output_dir=/workspace --root_dir=/workspace
```

#### Multi-Function Evaluation
For multi-function problems, run
```
bash multi_evaluate_conda.sh --model=model_name --types=Development,TDD,BugFix --output_dir=/workspace  --root_dir=/workspace
```


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