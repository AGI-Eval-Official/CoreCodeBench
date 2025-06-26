#!/bin/bash

# this is 
# terminal: source ./all_env_create.sh


# List of environment names
ENV_NAMES=("d3rlpy" "cloudnetpy" "datachain" "finam" "haystack" "inference" "langchain" "open-iris" "rdt" "skfolio" "transformers" "uniref")

# Parse --repo_idx argument
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
# Loop to create and activate environments
for ENV_NAME in "${ENV_NAMES[@]}"; do
    YML_FILE="${ENV_NAME}.yml"

    # Check if file exists
    if [ ! -f "$YML_FILE" ]; then
        echo "YML file does not exist: $YML_FILE"
        continue
    fi

    # Create conda environment
    conda env create -f "$YML_FILE"

    # Check if successfully created and activate
    if conda env list | grep "$ENV_NAME" >/dev/null 2>&1; then
        echo "Successfully activated conda environment: $ENV_NAME"
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
                echo "Detected CentOS system"
                if ! rpm -q libsndfile &>/dev/null; then
                    echo "Installing epel-release..."
                    sudo yum install -y epel-release
                    echo "Installing libsndfile..."
                    sudo yum install -y libsndfile
                else
                    echo "libsndfile is already installed."
                fi
            elif [ "$OS" == "ubuntu" ]; then
                echo "Detected Ubuntu system"
                if ! dpkg -l | grep -qw libsndfile1; then
                    echo "Updating package list..."
                    sudo apt update
                    echo "Installing libsndfile..."
                    sudo apt install -y libsndfile1
                else
                    echo "libsndfile is already installed."
                fi
            else
                echo "Unknown operating system, cannot determine installation method. Please manually install libsndfile."
            fi
        fi
        conda deactivate
    else
        echo "Environment $ENV_NAME creation failed. Please check YML file: $YML_FILE"
    fi
done
