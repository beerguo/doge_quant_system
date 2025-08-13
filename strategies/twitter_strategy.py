"""
Twitter情绪策略模块

策略原理:
1. 监控马斯克的推特消息
2. 使用NLP分析情感
3. 仅关注与加密货币相关的内容
4. 将情绪分析结果转化为交易信号

为什么重要:
- 马斯克的推特对狗狗币价格有显著影响
- 历史数据显示其推特可引起10-20%的短期价格波动
- 结合其他技术指标可提高交易信号可靠性

注意: 本策略需Twitter API Bearer Token，且仅在配置启用时生效
"""

from typing import Dict, Any
from data.market_data import MarketData
from core.config_manager import ConfigManager
from data.twitter_data import TwitterData
import logging

logger = logging.getLogger(__name__)

class TwitterSentimentStrategy:
    """
    Twitter情绪策略类
    """
    
    def __init__(self, market_data: MarketData, config_manager: ConfigManager, twitter_data: TwitterData):
        """
        初始化Twitter情绪策略
        
        Args:
            market_data: 市场数据对象
            config_manager: 配置管理器
            twitter_data: Twitter数据对象
        """
        self.market_data = market_data
        self.config_manager = config_manager
        self.twitter_data = twitter_data
        self.name = "twitter_sentiment"
        logger.info("Twitter情绪策略已初始化")
    
    def is_enabled(self) -> bool:
        """
        检查策略是否启用
        
        Returns:
            bool: 策略是否启用
        """
        # 策略启用需同时满足:
        # 1. 配置中启用
        # 2. TwitterData可用
        # 3. 有有效的Bearer Token
        is_enabled = (
            self.config_manager.is_strategy_enabled(self.name) and 
            self.twitter_data.should_consider_twitter()
        )
        
        logger.debug(f"Twitter情绪策略启用状态: {is_enabled}")
        return is_enabled
    
    def generate_signal(self) -> Dict[str, Any]:
        """
        生成交易信号
        
        Returns:
            Dict[str, Any]: 交易信号
        """
        if not self.is_enabled():
            logger.debug("Twitter情绪策略未启用或无相关推文，跳过信号生成")
            return {"signal": 0, "confidence": 0.0, "reason": "策略未启用或无相关推文"}
        
        # 获取策略配置
        config = self.config_manager.get_strategy_config(self.name)
        positive_threshold = config.get("positive_threshold", 0.6)
        negative_threshold = config.get("negative_threshold", -0.4)
        influence_factor = config.get("influence_factor", 1.5)
        
        logger.debug(f"使用Twitter参数: positive_threshold={positive_threshold}, "
                   f"negative_threshold={negative_threshold}, influence_factor={influence_factor}")
        
        try:
            # 获取最新推特情绪
            sentiment = self.twitter_data.get_latest_sentiment()
            
            # 获取当前价格
            current_price = self.market_data.get_current_price()
            
            # 检查是否持有仓位
            position = self.market_data.get_account_balance()
            has_position = position > 0.1
            
            logger.debug(f"Twitter情绪分析: 情感分={sentiment:.2f}")
            
            # 初始化信号
            signal = 0
            confidence = 0.0
            reason = ""
            
            # 强烈正面情绪 - 考虑买入或持有
            if sentiment >= positive_threshold:
                if not has_position:
                    signal = 1
                    confidence = min(1.0, sentiment)
                    reason = f"马斯克推文强烈看多狗狗币 (情感分: {sentiment:.2f})"
                    logger.info(f"Twitter买入信号: {reason}")
                else:
                    # 已持仓，可能考虑加仓
                    signal = 0.5
                    confidence = min(1.0, sentiment * 0.7)
                    reason = f"马斯克推文强化看多信号 (情感分: {sentiment:.2f})"
                    logger.info(f"Twitter持仓强化信号: {reason}")
            
            # 强烈负面情绪 - 考虑卖出
            elif sentiment <= negative_threshold:
                if has_position:
                    signal = -1
                    confidence = min(1.0, abs(sentiment))
                    reason = f"马斯克推文强烈看空狗狗币 (情感分: {sentiment:.2f})"
                    logger.warning(f"Twitter卖出信号: {reason}")
            
            # 中度正面情绪 - 可能强化其他策略信号
            elif sentiment > 0:
                signal = 0.3
                confidence = min(1.0, sentiment * 0.5)
                reason = f"马斯克推文轻微看多狗狗币 (情感分: {sentiment:.2f})"
                logger.debug(f"Twitter轻微看多信号: {reason}")
            
            # 中度负面情绪 - 可能弱化买入信号
            elif sentiment < 0:
                signal = -0.2
                confidence = min(1.0, abs(sentiment) * 0.3)
                reason = f"马斯克推文轻微看空狗狗币 (情感分: {sentiment:.2f})"
                logger.debug(f"Twitter轻微看空信号: {reason}")
            
            # 应用影响因子(放大信号)
            signal *= influence_factor
            confidence *= influence_factor
            
            # 信号强度限制在-1到1之间
            signal = max(-1, min(1, signal))
            confidence = min(1.0, confidence)
            
            return {
                "signal": signal,
                "confidence": confidence,
                "reason": reason,
                "sentiment": sentiment,
                "influence_factor": influence_factor,
                "strategy": self.name
            }
            
        except Exception as e:
            logger.exception(f"Twitter情绪策略分析错误: {str(e)}")
            return {"signal": 0, "confidence": 0.0, "reason": f"推特分析错误: {str(e)}"}
