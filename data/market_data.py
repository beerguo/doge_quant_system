"""
市场数据模块 - 从OKX获取狗狗币行情数据

主要功能:
1. 获取实时价格
2. 获取K线数据
3. 获取账户余额
4. 下单交易

注意: 
- 所有API调用都包含签名验证
- 数据缓存机制减少API调用频率
- 错误处理确保系统稳定性
"""

import requests
import time
import hmac
import hashlib
import json
import logging
from datetime import datetime, timedelta
from config.settings import OKX_CONFIG

logger = logging.getLogger(__name__)

class MarketData:
    """
    市场数据类
    
    负责与OKX API交互，获取市场数据和执行交易
    """
    
    def __init__(self):
        """
        初始化市场数据对象
        """
        self.symbol = OKX_CONFIG["symbol"]
        self.base_url = OKX_CONFIG["base_url"]
        self.last_candle_update = 0
        self.candle_cache = {}
        self.price_cache = {"price": 0.0, "timestamp": 0}
        logger.info(f"MarketData已初始化，交易对: {self.symbol}")
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """
        生成OKX API签名
        
        Args:
            timestamp: 时间戳
            method: HTTP方法
            request_path: 请求路径
            body: 请求体(POST请求)
        
        Returns:
            str: 签名字符串
        """
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        mac = hmac.new(
            bytes(OKX_CONFIG["secret_key"], encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        signature = mac.hexdigest()
        logger.debug(f"生成签名: {signature[:10]}... (消息: {message[:50]}...)")
        return signature
    
    def _make_request(self, method: str, endpoint: str, params: dict = None) -> dict:
        """
        发送API请求
        
        Args:
            method: HTTP方法(GET/POST)
            endpoint: API端点
            params: 请求参数
        
        Returns:
            dict: API响应
        """
        timestamp = str(int(time.time() * 1000))
        request_path = f"/api/v5{endpoint}"
        
        # 处理查询参数
        if params and method.upper() == "GET":
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            request_path += f"?{query_string}"
        
        headers = {
            "OK-ACCESS-KEY": OKX_CONFIG["api_key"],
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": OKX_CONFIG["passphrase"],
            "Content-Type": "application/json"
        }
        
        # 为POST请求准备body
        body = ""
        if method.upper() == "POST" and params:
            body = json.dumps(params)
        
        # 生成签名
        headers["OK-ACCESS-SIGN"] = self._generate_signature(timestamp, method, request_path, body)
        
        url = self.base_url + request_path
        logger.debug(f"发送{method}请求: {url}")
        
        try:
            # 发送请求
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params)
            else:
                response = requests.post(url, headers=headers, data=body)
            
            # 检查响应
            response.raise_for_status()
            result = response.json()
            
            # 检查API错误
            if result.get("code") != "0":
                error_msg = f"API错误 [{result.get('code')}]: {result.get('msg', '未知错误')}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.debug(f"API响应: 代码={result.get('code')}, 数据={len(str(result.get('data', '')))}字符")
            return result
        
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败: {str(e)}")
            raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            logger.exception(f"API请求处理失败: {str(e)}")
            raise
    
    def get_current_price(self) -> float:
        """
        获取狗狗币最新价格
        
        Returns:
            float: 最新价格
        """
        # 检查价格缓存(5秒内不重复请求)
        current_time = time.time()
        if current_time - self.price_cache["timestamp"] < 5 and self.price_cache["price"] > 0:
            logger.debug(f"使用价格缓存: {self.price_cache['price']:.6f}")
            return self.price_cache["price"]
        
        endpoint = "/market/ticker"
        params = {"instId": self.symbol}
        
        try:
            response = self._make_request("GET", endpoint, params)
            if response.get("code") == "0" and response.get("data"):
                price = float(response["data"][0]["last"])
                # 更新缓存
                self.price_cache = {"price": price, "timestamp": current_time}
                logger.info(f"获取最新价格: {price:.6f} USDT")
                return price
            else:
                logger.error(f"获取价格失败: {response}")
                raise Exception("无法获取价格数据")
        except Exception as e:
            logger.error(f"获取价格时出错: {str(e)}")
            # 尝试返回旧缓存数据
            if self.price_cache["price"] > 0 and current_time - self.price_cache["timestamp"] < 300:
                logger.warning(f"使用过期价格缓存: {self.price_cache['price']:.6f}")
                return self.price_cache["price"]
            raise
    
    def get_candlesticks(self, timeframe: str = "1H", limit: int = 100) -> list:
        """
        获取K线数据
        
        Args:
            timeframe: 时间周期(1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 1D, 1W, 1M)
            limit: 获取数量
        
        Returns:
            list: K线数据列表
        """
        cache_key = f"{timeframe}_{limit}"
        current_time = time.time()
        
        # 检查缓存
        if (cache_key in self.candle_cache and 
            current_time - self.candle_cache[cache_key]["timestamp"] < 60):
            logger.debug(f"使用K线数据缓存: {cache_key}")
            return self.candle_cache[cache_key]["data"]
        
        endpoint = "/market/candles"
        params = {
            "instId": self.symbol,
            "bar": timeframe,
            "limit": str(limit)
        }
        
        try:
            response = self._make_request("GET", endpoint, params)
            if response.get("code") == "0" and response.get("data"):
                candles = response["data"]
                # 缓存数据
                self.candle_cache[cache_key] = {
                    "timestamp": current_time,
                    "data": candles
                }
                logger.info(f"获取K线数据: {len(candles)} 条 {timeframe} K线")
                return candles
            else:
                logger.error(f"获取K线数据失败: {response}")
                raise Exception("无法获取K线数据")
        except Exception as e:
            logger.error(f"获取K线数据时出错: {str(e)}")
            # 尝试返回缓存数据
            if cache_key in self.candle_cache:
                logger.warning(f"使用过期K线缓存: {cache_key}")
                return self.candle_cache[cache_key]["data"]
            raise
    
    def get_account_balance(self, ccy: str = "DOGE") -> float:
        """
        获取账户余额
        
        Args:
            ccy: 货币类型(DOGE或USDT)
        
        Returns:
            float: 可用余额
        """
        endpoint = "/account/balance"
        params = {"ccy": ccy} if ccy else None
        
        try:
            response = self._make_request("GET", endpoint, params)
            if response.get("code") == "0" and response.get("data"):
                details = response["data"][0]["details"]
                for detail in details:
                    if detail["ccy"] == ccy:
                        balance = float(detail["availBal"])
                        logger.info(f"获取{ccy}余额: {balance:.4f}")
                        return balance
                logger.warning(f"未找到{ccy}余额信息")
                return 0.0
            else:
                logger.error(f"获取{ccy}余额失败: {response}")
                raise Exception(f"无法获取{ccy}余额")
        except Exception as e:
            logger.error(f"获取{ccy}余额时出错: {str(e)}")
            raise
    
    def get_avg_cost(self) -> float:
        """
        获取持仓平均成本
        
        Returns:
            float: 平均成本价格
        """
        endpoint = "/account/positions"
        params = {"instId": self.symbol}
        
        try:
            response = self._make_request("GET", endpoint, params)
            if response.get("code") == "0" and response.get("data"):
                positions = response["data"]
                if positions and float(positions[0]["pos"]) > 0:
                    avg_cost = float(positions[0]["avgPx"])
                    logger.info(f"获取平均成本: {avg_cost:.6f} USDT")
                    return avg_cost
                logger.debug("无持仓或持仓为0")
                return 0.0
            else:
                logger.warning(f"获取持仓信息失败: {response}")
                return 0.0
        except Exception as e:
            logger.error(f"获取平均成本时出错: {str(e)}")
            return 0.0
    
    def place_order(self, side: str, sz: float, ordType: str = "market", px: float = None) -> dict:
        """
        下单交易
        
        Args:
            side: 买卖方向(buy/sell)
            sz: 交易数量
            ordType: 订单类型(market/limit)
            px: 价格(限价单需要)
        
        Returns:
            dict: 订单响应
        """
        logger.info(f"准备下单: {side} {sz} {self.symbol} ({ordType}{' @ ' + str(px) if px else ''})")
        
        # 检查是否为模拟模式
        from config.settings import SYSTEM_CONFIG
        if SYSTEM_CONFIG["simulation_mode"]:
            logger.warning("模拟模式: 不执行实际交易")
            return {
                "code": "0",
                "msg": "模拟模式",
                "data": [{
                    "ordId": f"sim_{int(time.time())}",
                    "clOrdId": "",
                    "tag": ""
                }]
            }
        
        endpoint = "/trade/order"
        params = {
            "instId": self.symbol,
            "tdMode": "cash",  # 现货交易模式
            "side": side,
            "ordType": ordType,
            "sz": str(sz)
        }
        
        if px and ordType in ["limit", "post_only"]:
            params["px"] = str(px)
        
        try:
            response = self._make_request("POST", endpoint, params)
            if response.get("code") == "0":
                order_id = response["data"][0]["ordId"]
                logger.info(f"下单成功: {side} {sz} {self.symbol}, 订单ID: {order_id}")
            else:
                logger.error(f"下单失败: {response}")
            return response
        except Exception as e:
            logger.exception(f"下单时出错: {str(e)}")
            raise
