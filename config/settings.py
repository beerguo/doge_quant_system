"""
配置模块 - 系统全局设置

本模块定义了系统的所有全局配置参数，包括:
- OKX API 配置
- Twitter API 配置
- 系统运行参数
- 策略权重配置

注意: 敏感信息(如API密钥)应通过环境变量设置，而不是硬编码在代码中
"""

import os
from dotenv import load_dotenv

# 加载环境变量 (从.env文件或系统环境)
load_dotenv(os.path.expanduser("~/.config/doge_quant/.env"))

# OKX API 配置
OKX_CONFIG = {
    "api_key": os.getenv("OKX_API_KEY", ""),
    "secret_key": os.getenv("OKX_SECRET_KEY", ""),
    "passphrase": os.getenv("OKX_PASSPHRASE", ""),
    "base_url": "https://www.okx.com",
    "symbol": "DOGE-USDT"  # 狗狗币交易对
}

# Twitter API 配置
TWITTER_CONFIG = {
    "bearer_token": os.getenv("TWITTER_BEARER_TOKEN", ""),
    "user_id": "44196397",  # Elon Musk的Twitter用户ID
    "enabled": os.getenv("TWITTER_ANALYSIS_ENABLED", "true").lower() == "true"
}

# 系统配置
SYSTEM_CONFIG = {
    "check_interval": int(os.getenv("CHECK_INTERVAL", "300")),  # 检查间隔(秒)
    "data_cache_minutes": 60,  # 数据缓存时间(分钟)
    "max_strategies": 5,  # 同时启用的策略最大数量
    "log_file": os.getenv("LOG_FILE", "doge_quant.log"),
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
    "enable_backtest": os.getenv("ENABLE_BACKTEST", "false").lower() == "true",
    "simulation_mode": os.getenv("SIMULATION_MODE", "false").lower() == "true"
}

# 默认策略权重配置
STRATEGY_WEIGHTS = {
    "bollinger": 0.35,
    "breakout": 0.30,
    "multi_timeframe": 0.25,
    "twitter_sentiment": 0.10
}

def validate_config():
    """
    验证配置是否完整有效
    
    Returns:
        bool: 配置是否有效
        str: 错误信息(如果有)
    """
    # 检查OKX API配置
    if not OKX_CONFIG["api_key"] or not OKX_CONFIG["secret_key"] or not OKX_CONFIG["passphrase"]:
        return False, "OKX API密钥未正确配置! 请设置OKX_API_KEY、OKX_SECRET_KEY和OKX_PASSPHRASE环境变量"
    
    # 检查Twitter配置(如果启用)
    if TWITTER_CONFIG["enabled"] and not TWITTER_CONFIG["bearer_token"]:
        print("警告: Twitter分析已启用，但未配置BEARER_TOKEN")
    
    return True, ""
