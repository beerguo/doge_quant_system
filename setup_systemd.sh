#!/bin/bash
# setup_systemd.sh - systemd服务设置脚本

# 检查是否以root用户运行
if [ "$(id -u)" != "0" ]; then
    echo "错误: 此脚本必须以root用户运行"
    echo "请使用: sudo bash setup_systemd.sh"
    exit 1
fi

# 检查项目目录
if [ ! -d "/home/quantuser/doge_quant_system" ]; then
    echo "错误: 未找到项目目录 /home/quantuser/doge_quant_system"
    echo "请先完成基础安装步骤"
    exit 1
fi

# 创建systemd服务文件
cat > /etc/systemd/system/doge-quant.service << EOL
[Unit]
Description=Doge Quantitative Trading System
After=network.target

[Service]
User=quantuser
Group=quantuser
WorkingDirectory=/home/quantuser/doge_quant_system
Environment="PATH=/home/quantuser/doge_quant_system/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
EnvironmentFile=/home/quantuser/.config/doge_quant/.env
ExecStart=/home/quantuser/doge_quant_system/venv/bin/streamlit run ui/streamlit_ui.py --server.port \${STREAMLIT_SERVER_PORT} --server.address \${STREAMLIT_SERVER_ADDRESS}
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=doge_quant

[Install]
WantedBy=multi-user.target
EOL

# 创建Nginx配置
cat > /etc/nginx/sites-available/doge-quant << EOL
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:\${STREAMLIT_SERVER_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Streamlit需要的特殊头部
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时设置
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOL

# 启用Nginx站点
ln -sf /etc/nginx/sites-available/doge-quant /etc/nginx/sites-enabled/

# 测试Nginx配置
nginx -t
if [ $? -ne 0 ]; then
    echo "错误: Nginx配置测试失败"
    exit 1
fi

# 重新加载Nginx
systemctl reload nginx

# 重新加载systemd配置
systemctl daemon-reload

# 启动服务
systemctl start doge-quant

# 设置开机自启动
systemctl enable doge-quant

# 检查服务状态
systemctl status doge-quant

echo "系统服务已设置完成!"
echo "访问地址: http://$(hostname -I | awk '{print $1}')"
echo "查看日志: journalctl -u doge-quant -f"
