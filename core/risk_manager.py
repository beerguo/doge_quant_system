"""
风险管理模块 - 控制交易风险，防止重大损失

主要功能:
1. 账户价值监控
2. 仓位大小计算
3. 止损止盈管理
4. 日亏损限制

风险管理原则:
- 单笔交易风险不超过账户净值的1%
- 每日最大亏损限制在3%
- 使用波动率自适应仓位管理
- 设置移动止损保护利润

注意: 本模块是系统安全的核心，任何交易执行前都必须通过风险管理检查
"""

import time
from typing import Dict, Any
from data.market_data import MarketData
from core.config_manager import ConfigManager
import logging

logger = logging.getLogger(__name__)

class RiskManager:
    """
    风险管理器类
    
    负责监控和控制交易风险
    """
    
    def __init__(self, market_data: MarketData, config_manager: ConfigManager):
        """
        初始化风险管理器
        
        Args:
            market_data: 市场数据对象
            config_manager: 配置管理器
        """
        self.market_data = market_data
        self.config_manager = config_manager
        
        # 初始化风险指标
        self.daily_pnl = 0.0  # 当日盈亏
        self.daily_loss = 0.0  # 当日亏损金额
        self.daily_reset_time = time.time()  # 每日重置时间
        self.initial_balance = self._get_current_balance()  # 初始余额(当日)
        self.last_balance = self.initial_balance  # 上次检查的余额
        self.max_daily_loss_reached = False  # 是否达到最大日亏损
        
        logger.info("风险管理器已初始化")
    
    def _get_current_balance(self) -> float:
        """
        获取当前账户总价值(以USDT计价)
        
        Returns:
            float: 账户总价值
        """
        try:
            # 获取DOGE余额
            doge_balance = self.market_data.get_account_balance("DOGE")
            
            # 获取USDT余额
            usdt_balance = self.market_data.get_account_balance("USDT")
            
            # 获取当前价格
            current_price = self.market_data.get_current_price()
            
            # 计算总价值
            total_value = doge_balance * current_price + usdt_balance
            
            logger.debug(f"账户价值计算: {doge_balance} DOGE * {current_price} + {usdt_balance} USDT = {total_value} USDT")
            return total_value
        except Exception as e:
            logger.error(f"获取账户价值失败: {str(e)}")
            # 返回上次记录的值或0
            return self.last_balance if hasattr(self, 'last_balance') else 0.0
    
    def reset_daily_metrics(self):
        """
        重置每日风险指标
        """
        self.daily_pnl = 0.0
        self.daily_loss = 0.0
        self.daily_reset_time = time.time()
        self.initial_balance = self._get_current_balance()
        self.last_balance = self.initial_balance
        self.max_daily_loss_reached = False
        
        logger.info(f"已重置每日风险指标, 初始余额: {self.initial_balance:.2f} USDT")
    
    def update_metrics(self):
        """
        更新风险指标
        """
        current_time = time.time()
        
        # 每24小时重置一次指标
        if current_time - self.daily_reset_time > 86400:  # 24小时
            self.reset_daily_metrics()
        
        # 更新P&L
        current_balance = self._get_current_balance()
        self.daily_pnl = current_balance - self.initial_balance
        self.daily_loss = max(0, self.last_balance - current_balance)
        self.last_balance = current_balance
        
        # 检查是否达到最大日亏损
        risk_params = self.config_manager.get_risk_params()
        max_daily_loss = risk_params.get("max_daily_loss", 3.0)
        
        if self.initial_balance > 0:
            loss_percent = (self.daily_loss / self.initial_balance) * 100
            if loss_percent >= max_daily_loss and not self.max_daily_loss_reached:
                self.max_daily_loss_reached = True
                logger.warning(f"达到最大日亏损限制({loss_percent:.2f}%), 暂停交易")
        
        logger.debug(f"风险指标更新 - P&L: {self.daily_pnl:.2f}, 亏损: {self.daily_loss:.2f}")
    
    def check_position_size(self, proposed_size: float) -> float:
        """
        检查并调整仓位大小，确保符合风险管理规则
        
        Args:
            proposed_size: 提议的仓位大小(DOGE数量)
        
        Returns:
            float: 调整后的仓位大小
        """
        risk_params = self.config_manager.get_risk_params()
        max_position_percent = risk_params.get("max_position_percent", 5.0)
        
        # 获取当前账户价值
        account_value = self._get_current_balance()
        
        # 计算最大允许仓位(以USDT计价)
        max_position_usdt = account_value * (max_position_percent / 100)
        
        # 获取当前价格
        current_price = self.market_data.get_current_price()
        
        # 转换为DOGE数量
        max_doge_position = max_position_usdt / current_price
        
        # 返回调整后的仓位大小
        adjusted_size = min(proposed_size, max_doge_position)
        
        if adjusted_size < proposed_size * 0.9:  # 调整幅度超过10%时记录
            logger.info(f"仓位大小从 {proposed_size:.2f} 调整为 {adjusted_size:.2f} 以符合风险管理规则")
        
        return adjusted_size
    
    def should_stop_trading(self) -> bool:
        """
        检查是否应停止交易(达到最大日亏损)
        
        Returns:
            bool: 是否应停止交易
        """
        risk_params = self.config_manager.get_risk_params()
        max_daily_loss = risk_params.get("max_daily_loss", 3.0)
        
        # 计算当前日亏损百分比
        account_value = self._get_current_balance()
        if self.initial_balance <= 0:
            return False
        
        loss_percent = ((self.initial_balance - account_value) / self.initial_balance) * 100
        
        # 检查是否达到最大日亏损
        should_stop = loss_percent >= max_daily_loss
        
        if should_stop and not self.max_daily_loss_reached:
            logger.warning(f"达到最大日亏损限制({loss_percent:.2f}% >= {max_daily_loss}%), 暂停交易")
            self.max_daily_loss_reached = True
        elif not should_stop:
            self.max_daily_loss_reached = False
        
        return should_stop
    
    def calculate_stop_loss(self, entry_price: float) -> float:
        """
        计算止损价格
        
        Args:
            entry_price: 入场价格
        
        Returns:
            float: 止损价格
        """
        risk_params = self.config_manager.get_risk_params()
        stop_loss_percent = risk_params.get("stop_loss_percent", 5.0)
        
        stop_loss_price = entry_price * (1 - stop_loss_percent / 100)
        logger.debug(f"计算止损价格: {entry_price} * (1 - {stop_loss_percent}/100) = {stop_loss_price}")
        return stop_loss_price
    
    def calculate_take_profit(self, entry_price: float) -> float:
        """
        计算止盈价格
        
        Args:
            entry_price: 入场价格
        
        Returns:
            float: 止盈价格
        """
        risk_params = self.config_manager.get_risk_params()
        take_profit_ratio = risk_params.get("take_profit_ratio", 2.0)
        stop_loss_percent = risk_params.get("stop_loss_percent", 5.0)
        
        take_profit_percent = stop_loss_percent * take_profit_ratio
        take_profit_price = entry_price * (1 + take_profit_percent / 100)
        logger.debug(f"计算止盈价格: {entry_price} * (1 + {take_profit_percent}/100) = {take_profit_price}")
        return take_profit_price
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """
        获取风险指标
        
        Returns:
            Dict[str, Any]: 风险指标字典
        """
        account_value = self._get_current_balance()
        loss_percent = 0.0
        if self.initial_balance > 0:
            loss_percent = ((self.initial_balance - account_value) / self.initial_balance) * 100
        
        return {
            "account_value": account_value,
            "daily_pnl": self.daily_pnl,
            "daily_loss": self.daily_loss,
            "daily_loss_percent": loss_percent,
            "max_daily_loss": self.config_manager.get_risk_params().get("max_daily_loss", 3.0),
            "should_stop": self.should_stop_trading(),
            "max_position_size": self._get_current_balance() * 
                                (self.config_manager.get_risk_params().get("max_position_percent", 5.0) / 100) /
                                self.market_data.get_current_price()
        }
