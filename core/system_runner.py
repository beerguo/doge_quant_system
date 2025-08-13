"""
系统运行器模块 - 主交易循环

本模块提供:
1. 交易系统主循环
2. 信号生成与执行
3. 系统监控
4. 异常处理

运行流程:
1. 初始化系统组件
2. 检查系统状态
3. 生成交易信号
4. 执行交易决策
5. 记录交易日志
6. 等待下一次检查

注意: 这是系统的核心运行模块，负责实际交易执行
"""

import time
import logging
from datetime import datetime
from data.market_data import MarketData
from core.config_manager import ConfigManager
from core.risk_manager import RiskManager
from core.signal_combiner import SignalCombiner
from strategies import register_strategies
from execution.order_executor import OrderExecutor
from config.settings import SYSTEM_CONFIG

logger = logging.getLogger(__name__)

def run_trading_system():
    """运行交易系统主循环"""
    logger.info("===== 交易系统启动 =====")
    logger.info("按 Ctrl+C 停止系统")
    
    try:
        # 初始化组件
        market_data = MarketData()
        config_manager = ConfigManager()
        risk_manager = RiskManager(market_data, config_manager)
        signal_combiner = SignalCombiner(config_manager)
        order_executor = OrderExecutor(market_data, risk_manager)
        
        # 注册策略
        strategies = register_strategies(market_data, config_manager)
        active_strategies = [s.name for s in strategies if s.is_enabled()]
        logger.info(f"已加载 {len(strategies)} 个策略, {len(active_strategies)} 个策略已启用: {active_strategies}")
        
        # 主交易循环
        while True:
            start_time = time.time()
            logger.info("\n" + "="*50)
            logger.info(f"交易检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 更新风险指标
            risk_manager.update_metrics()
            risk_metrics = risk_manager.get_risk_metrics()
            
            # 检查是否应停止交易
            if risk_metrics["should_stop"]:
                logger.warning(f"达到最大日亏损限制({risk_metrics['daily_loss_percent']:.2f}%), 暂停交易")
                time.sleep(SYSTEM_CONFIG["check_interval"])
                continue
            
            # 获取当前价格
            try:
                current_price = market_data.get_current_price()
                logger.info(f"当前{OKX_CONFIG['symbol']}价格: {current_price:.6f} USDT")
            except Exception as e:
                logger.error(f"获取价格失败: {str(e)}")
                time.sleep(60)
                continue
            
            # 生成策略信号
            strategy_signals = []
            for strategy in strategies:
                if strategy.is_enabled():
                    signal = strategy.generate_signal()
                    strategy_signals.append(signal)
                    logger.info(f"{strategy.name}信号: {signal['signal']} (置信度: {signal['confidence']:.2f}) - {signal['reason']}")
            
            # 组合信号
            combined_signal = signal_combiner.combine_signals(strategy_signals)
            logger.info(f"综合信号: {combined_signal['final_signal']:.2f} (置信度: {combined_signal['confidence']:.2f})")
            
            # 检查是否交易
            if signal_combiner.should_trade(combined_signal):
                order_type = signal_combiner.determine_order_type(combined_signal["final_signal"])
                account_value = risk_metrics["account_value"]
                
                # 计算仓位大小
                position_size = signal_combiner.calculate_position_size(
                    combined_signal["final_signal"],
                    account_value,
                    current_price
                )
                
                logger.info(f"交易决策: {order_type.upper()} {position_size:.2f} DOGE")
                
                # 执行交易
                result = order_executor.execute_order(order_type, position_size)
                if result["success"]:
                    logger.info(f"交易执行成功: {result['message']}")
                else:
                    logger.error(f"交易执行失败: {result['message']}")
            else:
                logger.info("未达到交易条件，不执行交易")
            
            # 打印风险指标
            logger.info(f"账户价值: {risk_metrics['account_value']:.2f} USDT")
            logger.info(f"当日盈亏: {risk_metrics['daily_pnl']:.2f} USDT ({risk_metrics['daily_loss_percent']:.2f}%)")
            
            # 等待下一次检查
            elapsed = time.time() - start_time
            sleep_time = max(0, SYSTEM_CONFIG["check_interval"] - elapsed)
            logger.info(f"等待 {sleep_time:.1f} 秒后进行下一次检查...")
            time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        logger.info("系统已手动停止")
    except Exception as e:
        logger.exception(f"系统运行时出错: {str(e)}")
        # 可以在这里添加错误通知逻辑
