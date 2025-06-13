# 使用官方Python镜像作为基础
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装Miniconda
RUN apt-get update && apt-get install -y wget && \
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh && \
    bash miniconda.sh -b -p /opt/conda && \
    rm miniconda.sh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 将conda添加到PATH
ENV PATH=/opt/conda/bin:$PATH

# 复制环境文件
COPY d3rlpy.yml /app/

# 创建conda环境
RUN conda env create -f d3rlpy.yml

# 设置shell为bash并激活conda环境
SHELL ["/bin/bash", "-c"]
RUN echo "source activate d3rlpy" > ~/.bashrc
ENV PATH /opt/conda/envs/d3rlpy/bin:$PATH

# 设置入口点
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "d3rlpy"]
CMD ["python"]
