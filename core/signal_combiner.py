"""
信号整合模块 - 将多个策略信号组合成最终交易决策

主要功能:
1. 接收各策略生成的信号
2. 根据策略权重和置信度整合信号
3. 生成最终交易决策
4. 计算仓位大小

设计原则:
- 信号加权: 根据策略权重和置信度计算加权信号
- 信号过滤: 仅当信号强度超过阈值时才执行交易
- 仓位计算: 基于账户价值和信号强度动态计算仓位

注意: 本模块是连接策略和执行的关键组件
"""

from typing import List, Dict, Any
from core.config_manager import ConfigManager
import logging

logger = logging.getLogger(__name__)

class SignalCombiner:
    """
    信号整合器类
    
    负责将多个策略信号组合成最终交易决策
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        初始化信号整合器
        
        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        logger.info("信号整合器已初始化")
    
    def combine_signals(self, strategy_signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        组合多个策略信号
        
        Args:
            strategy_signals: 策略信号列表，每个元素包含:
                - strategy: 策略名称
                - signal: 信号值(-1到1之间)
                - confidence: 置信度(0到1之间)
                - reason: 信号原因
        
        Returns:
            Dict[str, Any]: 整合后的信号，包含:
                - final_signal: 最终信号值(-1到1之间)
                - confidence: 整合后的置信度
                - reasons: 各策略贡献的原因列表
                - details: 各策略详细信息
        """
        total_weight = 0
        weighted_signal = 0
        total_confidence = 0
        reasons = []
        details = {}
        
        # 获取策略权重配置
        weights = self.config_manager.config.get("strategy_weights", {})
        
        logger.debug(f"开始整合信号，共收到 {len(strategy_signals)} 个策略信号")
        
        for signal in strategy_signals:
            strategy_name = signal.get("strategy", "unknown")
            signal_value = signal.get("signal", 0)
            confidence = signal.get("confidence", 0)
            
            # 获取该策略的权重
            weight = weights.get(strategy_name, 1.0/len(strategy_signals) if len(strategy_signals) > 0 else 0)
            
            logger.debug(f"处理策略 {strategy_name}: 信号={signal_value:.2f}, 置信度={confidence:.2f}, 权重={weight:.2f}")
            
            # 计算加权信号(仅当置信度>0时)
            if confidence > 0:
                weighted_signal += signal_value * confidence * weight
                total_weight += confidence * weight
                total_confidence += confidence * weight
                
                # 记录原因
                if signal_value != 0:
                    reasons.append(f"{strategy_name}: {signal.get('reason', '无具体原因')} (置信度: {confidence:.2f})")
                
                # 记录详细信息
                details[strategy_name] = {
                    "signal": signal_value,
                    "confidence": confidence,
                    "weight": weight,
                    "raw_signal": signal
                }
        
        # 计算最终信号和置信度
        final_signal = weighted_signal / total_weight if total_weight > 0 else 0
        confidence = total_confidence / total_weight if total_weight > 0 else 0
        
        # 限制置信度在0-1范围内
        confidence = max(0, min(1, confidence))
        
        logger.info(f"信号整合完成: 最终信号={final_signal:.2f}, 置信度={confidence:.2f}")
        
        return {
            "final_signal": final_signal,
            "confidence": confidence,
            "reasons": reasons,
            "details": details
        }
    
    def should_trade(self, combined_signal: Dict[str, Any], threshold: float = 0.3) -> bool:
        """
        判断是否应该交易
        
        Args:
            combined_signal: 整合后的信号
            threshold: 信号强度阈值
        
        Returns:
            bool: 是否应该交易
        """
        signal_strength = abs(combined_signal["final_signal"])
        confidence = combined_signal["confidence"]
        
        should_trade = signal_strength >= threshold and confidence >= 0.2
        
        if should_trade:
            logger.info(f"达到交易条件: 信号强度={signal_strength:.2f} >= {threshold}, 置信度={confidence:.2f} >= 0.2")
        else:
            logger.debug(f"未达到交易条件: 信号强度={signal_strength:.2f} < {threshold} 或 置信度={confidence:.2f} < 0.2")
        
        return should_trade
    
    def determine_order_type(self, signal: float) -> str:
        """
        确定订单类型
        
        Args:
            signal: 信号值
        
        Returns:
            str: 订单类型("buy"或"sell")
        """
        order_type = "buy" if signal > 0 else "sell"
        logger.debug(f"确定订单类型: 信号={signal:.2f} -> {order_type}")
        return order_type
    
    def calculate_position_size(self, signal: float, account_value: float, current_price: float) -> float:
        """
        计算仓位大小
        
        Args:
            signal: 最终信号强度(-1到1)
            account_value: 账户总价值(USDT)
            current_price: 当前价格
        
        Returns:
            float: 仓位大小(DOGE数量)
        """
        # 基础仓位: 账户价值的1%
        base_position = account_value * 0.01
        
        # 根据信号强度调整
        signal_factor = min(3.0, max(0.5, abs(signal) * 2))
        
        # 计算DOGE数量
        position_size = (base_position * signal_factor) / current_price
        
        logger.info(f"计算仓位大小: 账户价值={account_value:.2f} USDT, 信号强度={abs(signal):.2f}, "
                   f"基础仓位={base_position:.2f} USDT, 调整因子={signal_factor:.2f}, "
                   f"最终仓位={position_size:.2f} DOGE")
        
        return position_size
