"""
交易执行模块 - 执行和管理交易订单

主要功能:
1. 执行交易订单
2. 管理订单状态
3. 处理订单确认
4. 记录交易历史

安全特性:
- 交易前风险检查
- 最小订单间隔控制
- 交易历史记录
- 模拟模式支持

注意: 本模块是连接信号和实际交易的关键组件
"""

import time
import logging
from data.market_data import MarketData
from core.risk_manager import RiskManager
import pandas as pd

logger = logging.getLogger(__name__)

class OrderExecutor:
    """
    订单执行器类
    
    负责执行和管理交易订单
    """
    
    def __init__(self, market_data: MarketData, risk_manager: RiskManager):
        """
        初始化订单执行器
        
        Args:
            market_data: 市场数据对象
            risk_manager: 风险管理器
        """
        self.market_data = market_data
        self.risk_manager = risk_manager
        self.last_order_time = 0
        self.min_order_interval = 60  # 最小订单间隔(秒)
        self.order_history = []
        logger.info("订单执行器已初始化")
    
    def _can_place_order(self) -> bool:
        """
        检查是否可以下单
        
        Returns:
            bool: 是否可以下单
        """
        # 检查时间间隔
        if time.time() - self.last_order_time < self.min_order_interval:
            elapsed = time.time() - self.last_order_time
            logger.warning(f"无法下单: 距离上次下单仅 {elapsed:.1f} 秒，需等待 {self.min_order_interval - elapsed:.1f} 秒")
            return False
        
        # 检查风险条件
        if self.risk_manager.should_stop_trading():
            logger.warning("达到最大日亏损限制，停止交易")
            return False
        
        return True
    
    def execute_order(self, order_type: str, size: float, order_params: dict = None) -> Dict[str, Any]:
        """
        执行交易订单
        
        Args:
            order_type: 订单类型(buy/sell)
            size: 交易数量
            order_params: 订单参数
        
        Returns:
            Dict[str, Any]: 订单执行结果
        """
        logger.info(f"执行{order_type}订单，数量: {size:.4f} DOGE")
        
        if not self._can_place_order():
            return {
                "success": False,
                "message": "无法下单: 不满足下单条件",
                "details": {
                    "time_constraint": time.time() - self.last_order_time < self.min_order_interval,
                    "risk_constraint": self.risk_manager.should_stop_trading()
                }
            }
        
        # 检查并调整仓位大小
        adjusted_size = self.risk_manager.check_position_size(size)
        if adjusted_size < size * 0.9:  # 调整幅度超过10%时记录
            logger.info(f"仓位大小从 {size:.4f} 调整为 {adjusted_size:.4f} 以符合风险管理规则")
        
        # 构建订单参数
        params = order_params or {}
        params.update({
            "instId": self.market_data.symbol,
            "tdMode": "cash",
            "side": order_type,
            "ordType": "market",
            "sz": str(adjusted_size)
        })
        
        try:
            # 执行下单
            start_time = time.time()
            result = self.market_data.place_order(
                side=order_type,
                sz=adjusted_size,
                ordType=params.get("ordType", "market"),
                px=params.get("px")
            )
            execution_time = time.time() - start_time
            
            # 记录订单
            self.last_order_time = time.time()
            
            # 处理成功订单
            if result.get("code") == "0":
                order_id = result.get("data", [{}])[0].get("ordId", "unknown")
                current_price = self.market_data.get_current_price()
                
                # 记录到历史
                self.order_history.append({
                    "timestamp": time.time(),
                    "type": order_type,
                    "size": adjusted_size,
                    "price": current_price,
                    "order_id": order_id,
                    "status": "success",
                    "execution_time": execution_time
                })
                
                logger.info(f"成功提交{order_type}订单: {adjusted_size:.4f} DOGE @ {current_price:.6f}, "
                           f"订单ID: {order_id}, 耗时: {execution_time:.2f}秒")
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "message": f"成功提交{order_type}订单",
                    "details": result
                }
            
            # 处理失败订单
            else:
                error_msg = result.get("msg", "未知错误")
                logger.error(f"下单失败: {error_msg}")
                
                self.order_history.append({
                    "timestamp": time.time(),
                    "type": order_type,
                    "size": adjusted_size,
                    "order_id": "failed",
                    "status": "failed",
                    "error": error_msg
                })
                
                return {
                    "success": False,
                    "message": f"下单失败: {error_msg}",
                    "details": result
                }
                
        except Exception as e:
            logger.exception(f"执行订单时出错: {str(e)}")
            self.order_history.append({
                "timestamp": time.time(),
                "type": order_type,
                "size": adjusted_size,
                "order_id": "error",
                "status": "error",
                "error": str(e)
            })
            return {
                "success": False,
                "message": f"执行订单异常: {str(e)}",
                "details": {"error": str(e)}
            }
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        获取订单状态
        
        Args:
            order_id: 订单ID
        
        Returns:
            Dict[str, Any]: 订单状态
        """
        logger.debug(f"查询订单状态: {order_id}")
        
        # 在历史记录中查找
        for order in self.order_history:
            if order["order_id"] == order_id:
                return {
                    "success": True,
                    "status": order["status"],
                    "details": order
                }
        
        # 如果找不到，返回错误
        logger.warning(f"订单不存在: {order_id}")
        return {
            "success": False,
            "message": "订单不存在"
        }
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        取消订单
        
        Args:
            order_id: 订单ID
        
        Returns:
            Dict[str, Any]: 取消结果
        """
        logger.info(f"取消订单: {order_id}")
        
        try:
            # 实际实现需要调用OKX API取消订单
            # 这里简化处理
            for order in self.order_history:
                if order["order_id"] == order_id and order["status"] == "pending":
                    order["status"] = "cancelled"
                    logger.info(f"订单已取消: {order_id}")
                    return {
                        "success": True,
                        "message": "订单已取消",
                        "order_id": order_id
                    }
            
            return {
                "success": False,
                "message": "无法取消订单(可能已完成或不存在)"
            }
        except Exception as e:
            logger.exception(f"取消订单时出错: {str(e)}")
            return {
                "success": False,
                "message": f"取消订单异常: {str(e)}"
            }
    
    def get_trade_history(self, limit: int = 50) -> pd.DataFrame:
        """
        获取交易历史
        
        Args:
            limit: 返回记录数
        
        Returns:
            pd.DataFrame: 交易历史DataFrame
        """
        logger.debug(f"获取交易历史，限制: {limit}")
        
        # 创建DataFrame
        if not self.order_history:
            logger.info("无交易历史记录")
            return pd.DataFrame(columns=[
                "timestamp", "type", "size", "price", "order_id", "status", "execution_time"
            ])
        
        # 限制返回数量
        history = self.order_history[-limit:]
        
        # 转换为DataFrame
        df = pd.DataFrame(history)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s')
        df = df.sort_values("timestamp", ascending=False)
        
        # 重命名列
        df = df.rename(columns={
            "timestamp": "时间",
            "type": "类型",
            "size": "数量(DOGE)",
            "price": "价格(USDT)",
            "order_id": "订单ID",
            "status": "状态",
            "execution_time": "执行时间(秒)"
        })
        
        # 选择需要的列
        columns = ["时间", "类型", "数量(DOGE)", "价格(USDT)", "状态"]
        if "执行时间(秒)" in df.columns:
            columns.append("执行时间(秒)")
        
        return df[columns]
