#!/bin/bash
# start.sh - 系统启动脚本

# 检查是否以root用户运行
if [ "$(id -u)" = "0" ]; then
    echo "错误: 请不要以root用户运行此脚本"
    echo "建议创建专用用户: sudo adduser quantuser && sudo usermod -aG sudo quantuser"
    exit 1
fi

# 检查Python环境
if ! command -v python3.10 &> /dev/null; then
    echo "错误: 未找到Python 3.10"
    echo "请安装Python 3.10: sudo apt install python3.10 python3.10-venv"
    exit 1
fi

# 检查项目目录
if [ ! -d "config" ] || [ ! -d "core" ] || [ ! -d "data" ]; then
    echo "错误: 未找到项目文件"
    echo "请确保在项目根目录运行此脚本"
    exit 1
fi

# 检查环境变量文件
ENV_FILE="$HOME/.config/doge_quant/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "错误: 未找到环境变量文件 $ENV_FILE"
    echo "请创建环境变量文件:"
    echo "mkdir -p \$HOME/.config/doge_quant"
    echo "nano \$HOME/.config/doge_quant/.env"
    echo "参考 .env.example 文件格式"
    exit 1
fi

# 设置文件权限
chmod 600 "$ENV_FILE"

# 检查OKX API配置
if ! grep -q "OKX_API_KEY" "$ENV_FILE" || ! grep -q "OKX_SECRET_KEY" "$ENV_FILE" || ! grep -q "OKX_PASSPHRASE" "$ENV_FILE"; then
    echo "错误: 环境变量文件中缺少OKX API配置"
    echo "请确保包含 OKX_API_KEY, OKX_SECRET_KEY 和 OKX_PASSPHRASE"
    exit 1
fi

# 创建虚拟环境(如果不存在)
if [ ! -d "venv" ]; then
    echo "创建Python虚拟环境..."
    python3.10 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "安装Python依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 下载NLTK数据
echo "下载NLTK数据..."
python -c "import nltk; nltk.download('vader_lexicon')"

# 检查Streamlit配置
STREAMLIT_CONFIG="$HOME/.streamlit/config.toml"
if [ ! -f "$STREAMLIT_CONFIG" ]; then
    echo "创建Streamlit配置文件..."
    mkdir -p "$HOME/.streamlit"
    cat > "$STREAMLIT_CONFIG" << EOL
[server]
port = $STREAMLIT_SERVER_PORT
enableXsrfProtection = false
maxUploadSize = 1028

[theme]
primaryColor="#1f77b4"
backgroundColor="#f0f2f6"
secondaryBackgroundColor="#e0e0e0"
textColor="#262730"
font="sans serif"
EOL
fi

# 启动Streamlit应用
echo "启动狗狗币量化交易系统..."
streamlit run ui/streamlit_ui.py \
    --server.port ${STREAMLIT_SERVER_PORT:-8501} \
    --server.address ${STREAMLIT_SERVER_ADDRESS:-0.0.0.0} \
    --browser.serverPort ${STREAMLIT_BROWSER_SERVER_PORT:-8501}
