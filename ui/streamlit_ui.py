"""
Streamlit UI界面 - 用于配置和监控量化交易系统

本模块提供:
1. 直观的Web界面
2. 策略配置面板
3. 风险管理面板
4. Twitter监控面板
5. 回测分析面板
6. 系统状态监控

设计特点:
- 响应式布局
- 实时数据更新
- 交互式图表
- 模块化设计
- 用户友好界面
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import time
import json
import os
from datetime import datetime, timedelta
from core.config_manager import ConfigManager
from data.market_data import MarketData
from data.twitter_data import TwitterData
from core.risk_manager import RiskManager
from core.signal_combiner import SignalCombiner
from strategies import register_strategies
from backtesting.backtester import Backtester
from execution.order_executor import OrderExecutor
from config.settings import OKX_CONFIG, SYSTEM_CONFIG, STRATEGY_WEIGHTS
import logging

# 配置页面
st.set_page_config(
    page_title="狗狗币量化交易系统",
    page_icon="🐶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
def load_css():
    """加载自定义CSS样式"""
    st.markdown("""
    <style>
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #1f77b4;
    }
    .metric-label {
        font-size: 14px;
        color: #666;
    }
    .strategy-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
        background-color: white;
    }
    .active-strategy {
        border-left: 4px solid #1f77b4;
    }
    .inactive-strategy {
        border-left: 4px solid #ccc;
    }
    .twitter-positive {
        background-color: #e6f7ff;
        border-left: 4px solid #1890ff;
    }
    .twitter-negative {
        background-color: #fff7e6;
        border-left: 4px solid #faad14;
    }
    .trading-active {
        color: #52c41a;
        font-weight: bold;
    }
    .trading-inactive {
        color: #f5222d;
        font-weight: bold;
    }
    .log-entry {
        padding: 5px 0;
        border-bottom: 1px solid #eee;
    }
    .log-info {
        color: #1890ff;
    }
    .log-warning {
        color: #faad14;
    }
    .log-error {
        color: #f5222d;
    }
    .stButton>button {
        border-radius: 8px;
        height: 40px;
    }
    .stSlider>div>div>div {
        background-color: #1f77b4;
    }
    </style>
    """, unsafe_allow_html=True)

# 初始化系统组件
def init_system():
    """初始化系统组件"""
    # 检查配置有效性
    from config.settings import validate_config
    is_valid, error_msg = validate_config()
    if not is_valid:
        st.error(f"系统配置错误: {error_msg}")
        st.stop()
    
    # 初始化MarketData
    if 'market_data' not in st.session_state:
        try:
            st.session_state.market_data = MarketData()
        except Exception as e:
            st.error(f"初始化MarketData失败: {str(e)}")
            st.stop()
    
    # 初始化ConfigManager
    if 'config_manager' not in st.session_state:
        try:
            st.session_state.config_manager = ConfigManager()
        except Exception as e:
            st.error(f"初始化ConfigManager失败: {str(e)}")
            st.stop()
    
    # 初始化TwitterData (如果启用)
    if 'twitter_data' not in st.session_state and SYSTEM_CONFIG["TWITTER_CONFIG"]["enabled"]:
        if SYSTEM_CONFIG["TWITTER_CONFIG"]["bearer_token"]:
            try:
                st.session_state.twitter_data = TwitterData()
            except Exception as e:
                st.warning(f"初始化TwitterData失败: {str(e)}")
    
    # 注册策略
    if 'strategies' not in st.session_state:
        twitter_data = st.session_state.get('twitter_data', None)
        try:
            st.session_state.strategies = register_strategies(
                st.session_state.market_data, 
                st.session_state.config_manager,
                twitter_data
            )
        except Exception as e:
            st.error(f"注册策略失败: {str(e)}")
            st.stop()
    
    # 初始化RiskManager
    if 'risk_manager' not in st.session_state:
        try:
            st.session_state.risk_manager = RiskManager(
                st.session_state.market_data,
                st.session_state.config_manager
            )
        except Exception as e:
            st.error(f"初始化RiskManager失败: {str(e)}")
            st.stop()
    
    # 初始化OrderExecutor
    if 'order_executor' not in st.session_state:
        try:
            st.session_state.order_executor = OrderExecutor(
                st.session_state.market_data,
                st.session_state.risk_manager
            )
        except Exception as e:
            st.error(f"初始化OrderExecutor失败: {str(e)}")
            st.stop()
    
    # 系统状态
    if 'system_running' not in st.session_state:
        st.session_state.system_running = False
    
    # 交易历史
    if 'trade_history' not in st.session_state:
        st.session_state.trade_history = []
    
    # 系统日志
    if 'system_log' not in st.session_state:
        st.session_state.system_log = []
    
    # 当前价格
    if 'current_price' not in st.session_state:
        try:
            st.session_state.current_price = st.session_state.market_data.get_current_price()
        except Exception as e:
            st.warning(f"获取价格失败: {str(e)}")
            st.session_state.current_price = 0.0
    
    # 账户价值
    if 'account_value' not in st.session_state:
        try:
            st.session_state.account_value = st.session_state.risk_manager._get_current_balance()
        except Exception as e:
            st.warning(f"获取账户价值失败: {str(e)}")
            st.session_state.account_value = 0.0
    
    # 系统指标刷新时间
    if 'last_metrics_update' not in st.session_state:
        st.session_state.last_metrics_update = time.time()
    
    # 系统自动刷新
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True
    
    # 刷新间隔
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 15

# 更新系统指标
def update_system_metrics():
    """更新系统指标"""
    try:
        # 更新价格
        st.session_state.current_price = st.session_state.market_data.get_current_price()
        
        # 更新风险指标
        st.session_state.risk_manager.update_metrics()
        
        # 更新账户价值
        st.session_state.account_value = st.session_state.risk_manager._get_current_balance()
        
        # 记录最后更新时间
        st.session_state.last_metrics_update = time.time()
        
        return True
    except Exception as e:
        st.session_state.system_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": "ERROR",
            "message": f"更新系统指标失败: {str(e)}"
        })
        return False

# 显示系统状态
def display_system_status():
    """显示系统状态面板"""
    st.subheader("系统状态")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{:.6f} USDT</div>
            <div class="metric-label">当前DOGE价格</div>
        </div>
        """.format(st.session_state.current_price), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{:.2f} USDT</div>
            <div class="metric-label">账户总价值</div>
        </div>
        """.format(st.session_state.account_value), unsafe_allow_html=True)
    
    with col3:
        risk_metrics = st.session_state.risk_manager.get_risk_metrics()
        daily_loss = risk_metrics["daily_loss_percent"]
        color = "red" if daily_loss > 0 else "green"
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value" style="color: {};">{:.2f}%</div>
            <div class="metric-label">当日盈亏</div>
        </div>
        """.format(color, daily_loss), unsafe_allow_html=True)
    
    with col4:
        status = "运行中" if st.session_state.system_running else "已停止"
        status_class = "trading-active" if st.session_state.system_running else "trading-inactive"
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value"><span class="{}">{}</span></div>
            <div class="metric-label">交易系统状态</div>
        </div>
        """.format(status_class, status), unsafe_allow_html=True)
    
    # 系统控制按钮
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    if col1.button("启动交易系统", use_container_width=True, type="primary"):
        st.session_state.system_running = True
        st.success("交易系统已启动!")
        st.rerun()
    
    if col2.button("停止交易系统", use_container_width=True):
        st.session_state.system_running = False
        st.warning("交易系统已停止!")
        st.rerun()
    
    if col3.button("刷新数据", use_container_width=True):
        update_system_metrics()
        st.success("数据已刷新!")
        st.rerun()
    
    if col4.button("清空日志", use_container_width=True):
        st.session_state.system_log = []
        st.info("日志已清空!")
        st.rerun()
    
    # 显示最近交易
    st.subheader("最近交易")
    trade_history = st.session_state.order_executor.get_trade_history(5)
    
    if not trade_history.empty:
        st.dataframe(trade_history, hide_index=True, use_container_width=True)
    else:
        st.info("暂无交易记录")
    
    # 显示系统指标历史图表
    st.subheader("系统指标历史")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 创建模拟指标历史数据
        hours = list(range(24))
        pnl_values = [st.session_state.risk_manager.get_risk_metrics()["daily_pnl"] * (i/24) for i in hours]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hours, y=pnl_values, mode='lines', name='盈亏'))
        fig.update_layout(
            title='24小时盈亏变化', 
            xaxis_title='小时前', 
            yaxis_title='盈亏(USDT)',
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # 创建模拟持仓历史数据
        position_values = [st.session_state.market_data.get_account_balance() * (i/24) for i in hours]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hours, y=position_values, mode='lines', name='持仓'))
        fig.update_layout(
            title='24小时持仓变化', 
            xaxis_title='小时前', 
            yaxis_title='持仓(DOGE)',
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)

# 策略配置面板
def strategy_config_panel():
    """策略配置面板"""
    st.subheader("交易策略配置")
    
    # 获取所有策略配置
    config = st.session_state.config_manager.config
    active_strategies = config["active_strategies"]
    
    # 策略启用/禁用
    st.markdown("#### 策略启用状态")
    
    for strategy in st.session_state.strategies:
        col1, col2, col3 = st.columns([3, 2, 1])
        
        # 策略卡片样式
        card_class = "active-strategy" if strategy.name in active_strategies else "inactive-strategy"
        
        with col1:
            st.markdown(f'<div class="strategy-card {card_class}">', unsafe_allow_html=True)
            st.markdown(f"**{strategy.name.replace('_', ' ').title()}**")
            st.caption("点击切换策略状态")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            # 策略权重
            weight = STRATEGY_WEIGHTS.get(strategy.name, 0.25)
            new_weight = st.slider(
                f"权重", 
                min_value=0.0, 
                max_value=1.0, 
                value=float(weight), 
                step=0.05,
                key=f"weight_{strategy.name}"
            )
            # 保存权重 (实际应用中应有保存机制)
        
        with col3:
            # 切换策略状态
            is_active = strategy.name in active_strategies
            if st.toggle("", value=is_active, key=f"toggle_{strategy.name}"):
                if strategy.name not in active_strategies:
                    active_strategies.append(strategy.name)
            else:
                if strategy.name in active_strategies:
                    active_strategies.remove(strategy.name)
    
    # 保存配置
    if st.button("保存策略配置", type="primary", use_container_width=True):
        st.session_state.config_manager.config["active_strategies"] = active_strategies
        st.success("策略配置已保存!")
        st.rerun()
    
    # 策略参数详细配置
    st.markdown("#### 策略参数设置")
    
    for strategy in st.session_state.strategies:
        if strategy.name not in active_strategies:
            continue
        
        with st.expander(f"{strategy.name.replace('_', ' ').title()} 参数设置", expanded=True):
            params = st.session_state.config_manager.get_strategy_config(strategy.name)
            
            if strategy.name == "bollinger":
                col1, col2 = st.columns(2)
                with col1:
                    params["period"] = st.number_input("周期", min_value=5, max_value=50, 
                                                    value=params.get("period", 20), key=f"b_period_{strategy.name}")
                    params["std_dev"] = st.number_input("标准差倍数", min_value=1.0, max_value=3.0, 
                                                      value=params.get("std_dev", 2.0), step=0.1, key=f"b_std_{strategy.name}")
                with col2:
                    params["buy_threshold"] = st.number_input("买入阈值", min_value=0.1, max_value=0.9, 
                                                           value=params.get("buy_threshold", 0.3), step=0.05, key=f"b_buy_{strategy.name}")
                    params["sell_threshold"] = st.number_input("卖出阈值", min_value=0.1, max_value=0.9, 
                                                            value=params.get("sell_threshold", 0.7), step=0.05, key=f"b_sell_{strategy.name}")
            
            elif strategy.name == "breakout":
                col1, col2 = st.columns(2)
                with col1:
                    params["atr_period"] = st.number_input("ATR周期", min_value=5, max_value=30, 
                                                        value=params.get("atr_period", 14), key=f"bo_atr_{strategy.name}")
                    params["volume_factor"] = st.number_input("成交量因子", min_value=1.0, max_value=3.0, 
                                                           value=params.get("volume_factor", 1.5), step=0.1, key=f"bo_vol_{strategy.name}")
                with col2:
                    params["breakout_factor"] = st.number_input("突破因子", min_value=1.0, max_value=3.0, 
                                                             value=params.get("breakout_factor", 1.5), step=0.1, key=f"bo_break_{strategy.name}")
            
            elif strategy.name == "multi_timeframe":
                col1, col2 = st.columns(2)
                with col1:
                    params["daily_sma_fast"] = st.number_input("日线快SMA", min_value=10, max_value=100, 
                                                            value=params.get("daily_sma_fast", 50), key=f"mt_fast_{strategy.name}")
                    params["rsi_period"] = st.number_input("RSI周期", min_value=5, max_value=30, 
                                                         value=params.get("rsi_period", 14), key=f"mt_rsi_{strategy.name}")
                with col2:
                    params["daily_sma_slow"] = st.number_input("日线慢SMA", min_value=50, max_value=200, 
                                                            value=params.get("daily_sma_slow", 200), key=f"mt_slow_{strategy.name}")
                    params["rsi_oversold"] = st.number_input("RSI超卖", min_value=10, max_value=40, 
                                                          value=params.get("rsi_oversold", 35), key=f"mt_oversold_{strategy.name}")
                    params["rsi_overbought"] = st.number_input("RSI超买", min_value=60, max_value=90, 
                                                             value=params.get("rsi_overbought", 70), key=f"mt_overbought_{strategy.name}")
            
            elif strategy.name == "twitter_sentiment":
                col1, col2 = st.columns(2)
                with col1:
                    params["positive_threshold"] = st.number_input("正面情绪阈值", min_value=0.0, max_value=1.0, 
                                                                value=params.get("positive_threshold", 0.6), step=0.05, key=f"tw_pos_{strategy.name}")
                    params["influence_factor"] = st.number_input("影响因子", min_value=0.5, max_value=3.0, 
                                                              value=params.get("influence_factor", 1.5), step=0.1, key=f"tw_inf_{strategy.name}")
                with col2:
                    params["negative_threshold"] = st.number_input("负面情绪阈值", min_value=-1.0, max_value=0.0, 
                                                                value=params.get("negative_threshold", -0.4), step=0.05, key=f"tw_neg_{strategy.name}")
            
            # 保存策略参数
            if st.button(f"保存{strategy.name}参数", key=f"save_{strategy.name}"):
                st.session_state.config_manager.config["strategy_params"][strategy.name] = params
                st.success(f"{strategy.name}参数已保存!")
                st.rerun()

# 风险管理面板
def risk_management_panel():
    """风险管理面板"""
    st.subheader("风险管理配置")
    
    # 获取当前风险配置
    risk_config = st.session_state.config_manager.config["risk_management"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 仓位管理")
        risk_config["max_position_percent"] = st.slider(
            "最大单笔仓位(%)", 
            min_value=1.0, 
            max_value=20.0, 
            value=float(risk_config.get("max_position_percent", 5.0)), 
            step=0.5
        )
        risk_config["max_daily_loss"] = st.slider(
            "最大日亏损(%)", 
            min_value=1.0, 
            max_value=10.0, 
            value=float(risk_config.get("max_daily_loss", 3.0)), 
            step=0.5
        )
    
    with col2:
        st.markdown("#### 止损止盈")
        risk_config["stop_loss_percent"] = st.slider(
            "止损百分比(%)", 
            min_value=1.0, 
            max_value=10.0, 
            value=float(risk_config.get("stop_loss_percent", 5.0)), 
            step=0.5
        )
        risk_config["take_profit_ratio"] = st.slider(
            "止盈比例", 
            min_value=1.0, 
            max_value=5.0, 
            value=float(risk_config.get("take_profit_ratio", 2.0)), 
            step=0.1
        )
    
    # 保存风险配置
    if st.button("保存风险管理配置", type="primary", use_container_width=True):
        st.session_state.config_manager.update_risk_params(risk_config)
        st.success("风险管理配置已保存!")
        st.rerun()
    
    # 显示风险指标
    st.markdown("#### 当前风险指标")
    risk_metrics = st.session_state.risk_manager.get_risk_metrics()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("账户总价值", f"${risk_metrics['account_value']:.2f} USDT")
    
    with col2:
        color = "red" if risk_metrics["daily_loss_percent"] > 0 else "green"
        st.metric("当日盈亏", 
                 f"{risk_metrics['daily_loss_percent']:.2f}%", 
                 delta=f"{risk_metrics['daily_pnl']:.2f} USDT",
                 delta_color="inverse" if risk_metrics["daily_pnl"] < 0 else "normal")
    
    with col3:
        st.metric("是否应停止交易", 
                 "是" if risk_metrics["should_stop"] else "否",
                 help="当达到最大日亏损限制时应停止交易")
    
    # 风险指标图表
    st.markdown("#### 风险指标历史")
    
    # 这里应显示历史风险指标图表
    # 为简化，我们模拟一些数据
    dates = [datetime.now() - timedelta(hours=i) for i in range(24, 0, -1)]
    pnl_values = [risk_metrics["daily_pnl"] * (i/24) for i in range(24)]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=pnl_values, mode='lines', name='盈亏'))
    fig.update_layout(title='24小时盈亏变化', xaxis_title='时间', yaxis_title='盈亏(USDT)', height=300)
    st.plotly_chart(fig, use_container_width=True)

# Twitter监控面板
def twitter_monitor_panel():
    """Twitter监控面板"""
    st.subheader("马斯克推特监控")
    
    # 检查Twitter数据是否可用
    if 'twitter_data' not in st.session_state:
        st.warning("Twitter监控未启用或配置不完整")
        st.info("""
        要启用Twitter监控，请设置以下环境变量:
        - TWITTER_BEARER_TOKEN: 您的Twitter API Bearer Token
        - TWITTER_ANALYSIS_ENABLED: true
        """)
        return
    
    # 获取最新推特情绪
    sentiment = st.session_state.twitter_data.get_latest_sentiment()
    tweet_info = st.session_state.twitter_data.get_latest_tweet_info()
    
    # 显示情绪分析结果
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 情绪仪表盘
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=sentiment,
            title={'text': "情绪分析"},
            gauge={'axis': {'range': [-1, 1]},
                   'bar': {'color': "darkblue"},
                   'steps': [
                       {'range': [-1, -0.4], 'color': "red"},
                       {'range': [-0.4, 0.6], 'color': "yellow"},
                       {'range': [0.6, 1], 'color': "green"}],
                   'threshold': {
                       'line': {'color': "black", 'width': 4},
                       'thickness': 0.75,
                       'value': sentiment}}))
        
        fig.update_layout(height=250)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # 情绪历史图表
        st.markdown("**情绪趋势 (最近24小时)**")
        # 模拟数据
        hours = list(range(24))
        sentiments = [sentiment * (1 - abs(h-12)/12) for h in hours]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hours, y=sentiments, mode='lines', name='情绪'))
        fig.update_layout(xaxis_title='小时前', yaxis_title='情绪值', height=200)
        st.plotly_chart(fig, use_container_width=True)
    
    with col3:
        # 情绪影响
        st.markdown("**情绪影响**")
        if sentiment > 0.6:
            st.success("强烈看多信号")
            st.info("考虑增加买入信号权重")
        elif sentiment > 0:
            st.info("轻微看多信号")
            st.info("可能强化其他买入信号")
        elif sentiment < -0.4:
            st.error("强烈看空信号")
            st.info("考虑增加卖出信号权重")
        else:
            st.warning("轻微看空信号")
            st.info("可能弱化买入信号")
    
    # 显示最新推文
    if tweet_info:
        tweet_class = "twitter-positive" if sentiment > 0 else "twitter-negative"
        st.markdown(f'<div class="strategy-card {tweet_class}">', unsafe_allow_html=True)
        st.markdown(f"**最新推文 ({datetime.strptime(tweet_info["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d %H:%M")})**")
        st.write(tweet_info["text"])
        
        # 显示情感分析详情
        st.markdown(f"**情感分析**: {sentiment:.2f} "
                   f"({'正面' if sentiment > 0 else '负面'})")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Twitter配置
    st.markdown("#### Twitter监控配置")
    config = st.session_state.config_manager.get_strategy_config("twitter_sentiment")
    
    col1, col2 = st.columns(2)
    with col1:
        config["positive_threshold"] = st.slider(
            "正面情绪阈值", 
            min_value=0.0, 
            max_value=1.0, 
            value=config.get("positive_threshold", 0.6),
            step=0.05
        )
        config["influence_factor"] = st.slider(
            "影响因子", 
            min_value=0.5, 
            max_value=3.0, 
            value=config.get("influence_factor", 1.5),
            step=0.1
        )
    
    with col2:
        config["negative_threshold"] = st.slider(
            "负面情绪阈值", 
            min_value=-1.0, 
            max_value=0.0, 
            value=config.get("negative_threshold", -0.4),
            step=0.05
        )
    
    if st.button("保存Twitter配置", type="primary", use_container_width=True):
        st.session_state.config_manager.config["strategy_params"]["twitter_sentiment"] = config
        st.success("Twitter配置已保存!")
        st.rerun()

# 回测面板
def backtest_panel():
    """回测面板"""
    st.subheader("策略回测")
    
    st.info("""
    回测功能允许您使用历史数据测试交易策略表现。
    通过调整参数，您可以找到最适合当前市场条件的配置。
    """)
    
    # 回测参数设置
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input("回测开始日期", 
                                 value=datetime.now() - timedelta(days=90))
        initial_capital = st.number_input("初始资金(USDT)", 
                                        min_value=100.0, 
                                        value=1000.0, 
                                        step=100.0)
    
    with col2:
        end_date = st.date_input("回测结束日期", 
                               value=datetime.now())
        # 确保结束日期不早于开始日期
        if end_date < start_date:
            end_date = start_date
            st.warning("结束日期不能早于开始日期，已自动调整")
    
    # 选择要回测的策略
    st.markdown("#### 选择回测策略")
    strategies = st.session_state.strategies
    selected_strategies = []
    
    cols = st.columns(4)
    for i, strategy in enumerate(strategies):
        with cols[i % 4]:
            is_selected = st.checkbox(strategy.name.replace('_', ' ').title(), 
                                   value=True,
                                   key=f"backtest_{strategy.name}")
            if is_selected:
                selected_strategies.append(strategy.name)
    
    if not selected_strategies:
        st.warning("请至少选择一个策略进行回测")
        return
    
    # 运行回测按钮
    if st.button("运行回测", type="primary", use_container_width=True):
        with st.spinner("正在运行回测，请稍候..."):
            # 创建回测器
            backtester = Backtester(
                st.session_state.market_data,
                st.session_state.config_manager
            )
            
            # 运行回测
            results = backtester.run_backtest(
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                initial_capital
            )
            
            # 保存回测结果到session state
            st.session_state.backtest_results = results
            
            st.success("回测完成!")
    
    # 显示回测结果
    if 'backtest_results' in st.session_state:
        results = st.session_state.backtest_results
        
        # 绩效指标
        st.markdown("#### 回测绩效指标")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("总收益率", f"{results['total_return']:.2f}%")
        
        with col2:
            st.metric("年化收益率", f"{results['annualized_return']:.2f}%")
        
        with col3:
            st.metric("夏普比率", f"{results['sharpe_ratio']:.2f}")
        
        with col4:
            st.metric("最大回撤", f"{results['max_drawdown']:.2f}%")
        
        # 投资组合价值图表
        st.markdown("#### 投资组合价值变化")
        fig = backtester.plot_results(results, show_plot=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # 回撤图表
        st.markdown("#### 回撤分析")
        fig = backtester.plot_drawdown(results, show_plot=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # 交易详情
        st.markdown("#### 交易详情")
        if results["trade_log"]:
            trade_df = pd.DataFrame(results["trade_log"])
            trade_df["timestamp"] = pd.to_datetime(trade_df["timestamp"])
            trade_df = trade_df.sort_values("timestamp", ascending=False)
            
            # 重命名列
            trade_df = trade_df.rename(columns={
                "timestamp": "时间",
                "type": "类型",
                "size": "数量(DOGE)",
                "price": "价格(USDT)",
                "reason": "原因"
            })
            
            # 选择需要的列
            columns = ["时间", "类型", "数量(DOGE)", "价格(USDT)", "原因"]
            st.dataframe(trade_df[columns], hide_index=True, use_container_width=True)
        else:
            st.info("回测期间无交易")

# 系统日志面板
def system_log_panel():
    """系统日志面板"""
    st.subheader("系统日志")
    
    # 日志筛选
    log_level = st.selectbox("日志级别", ["全部", "错误", "警告", "信息", "调试"])
    
    # 日志显示区域
    log_container = st.container(height=300)
    
    with log_container:
        # 按时间倒序显示日志
        for log in reversed(st.session_state.system_log):
            if log_level == "全部" or log["level"] == log_level:
                level_class = "log-" + log["level"].lower()
                st.markdown(f'<div class="log-entry {level_class}">[{log["time"]}] [{log["level"]}] {log["message"]}</div>', 
                          unsafe_allow_html=True)
    
    # 日志控制
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("清空日志", use_container_width=True):
            st.session_state.system_log = []
            st.rerun()

# 主界面函数
def main_ui():
    """主界面函数"""
    load_css()
    
    # 初始化系统
    init_system()
    
    # 侧边栏
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/en/d/d0/Dogecoin_Logo.png", width=150)
        st.title("🐶 狗狗币量化交易系统")
        
        # 系统信息
        st.markdown("---")
        st.markdown("**系统信息**")
        st.write(f"当前版本: 1.0.0")
        st.write(f"交易对: {OKX_CONFIG['symbol']}")
        
        # 系统状态
        st.markdown("---")
        st.markdown("**系统状态**")
        status_color = "🟢" if st.session_state.system_running else "🔴"
        st.write(f"{status_color} 系统运行: {'运行中' if st.session_state.system_running else '已停止'}")
        
        # 系统设置
        st.markdown("---")
        st.markdown("**系统设置**")
        st.session_state.auto_refresh = st.toggle("自动刷新", value=st.session_state.auto_refresh)
        st.session_state.refresh_interval = st.slider("刷新间隔(秒)", 5, 60, st.session_state.refresh_interval)
    
    # 主内容区域
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "系统概览", 
        "策略配置", 
        "风险管理", 
        "Twitter监控", 
        "回测分析"
    ])
    
    with tab1:
        display_system_status()
    
    with tab2:
        strategy_config_panel()
    
    with tab3:
        risk_management_panel()
    
    with tab4:
        twitter_monitor_panel()
    
    with tab5:
        backtest_panel()
    
    # 系统日志始终显示在底部
    system_log_panel()
    
    # 自动刷新功能
    if st.session_state.auto_refresh:
        time.sleep(st.session_state.refresh_interval)
        st.rerun()

# 运行Streamlit应用
def run_streamlit_ui():
    """运行Streamlit UI"""
    try:
        main_ui()
    except Exception as e:
        st.error(f"界面发生错误: {str(e)}")
        st.exception(e)

if __name__ == "__main__":
    run_streamlit_ui()
