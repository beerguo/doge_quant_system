"""
回测模块 - 评估策略历史表现

主要功能:
1. 获取历史市场数据
2. 模拟交易执行
3. 计算绩效指标
4. 生成可视化报告

回测注意事项:
- 避免未来函数
- 考虑交易成本
- 使用OHLC数据而非收盘价
- 处理数据缺口

绩效指标:
- 总收益率
- 年化收益率
- 夏普比率
- 最大回撤
- 交易胜率
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import logging
from data.market_data import MarketData
from core.config_manager import ConfigManager
from strategies import register_strategies
from core.signal_combiner import SignalCombiner
from core.risk_manager import RiskManager

logger = logging.getLogger(__name__)

class Backtester:
    """
    回测器类
    
    负责策略历史表现的回测和评估
    """
    
    def __init__(self, market_data: MarketData, config_manager: ConfigManager):
        """
        初始化回测器
        
        Args:
            market_data: 市场数据对象
            config_manager: 配置管理器
        """
        self.market_data = market_data
        self.config_manager = config_manager
        self.signal_combiner = SignalCombiner(config_manager)
        self.initial_capital = 1000.0  # 初始资金(USDT)
        self.commission = 0.001  # 0.1%手续费
        logger.info("回测器已初始化")
    
    def _prepare_historical_data(self, start_date: str, end_date: str, timeframe: str = "1H") -> pd.DataFrame:
        """
        准备历史数据用于回测
        
        Args:
            start_date: 开始日期(YYYY-MM-DD)
            end_date: 结束日期(YYYY-MM-DD)
            timeframe: K线周期
        
        Returns:
            pd.DataFrame: 格式化的历史数据
        """
        logger.info(f"准备历史数据: {start_date} 到 {end_date}, 周期={timeframe}")
        
        # 转换日期为时间戳
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
        
        # 获取K线数据(实际实现中应调用API获取指定时间段数据)
        # 这里简化处理，直接获取最近数据
        candles = self.market_data.get_candlesticks(timeframe, 1000)
        
        # 转换为DataFrame
        df = pd.DataFrame(candles, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'other'
        ])
        
        # 转换时间戳
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # 转换数值列
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        # 筛选指定时间段
        start_date = pd.Timestamp(start_date)
        end_date = pd.Timestamp(end_date)
        df = df[(df.index >= start_date) & (df.index <= end_date)]
        
        logger.info(f"获取到 {len(df)} 条历史K线数据")
        return df
    
    def run_backtest(self, start_date: str, end_date: str, initial_capital: float = 1000.0) -> Dict[str, Any]:
        """
        运行回测
        
        Args:
            start_date: 开始日期(YYYY-MM-DD)
            end_date: 结束日期(YYYY-MM-DD)
            initial_capital: 初始资金(USDT)
        
        Returns:
            Dict[str, Any]: 回测结果
        """
        self.initial_capital = initial_capital
        logger.info(f"开始回测: {start_date} 到 {end_date}, 初始资金: {initial_capital} USDT")
        
        # 获取历史数据
        df = self._prepare_historical_data(start_date, end_date)
        if len(df) < 50:
            logger.error(f"历史数据不足，需要至少50条，但只有{len(df)}条")
            raise ValueError("历史数据不足，无法进行回测")
        
        # 准备数据结构
        positions = pd.Series(0, index=df.index)  # 持仓数量(DOGE)
        cash = pd.Series(initial_capital, index=df.index)  # 现金余额(USDT)
        portfolio_value = pd.Series(initial_capital, index=df.index)  # 投资组合总价值
        
        # 模拟交易
        current_position = 0
        current_cash = initial_capital
        trade_log = []
        
        # 注册策略
        strategies = register_strategies(self.market_data, self.config_manager)
        active_strategies = [s.name for s in strategies if s.is_enabled()]
        logger.info(f"回测使用策略: {active_strategies}")
        
        # 用于模拟的MarketData
        class MockMarketData:
            def __init__(self, df, idx):
                self.df = df
                self.idx = idx
                self.symbol = "DOGE-USDT"
            
            def get_current_price(self):
                return self.df['close'].iloc[self.idx]
            
            def get_candlesticks(self, timeframe, limit):
                """返回历史K线数据"""
                start_idx = max(0, self.idx - limit + 1)
                return self.df.iloc[start_idx:self.idx+1][['open', 'high', 'low', 'close', 'volume']].values.tolist()
            
            def get_account_balance(self, ccy="DOGE"):
                return current_position if ccy == "DOGE" else current_cash
            
            def get_avg_cost(self):
                return 0  # 简化实现
        
        # 回测主循环
        for i in range(50, len(df)):  # 从有足够的数据点开始
            timestamp = df.index[i]
            
            # 创建模拟MarketData
            mock_market_data = MockMarketData(df, i)
            
            # 生成策略信号
            strategy_signals = []
            for strategy in strategies:
                if strategy.is_enabled():
                    signal = strategy.generate_signal()
                    signal["strategy"] = strategy.name
                    strategy_signals.append(signal)
            
            # 组合信号
            combined_signal = self.signal_combiner.combine_signals(strategy_signals)
            
            # 检查是否交易
            if self.signal_combiner.should_trade(combined_signal):
                order_type = self.signal_combiner.determine_order_type(combined_signal["final_signal"])
                current_price = df['close'].iloc[i]
                
                # 计算仓位大小
                position_size = self.signal_combiner.calculate_position_size(
                    combined_signal["final_signal"],
                    current_cash + current_position * current_price,
                    current_price
                )
                
                # 执行交易
                if order_type == "buy" and current_cash >= position_size * current_price * (1 + self.commission):
                    # 买入
                    cost = position_size * current_price * (1 + self.commission)
                    current_position += position_size
                    current_cash -= cost
                    
                    # 记录交易
                    trade_log.append({
                        "timestamp": timestamp,
                        "type": "buy",
                        "size": position_size,
                        "price": current_price,
                        "cost": cost,
                        "value": position_size * current_price,
                        "commission": cost * self.commission,
                        "reason": " & ".join(combined_signal["reasons"])
                    })
                    logger.debug(f"回测买入: {position_size:.2f} DOGE @ {current_price:.6f}")
                
                elif order_type == "sell" and current_position >= position_size:
                    # 卖出
                    revenue = position_size * current_price * (1 - self.commission)
                    current_position -= position_size
                    current_cash += revenue
                    
                    # 记录交易
                    trade_log.append({
                        "timestamp": timestamp,
                        "type": "sell",
                        "size": position_size,
                        "price": current_price,
                        "revenue": revenue,
                        "value": position_size * current_price,
                        "commission": position_size * current_price * self.commission,
                        "reason": " & ".join(combined_signal["reasons"])
                    })
                    logger.debug(f"回测卖出: {position_size:.2f} DOGE @ {current_price:.6f}")
            
            # 更新持仓和现金
            positions.iloc[i] = current_position
            cash.iloc[i] = current_cash
            portfolio_value.iloc[i] = current_cash + current_position * df['close'].iloc[i]
        
        # 计算绩效指标
        returns = portfolio_value.pct_change().dropna()
        total_return = (portfolio_value.iloc[-1] / initial_capital - 1) * 100
        num_days = (df.index[-1] - df.index[0]).days
        annualized_return = ((1 + total_return/100) ** (365 / num_days) - 1) * 100 if num_days > 0 else 0
        sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std() if len(returns) > 0 and returns.std() != 0 else 0
        drawdown = (portfolio_value / portfolio_value.cummax() - 1)
        max_drawdown = drawdown.min() * 100
        
        # 计算交易统计
        num_trades = len(trade_log)
        winning_trades = 0
        total_pnl = 0
        
        if num_trades > 0:
            # 计算每笔交易盈亏
            for i in range(1, len(trade_log)):
                if trade_log[i]["type"] == "sell" and trade_log[i-1]["type"] == "buy":
                    buy_price = trade_log[i-1]["price"]
                    sell_price = trade_log[i]["price"]
                    pnl = (sell_price - buy_price) / buy_price * 100
                    total_pnl += pnl
                    if pnl > 0:
                        winning_trades += 1
            
            win_rate = (winning_trades / (num_trades // 2)) * 100 if num_trades > 1 else 0
            avg_return_per_trade = total_pnl / (num_trades // 2) if num_trades > 1 else 0
        else:
            win_rate = 0
            avg_return_per_trade = 0
        
        logger.info(f"回测完成! 总收益率: {total_return:.2f}%, 年化收益率: {annualized_return:.2f}%")
        logger.info(f"夏普比率: {sharpe_ratio:.2f}, 最大回撤: {max_drawdown:.2f}%")
        logger.info(f"交易次数: {num_trades}, 胜率: {win_rate:.2f}%, 平均每笔收益: {avg_return_per_trade:.2f}%")
        
        # 保存结果
        results = {
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "final_value": portfolio_value.iloc[-1],
            "total_return": total_return,
            "annualized_return": annualized_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "avg_return_per_trade": avg_return_per_trade,
            "num_trades": num_trades,
            "positions": positions,
            "cash": cash,
            "portfolio_value": portfolio_value,
            "returns": returns,
            "drawdown": drawdown,
            "trade_log": trade_log,
            "strategy_params": self.config_manager.config
        }
        
        return results
    
    def plot_results(self, results: Dict[str, Any], show_plot: bool = True) -> go.Figure:
        """
        绘制回测结果图表
        
        Args:
            results: 回测结果
            show_plot: 是否显示图表
        
        Returns:
            go.Figure: Plotly图表对象
        """
        logger.info("生成回测结果图表...")
        
        # 创建子图
        fig = go.Figure()
        
        # 投资组合价值
        fig.add_trace(go.Scatter(
            x=results["portfolio_value"].index,
            y=results["portfolio_value"].values,
            mode='lines',
            name='投资组合价值',
            line=dict(color='blue', width=2)
        ))
        
        # 初始资金线
        fig.add_hline(
            y=results["initial_capital"],
            line_dash="dash",
            line_color="red",
            annotation_text="初始资金",
            annotation_position="bottom right"
        )
        
        # 设置布局
        fig.update_layout(
            title=f'投资组合价值 ({results["start_date"]} 到 {results["end_date"]})',
            xaxis_title='日期',
            yaxis_title='价值(USDT)',
            hovermode="x unified",
            template="plotly_white",
            height=500
        )
        
        # 添加绩效指标到图表
        metrics_text = (
            f"总收益率: {results['total_return']:.2f}%<br>"
            f"年化收益率: {results['annualized_return']:.2f}%<br>"
            f"夏普比率: {results['sharpe_ratio']:.2f}<br>"
            f"最大回撤: {results['max_drawdown']:.2f}%<br>"
            f"交易次数: {results['num_trades']}<br>"
            f"胜率: {results['win_rate']:.2f}%"
        )
        
        fig.add_annotation(
            xref="paper", yref="paper",
            x=0.05, y=0.95,
            text=metrics_text,
            showarrow=False,
            bordercolor="black",
            borderwidth=1,
            borderpad=4,
            bgcolor="white",
            opacity=0.8
        )
        
        if show_plot:
            fig.show()
        
        return fig
    
    def plot_drawdown(self, results: Dict[str, Any], show_plot: bool = True) -> go.Figure:
        """
        绘制回撤图表
        
        Args:
            results: 回测结果
            show_plot: 是否显示图表
        
        Returns:
            go.Figure: Plotly图表对象
        """
        logger.info("生成回撤分析图表...")
        
        fig = go.Figure()
        
        # 回撤曲线
        fig.add_trace(go.Scatter(
            x=results["drawdown"].index,
            y=results["drawdown"].values * 100,
            fill='tozeroy',
            mode='lines',
            line_color='red',
            name='回撤(%)'
        ))
        
        # 设置布局
        fig.update_layout(
            title='回撤分析',
            xaxis_title='日期',
            yaxis_title='回撤(%)',
            hovermode="x unified",
            template="plotly_white",
            height=300
        )
        
        # 添加最大回撤标记
        max_drawdown_idx = results["drawdown"].idxmin()
        max_drawdown_val = results["drawdown"].min() * 100
        
        fig.add_annotation(
            x=max_drawdown_idx,
            y=max_drawdown_val,
            text=f"最大回撤: {max_drawdown_val:.2f}%",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor="red",
            ax=0,
            ay=-40
        )
        
        if show_plot:
            fig.show()
        
        return fig
    
    def plot_trades(self, results: Dict[str, Any], show_plot: bool = True) -> go.Figure:
        """
        绘制交易标记图表
        
        Args:
            results: 回测结果
            show_plot: 是否显示图表
        
        Returns:
            go.Figure: Plotly图表对象
        """
        logger.info("生成交易标记图表...")
        
        # 创建基础图表
        fig = go.Figure()
        
        # 添加价格曲线
        fig.add_trace(go.Scatter(
            x=results["portfolio_value"].index,
            y=results["portfolio_value"].index.map(lambda x: results["portfolio_value"].loc[x]),
            mode='lines',
            name='价格',
            line=dict(color='gray', width=1)
        ))
        
        # 添加买入标记
        buy_trades = [t for t in results["trade_log"] if t["type"] == "buy"]
        if buy_trades:
            fig.add_trace(go.Scatter(
                x=[t["timestamp"] for t in buy_trades],
                y=[t["price"] for t in buy_trades],
                mode='markers',
                name='买入',
                marker=dict(
                    symbol='triangle-up',
                    size=10,
                    color='green',
                    line=dict(width=1, color='DarkSlateGrey')
                )
            ))
        
        # 添加卖出标记
        sell_trades = [t for t in results["trade_log"] if t["type"] == "sell"]
        if sell_trades:
            fig.add_trace(go.Scatter(
                x=[t["timestamp"] for t in sell_trades],
                y=[t["price"] for t in sell_trades],
                mode='markers',
                name='卖出',
                marker=dict(
                    symbol='triangle-down',
                    size=10,
                    color='red',
                    line=dict(width=1, color='DarkSlateGrey')
                )
            ))
        
        # 设置布局
        fig.update_layout(
            title='交易标记',
            xaxis_title='日期',
            yaxis_title='价格(USDT)',
            hovermode="x unified",
            template="plotly_white",
            height=400
        )
        
        if show_plot:
            fig.show()
        
        return fig
