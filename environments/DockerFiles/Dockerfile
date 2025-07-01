FROM jupyter/scipy-notebook:latest
WORKDIR /app

COPY CondaYmls/ /app/CondaYmls/
RUN export http_proxy=http://10.229.18.30:8412
RUN export https_proxy=http://10.229.18.30:8412
# RUN apt-get update --fix-missing && apt-get install -y \
#     build-essential \
#     gcc \
#     g++ \
#     clang \
#     pkg-config \
#     libhdf5-dev \
#     libssl-dev
# RUN apt-get update --fix-missing && apt-get install -y \
#     clang

# # 循环创建所有conda环境
RUN conda env create -f /app/CondaYmls/inference.yml
RUN conda env create -f /app/CondaYmls/d3rlpy.yml
RUN conda env create -f /app/CondaYmls/cloudnetpy.yml
RUN conda env create -f /app/CondaYmls/datachain.yml
RUN conda env create -f /app/CondaYmls/finam.yml
RUN conda env create -f /app/CondaYmls/haystack.yml
RUN conda env create -f /app/CondaYmls/langchain.yml
RUN conda env create -f /app/CondaYmls/open-iris.yml
RUN conda env create -f /app/CondaYmls/rdt.yml
RUN conda env create -f /app/CondaYmls/skfolio.yml
RUN conda env create -f /app/CondaYmls/transformers.yml
RUN conda env create -f /app/CondaYmls/uniref.yml

RUN conda clean --all -f -y