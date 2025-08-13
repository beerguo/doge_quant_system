"""
推特数据模块 - 获取和分析马斯克的推特消息

主要功能:
1. 获取马斯克最新推文
2. 情感分析
3. 筛选与加密货币相关的内容
4. 提供情绪指标

注意:
- 需要Twitter API Bearer Token
- 使用NLTK的VADER进行情感分析
- 仅关注包含加密货币关键词的推文
"""

import requests
import time
import logging
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from config.settings import TWITTER_CONFIG

logger = logging.getLogger(__name__)

# 确保nltk数据已下载
try:
    nltk.data.find('vader_lexicon')
    logger.debug("已找到nltk vader_lexicon")
except LookupError:
    logger.info("下载nltk vader_lexicon...")
    nltk.download('vader_lexicon')

class TwitterData:
    """
    推特数据类
    
    负责获取和分析马斯克的推特消息
    """
    
    def __init__(self):
        """
        初始化推特数据对象
        """
        self.bearer_token = TWITTER_CONFIG["bearer_token"]
        self.user_id = TWITTER_CONFIG["user_id"]
        self.sia = SentimentIntensityAnalyzer()
        self.last_tweet_id = None
        self.last_check_time = 0
        self.tweet_cache = []
        self.cache_duration = 300  # 5分钟缓存
        self.crypto_keywords = ['doge', 'bitcoin', 'crypto', 'btc', 'eth', 'shib', 'coin', 'blockchain', 'musk']
        
        if TWITTER_CONFIG["enabled"]:
            logger.info(f"TwitterData已初始化，监控用户ID: {self.user_id}")
        else:
            logger.info("Twitter分析已禁用")
    
    def _get_headers(self):
        """
        获取Twitter API请求头
        
        Returns:
            dict: 请求头
        """
        return {"Authorization": f"Bearer {self.bearer_token}"}
    
    def _get_recent_tweets(self, max_results=10):
        """
        获取马斯克最近的推文
        
        Args:
            max_results: 最大返回结果数
        
        Returns:
            dict: Twitter API响应
        """
        url = f"https://api.twitter.com/2/users/{self.user_id}/tweets"
        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,public_metrics,text",
            "exclude": "replies,retweets"
        }
        
        logger.debug(f"获取推特数据: {url} (max_results={max_results})")
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            tweets_data = response.json()
            
            if "data" in tweets_data and tweets_data["data"]:
                logger.info(f"获取到 {len(tweets_data['data'])} 条推文")
                return tweets_data
            else:
                logger.warning("API返回但无推文数据")
                return {"data": []}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"获取推特数据网络错误: {str(e)}")
            if hasattr(self, 'tweet_cache') and self.tweet_cache:
                logger.info("使用缓存推文数据")
                return {"data": self.tweet_cache}
            raise Exception(f"获取推特数据失败: {str(e)}")
        except Exception as e:
            logger.exception(f"获取推特数据处理错误: {str(e)}")
            if hasattr(self, 'tweet_cache') and self.tweet_cache:
                logger.info("使用缓存推文数据")
                return {"data": self.tweet_cache}
            raise Exception(f"处理推特数据失败: {str(e)}")
    
    def analyze_sentiment(self, text: str) -> float:
        """
        分析推文情感
        
        Args:
            text: 推文文本
        
        Returns:
            float: 情感分值(-1到1之间)
        """
        # 检查是否包含加密货币相关关键词
        contains_crypto = any(keyword in text.lower() for keyword in self.crypto_keywords)
        
        if not contains_crypto:
            logger.debug("推文不包含加密货币关键词，情感分设为0")
            return 0.0
        
        # 使用VADER进行情感分析
        sentiment = self.sia.polarity_scores(text)
        compound_score = sentiment['compound']
        
        logger.debug(f"推文情感分析: '{text[:50]}...' -> 分数={compound_score:.2f}")
        return compound_score
    
    def get_latest_sentiment(self) -> float:
        """
        获取最新的情感分析结果
        
        Returns:
            float: 情感分值
        """
        current_time = time.time()
        
        # 检查缓存
        if hasattr(self, 'last_sentiment') and current_time - self.last_check_time < self.cache_duration:
            logger.debug(f"使用推特情感缓存: {self.last_sentiment:.2f}")
            return self.last_sentiment
        
        # 如果Twitter未启用，返回0
        if not TWITTER_CONFIG["enabled"]:
            logger.debug("Twitter分析已禁用，返回0")
            return 0.0
        
        # 如果没有Bearer Token，返回0
        if not self.bearer_token:
            logger.warning("Twitter Bearer Token未配置，无法获取推特数据")
            return 0.0
        
        try:
            tweets_data = self._get_recent_tweets()
            
            if "data" in tweets_data and tweets_data["data"]:
                # 更新缓存
                self.tweet_cache = tweets_data["data"]
                self.last_check_time = current_time
                
                # 分析最新推文
                latest_tweet = tweets_data["data"][0]
                text = latest_tweet["text"]
                sentiment = self.analyze_sentiment(text)
                
                # 检查是否是新推文
                if self.last_tweet_id != latest_tweet["id"]:
                    self.last_tweet_id = latest_tweet["id"]
                    logger.info(f"检测到新推文: {text[:50]}... | 情感分: {sentiment:.2f}")
                
                self.last_sentiment = sentiment
                return sentiment
            else:
                logger.warning("未获取到推特数据")
                return 0.0
        except Exception as e:
            logger.error(f"分析推特情感时出错: {str(e)}")
            return 0.0
    
    def should_consider_twitter(self) -> bool:
        """
        判断是否应该考虑推特情绪
        
        Returns:
            bool: 是否应考虑推特情绪
        """
        # 只有在配置启用、有Bearer Token且最近有相关推文时才考虑
        sentiment = self.get_latest_sentiment()
        should_consider = (TWITTER_CONFIG["enabled"] and 
                          bool(self.bearer_token) and 
                          abs(sentiment) > 0.1)
        
        if should_consider:
            logger.debug(f"考虑推特情绪，情感分: {sentiment:.2f}")
        else:
            logger.debug("不考虑推特情绪")
        
        return should_consider
    
    def get_latest_tweet_info(self):
        """
        获取最新推文信息
        
        Returns:
            dict: 推文信息
        """
        if self.tweet_cache:
            return {
                "text": self.tweet_cache[0]["text"],
                "created_at": self.tweet_cache[0]["created_at"],
                "sentiment": self.get_latest_sentiment()
            }
        return None
