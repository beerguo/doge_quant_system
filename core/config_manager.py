"""
配置管理模块 - 负责加载、保存和管理所有系统配置

主要功能:
1. 从文件加载策略配置
2. 动态更新策略启用状态
3. 管理策略参数
4. 管理风险管理参数

设计特点:
- 配置持久化: 所有更改会保存到文件
- 模块化: 支持策略、风险等不同类别的配置
- 安全性: 避免敏感信息暴露
"""

import json
import os
from typing import Dict, Any
from config.settings import SYSTEM_CONFIG

class ConfigManager:
    """
    配置管理器类
    
    负责系统配置的加载、更新和保存
    """
    
    def __init__(self, config_path: str = "config/strategy_config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        print(f"配置管理器已初始化，配置文件: {config_path}")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件，如果不存在则创建默认配置
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        # 检查配置目录是否存在，不存在则创建
        config_dir = os.path.dirname(self.config_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        # 如果配置文件存在，加载它
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                print(f"已加载现有配置: {self.config_path}")
                return config
            except Exception as e:
                print(f"加载配置文件时出错: {str(e)}，将创建默认配置")
        
        # 创建默认配置
        default_config = {
            "active_strategies": ["bollinger", "breakout", "multi_timeframe"],
            "strategy_params": {
                "bollinger": {
                    "enabled": True,
                    "period": 20,
                    "std_dev": 2.0,
                    "buy_threshold": 0.3,
                    "sell_threshold": 0.7
                },
                "breakout": {
                    "enabled": True,
                    "atr_period": 14,
                    "volume_factor": 1.5,
                    "breakout_factor": 1.5
                },
                "multi_timeframe": {
                    "enabled": True,
                    "daily_sma_fast": 50,
                    "daily_sma_slow": 200,
                    "rsi_period": 14,
                    "rsi_overbought": 70,
                    "rsi_oversold": 35
                },
                "twitter_sentiment": {
                    "enabled": True,
                    "positive_threshold": 0.6,
                    "negative_threshold": -0.4,
                    "influence_factor": 1.5
                }
            },
            "risk_management": {
                "max_position_percent": 5.0,
                "max_daily_loss": 3.0,
                "stop_loss_percent": 5.0,
                "take_profit_ratio": 2.0
            }
        }
        
        # 保存默认配置
        self._save_config(default_config)
        print(f"已创建默认配置: {self.config_path}")
        return default_config
    
    def _save_config(self, config: Dict[str, Any] = None):
        """
        保存配置到文件
        
        Args:
            config: 要保存的配置字典(可选)
        """
        save_config = config if config is not None else self.config
        
        # 确保目录存在
        config_dir = os.path.dirname(self.config_path)
        os.makedirs(config_dir, exist_ok=True)
        
        # 保存配置
        with open(self.config_path, 'w') as f:
            json.dump(save_config, f, indent=2, sort_keys=True)
        print(f"配置已保存到: {self.config_path}")
    
    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """
        获取特定策略的配置
        
        Args:
            strategy_name: 策略名称
        
        Returns:
            Dict[str, Any]: 策略配置字典
        """
        return self.config["strategy_params"].get(strategy_name, {})
    
    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """
        检查策略是否启用
        
        Args:
            strategy_name: 策略名称
        
        Returns:
            bool: 策略是否启用
        """
        # 策略必须在active_strategies列表中且其enabled标志为True
        return (strategy_name in self.config["active_strategies"] and 
                self.config["strategy_params"][strategy_name]["enabled"])
    
    def update_strategy_status(self, strategy_name: str, enabled: bool):
        """
        启用或禁用策略
        
        Args:
            strategy_name: 策略名称
            enabled: 是否启用
        """
        # 更新active_strategies列表
        if enabled and strategy_name not in self.config["active_strategies"]:
            self.config["active_strategies"].append(strategy_name)
            print(f"已添加策略到active_strategies: {strategy_name}")
        elif not enabled and strategy_name in self.config["active_strategies"]:
            self.config["active_strategies"].remove(strategy_name)
            print(f"已从active_strategies移除策略: {strategy_name}")
        
        # 更新策略的enabled标志
        if strategy_name in self.config["strategy_params"]:
            self.config["strategy_params"][strategy_name]["enabled"] = enabled
            print(f"策略 {strategy_name} 的enabled标志已设置为: {enabled}")
            self._save_config()
        else:
            print(f"警告: 策略 {strategy_name} 未在strategy_params中定义")
    
    def update_strategy_params(self, strategy_name: str, params: Dict[str, Any]):
        """
        更新策略参数
        
        Args:
            strategy_name: 策略名称
            params: 新的参数字典
        """
        if strategy_name in self.config["strategy_params"]:
            # 更新参数
            self.config["strategy_params"][strategy_name].update(params)
            print(f"策略 {strategy_name} 的参数已更新: {params}")
            self._save_config()
        else:
            print(f"警告: 策略 {strategy_name} 未在strategy_params中定义")
    
    def update_risk_params(self, params: Dict[str, Any]):
        """
        更新风险管理参数
        
        Args:
            params: 新的风险管理参数
        """
        self.config["risk_management"].update(params)
        print(f"风险管理参数已更新: {params}")
        self._save_config()
    
    def get_risk_params(self) -> Dict[str, Any]:
        """
        获取风险管理参数
        
        Returns:
            Dict[str, Any]: 风险管理参数
        """
        return self.config["risk_management"].copy()
