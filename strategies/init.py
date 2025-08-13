"""
策略注册模块 - 用于动态加载和管理所有交易策略

本模块提供:
1. 策略注册功能
2. 策略实例化
3. 策略状态管理

设计特点:
- 模块化: 每个策略独立实现
- 可插拔: 可动态启用/禁用策略
- 统一接口: 所有策略实现相同接口
"""

from .bollinger_strategy import BollingerStrategy
from .breakout_strategy import BreakoutStrategy
from .multi_timeframe_strategy import MultiTimeframeStrategy
from .twitter_strategy import TwitterSentimentStrategy
from data.twitter_data import TwitterData
from data.market_data import MarketData
from core.config_manager import ConfigManager
import logging

logger = logging.getLogger(__name__)

def register_strategies(market_data: MarketData, config_manager: ConfigManager, twitter_data: TwitterData = None) -> list:
    """
    注册所有可用策略
    
    Args:
        market_data: 市场数据对象
        config_manager: 配置管理器
        twitter_data: Twitter数据对象(可选)
    
    Returns:
        list: 策略实例列表
    """
    logger.info("注册交易策略...")
    
    # 基础策略(始终可用)
    strategies = [
        BollingerStrategy(market_data, config_manager),
        BreakoutStrategy(market_data, config_manager),
        MultiTimeframeStrategy(market_data, config_manager)
    ]
    
    # 如果Twitter分析可用，添加Twitter策略
    if twitter_data:
        strategies.append(TwitterSentimentStrategy(market_data, config_manager, twitter_data))
        logger.info("已添加Twitter情绪策略")
    
    # 显示已注册策略
    active_strategies = [s.name for s in strategies if s.is_enabled()]
    inactive_strategies = [s.name for s in strategies if not s.is_enabled()]
    
    logger.info(f"已注册 {len(strategies)} 个策略, {len(active_strategies)} 个策略已启用: {active_strategies}")
    if inactive_strategies:
        logger.info(f"以下策略已禁用: {inactive_strategies}")
    
    return strategies
