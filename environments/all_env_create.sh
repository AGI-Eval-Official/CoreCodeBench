#!/bin/bash

# 终端执行: source ./all_env_create.sh

# List of environment names
ENV_NAMES=("d3rlpy" "cloudnetpy" "datachain" "finam" "haystack" "inference" "langchain" "open-iris" "rdt" "skfolio" "transformers" "UniRef")

# 解析 --repo_idx 参数
for arg in "$@"; do
    case $arg in
        --repo_idx=*)
        REPO_IDX="${arg#*=}"
        shift
        ;;
    esac
done

if [ -n "$REPO_IDX" ]; then
    ENV_NAMES=("${ENV_NAMES[$REPO_IDX]}")
fi

echo "ENV_NAMES: $ENV_NAMES"

conda init ; source ~/.bashrc ; conda activate ;
# 循环创建和激活环境
for ENV_NAME in "${ENV_NAMES[@]}"; do
    YML_FILE="${ENV_NAME}.yml"

    # 检查文件是否存在
    if [ ! -f "$YML_FILE" ]; then
        echo "YML 文件不存在: $YML_FILE"
        continue
    fi

    # 创建 conda 环境
    conda env create -f "$YML_FILE"

    # 检查是否成功创建并激活
    if conda env list | grep "$ENV_NAME" >/dev/null 2>&1; then
        echo "成功激活 conda 环境: $ENV_NAME"
        conda activate "$ENV_NAME"
        if [ "$ENV_NAME" == "transformers" ]; then
            pip install aqlm==1.0.3
            pip install transformers==4.51.3
            pip install tokenizers==0.19.0
        fi
        if [ "$ENV_NAME" == "datachain" ]; then
            CFLAGS="-std=c99" pip install thriftpy2

            if [ -f /etc/os-release ]; then
                . /etc/os-release
                OS=$ID
            elif [ -f /etc/redhat-release ]; then
                OS=$(cat /etc/redhat-release | cut -d ' ' -f 1 | tr '[:upper:]' '[:lower:]')
            else
                OS="unknown"
            fi
            if [ "$OS" == "centos" ]; then
                echo "检测到 CentOS 系统"
                if ! rpm -q libsndfile &>/dev/null; then
                    echo "安装 epel-release..."
                    sudo yum install -y epel-release
                    echo "安装 libsndfile..."
                    sudo yum install -y libsndfile
                else
                    echo "libsndfile 已经安装。"
                fi
            elif [ "$OS" == "ubuntu" ]; then
                echo "检测到 Ubuntu 系统"
                if ! dpkg -l | grep -qw libsndfile1; then
                    echo "更新软件包列表..."
                    sudo apt update
                    echo "安装 libsndfile..."
                    sudo apt install -y libsndfile1
                else
                    echo "libsndfile 已经安装。"
                fi
            else
                echo "未知操作系统，无法确定安装方法。需手动安装安装 libsndfile。"
            fi
        fi
        conda deactivate
    else
        echo "环境$ENV_NAME 创建失败。请检查 YML 文件：$YML_FILE"
    fi
done
