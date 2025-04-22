# 使用官方 Python 运行时作为父镜像
FROM python:3.12-slim

# 安装构建 TA-Lib 和其他依赖所需的系统包
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 下载并安装 TA-Lib C 库
WORKDIR /tmp
RUN wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz \
    && tar -xzf ta-lib-0.6.4-src.tar.gz \
    && cd ta-lib-0.6.4/ \
    # Fix for https://github.com/TA-Lib/ta-lib/issues/177
    # Correct path for Makefile.am after cd ta-lib/
    # && sed -i.bak 's/ LDFLAGS = / LDFLAGS = -lm /' Makefile.am \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd / \
    && rm -rf /tmp/*

# 设置工作目录
WORKDIR /app

# 复制根 requirements 文件并安装依赖
# Ensure TA-Lib python wrapper is installed *after* the C library
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制 flask-api requirements 文件并安装依赖
# （如果 flask-api 有独立的依赖）
COPY flask-api/requirements.txt ./flask-api/
# 检查文件是否存在，如果存在则安装
RUN if [ -f flask-api/requirements.txt ]; then pip install --no-cache-dir -r flask-api/requirements.txt; fi

# 复制项目代码到工作目录
COPY . .

# 安装本地包 (quant_lib)
RUN pip install .

# 暴露 Flask 应用程序运行的端口
EXPOSE 5000
EXPOSE 8888

# 定义运行应用程序的命令
CMD ["gunicorn", "--chdir", "flask-api", "-w", "4", "-b", "0.0.0.0:5000", "run:create_app()"]