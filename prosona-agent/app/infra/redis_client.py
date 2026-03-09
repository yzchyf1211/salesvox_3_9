# -*- coding: utf-8 -*-
import asyncio
import functools
import json
import logging
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from json import JSONDecodeError
from typing import Dict, Any, Callable, Union

from agentickit.core.utils import config_util

logger = logging.getLogger()

from redis import Redis as SyncRedis
from redis.asyncio import Redis as AsyncRedis
from redis.cluster import RedisCluster as SyncRedisCluster
from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster
from redis.connection import ConnectionPool as SyncConnectionPool
from redis.asyncio.connection import ConnectionPool as AsyncConnectionPool
from redis.connection import SSLConnection as SyncSSLConnection
from redis.asyncio.connection import SSLConnection as AsyncSSLConnection
from typing import Optional, Any


# 定义一个线程本地存储
thread_local = threading.local()

class RedisClient:
    """
    Redis 客户端封装，支持单节点模式和集群模式
    
    Args:
        host: Redis 主机地址
        port: Redis 端口
        db: 数据库索引（仅单节点模式有效，集群模式忽略此参数）
        password: 密码
        max_connections: 最大连接数
        decode_responses: 是否自动解码响应
        socket_timeout: 连接超时时间
        use_ssl: 是否使用 SSL/TLS
        cluster_mode: 是否启用集群模式（用于 AWS ElastiCache Redis Cluster 等）
    """
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 32,
        decode_responses: bool = True,
        socket_timeout: float = 5.0,
        use_ssl: bool = False,
        cluster_mode: bool = False,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.max_connections = max_connections
        self.decode_responses = decode_responses
        self.socket_timeout = socket_timeout
        self.use_ssl = use_ssl
        self.cluster_mode = cluster_mode
        
        # 用于存储连接池（仅单节点模式）
        self.sync_pool = None
        self.async_pool = None
        
        if cluster_mode:
            # ===== Redis Cluster 模式 =====
            # 集群模式会自动发现所有节点并处理 MOVED/ASK 重定向
            logger.info(f"初始化 Redis Cluster 客户端: {host}:{port}, ssl={use_ssl}")
            
            cluster_kwargs = dict(
                host=host,
                port=port,
                password=password,
                decode_responses=decode_responses,
                socket_connect_timeout=socket_timeout,
                ssl=use_ssl,
            )
            
            # 同步集群客户端
            self.sync_client: Union[SyncRedis, SyncRedisCluster] = SyncRedisCluster(**cluster_kwargs)
            
            # 异步集群客户端
            self.async_client: Union[AsyncRedis, AsyncRedisCluster] = AsyncRedisCluster(**cluster_kwargs)
        else:
            # ===== 单节点模式 =====
            logger.info(f"初始化 Redis 单节点客户端: {host}:{port}, ssl={use_ssl}")
            
            # 同步连接池和客户端（TLS/SSL）
            # 注意：redis-py 不支持在 ConnectionPool 里传 ssl=True，否则会透传给 AbstractConnection 触发报错。
            # 正确方式是使用 SSLConnection 作为 connection_class。
            sync_pool_kwargs = dict(
                host=host,
                port=port,
                db=db,
                password=password,
                max_connections=max_connections,
                decode_responses=decode_responses,
                socket_connect_timeout=socket_timeout,
                socket_timeout=socket_timeout,
        )
            if use_ssl:
                sync_pool_kwargs["connection_class"] = SyncSSLConnection

            self.sync_pool = SyncConnectionPool(**sync_pool_kwargs)
            self.sync_client: Union[SyncRedis, SyncRedisCluster] = SyncRedis(connection_pool=self.sync_pool)

            # 异步连接池和客户端（TLS/SSL）
            async_pool_kwargs = dict(
                host=host,
                port=port,
                db=db,
                password=password,
                max_connections=max_connections,
                decode_responses=decode_responses,
                socket_connect_timeout=socket_timeout,
                socket_timeout=socket_timeout,
        )
            if use_ssl:
                async_pool_kwargs["connection_class"] = AsyncSSLConnection

            self.async_pool = AsyncConnectionPool(**async_pool_kwargs)
            self.async_client: Union[AsyncRedis, AsyncRedisCluster] = AsyncRedis(connection_pool=self.async_pool)

    # ======================
    # 同步方法
    # ======================
    def get(self, key: str) -> Any:
        return self.sync_client.get(key)

    def set(self, key: str, value: Any, ex: int = None) -> bool:
        return self.sync_client.set(key, value, ex=ex)

    def delete(self, *keys) -> int:
        return self.sync_client.delete(*keys)

    # ======================
    # 异步方法
    # ======================
    async def aget(self, key: str) -> Any:
        return await self.async_client.get(key)

    async def aset(self, key: str, value: Any, ex: int = None) -> bool:
        return await self.async_client.set(key, value, ex=ex)

    async def adelete(self, *keys) -> int:
        return await self.async_client.delete(*keys)

    # ======================
    # 工具方法
    # ======================
    def ping(self) -> bool:
        return self.sync_client.ping()

    async def ping_async(self) -> bool:
        return await self.async_client.ping()

    def close(self):
        if self.cluster_mode:
            self.sync_client.close()
        elif self.sync_pool:
            self.sync_pool.disconnect()

    async def close_async(self):
        await self.async_client.close()
        if not self.cluster_mode and self.async_pool:
            await self.async_pool.disconnect()


# get thread redis client
def get_redis_client(namespace=None, default_ttl=120):
    if not hasattr(thread_local, "redis_client"):
        # redis_ssl：true 启用 TLS/SSL；false（或缺省）使用普通连接
        raw_ssl = config_util.get_config("redis", "redis_ssl", "false")
        ssl_enabled = str(raw_ssl).strip().lower() in {"1", "true", "yes", "y", "on"}
        logger.info(
            f"RedisClient init: host={config_util.get_config('redis','redis_host','')}, "
            f"port={config_util.get_config('redis','redis_port','')}, db={config_util.get_config('redis','redis_db','')}, "
            f"use_ssl={ssl_enabled}"
        )
        
        # redis_cluster_mode：true 启用集群模式（用于 AWS ElastiCache Redis Cluster）
        raw_cluster = config_util.get_config("redis", "redis_cluster_mode", "false")
        cluster_enabled = str(raw_cluster).strip().lower() in {"1", "true", "yes", "y", "on"}
        
        # ✅ 每个线程第一次调用时创建自己的实例
        thread_local.redis_client = RedisClient(
            host=config_util.get_config("redis", "redis_host", ""),
            port=int(config_util.get_config("redis", "redis_port", "")),
            db=int(config_util.get_config("redis", "redis_db", "0")),
            password=config_util.get_config("redis", "redis_password", ""),
            max_connections=int(config_util.get_config("redis", "redis_max_connections", "20")),
            use_ssl=ssl_enabled,
            cluster_mode=cluster_enabled,
        )
    return thread_local.redis_client


# Redis Stream 队列定义
class RedisStreamQueue:
    def __init__(self, redis_tool: AsyncRedis,
                 stream_key: str = "drill:stream",
                 group_name: str = "drill-group",
                 dlq_stream: str = "drill:dlq",  # 死信队列
                 max_retry: int = 3):
        self.redis = redis_tool
        self.stream_key = stream_key
        self.group_name = group_name
        self.consumer_name: Optional[str] = None
        self.dlq_stream = dlq_stream
        self.max_retry = max_retry

    async def initialize(self):
        """创建消费者组（如果不存在）"""
        try:
            await self.redis.xgroup_create(
                name=self.stream_key,
                groupname=self.group_name,
                id="$",  # 从最后开始
                mkstream=True,
            )
            logger.info(f"✅ 消费者组 '{self.group_name}' 已创建或已存在")
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"❌ 创建消费者组失败: {e}")

    async def produce(self, message: Dict[str, Any], stream_key: str = None) -> str:
        """生产消息到 Redis Stream
        :param message: 要发送的数据（会自动 JSON 序列化）
        :param stream_key: 指定 stream key（可选）
        :return: 消息 ID
        """
        try:
            # 序列化
            body = json.dumps({
                "task": message["task"],
                "args": message["args"],
                "kwargs": message["kwargs"],
                "data_id": message.get("data_id", str(uuid.uuid4())),
                "timestamp": datetime.now().isoformat(),
                "retry_count": message.get("retry_count", 0)
            })
            # 写入 Stream
            msg_id = await self.redis.xadd(self.stream_key, {"data": body})
            logger.info(f"消息已入队 | task={message['task']} | msg_id={msg_id} | id={message.get('data_id')}")
            return msg_id
        except Exception as e:
            if str(e).__contains__('is bound to a different event loop') or str(e).__contains__(
                    'attached to a different loop'):
                logger.warning(f"消息入队失败: {e}")
            else:
                logger.error(f"消息入队失败: {e}")
                raise


    # 在 consume 方法中，处理消息时查找注册的任务
    async def consume(
            self,
            handler: Callable = None,  # 可选：自定义 handler
            consumer_name: str = "worker",
            block: int = 1000,
            auto_ack: bool = True,
    ):
        """
        消费消息，支持：
        - 自定义 handler
        - 自动调用 @task 注册的函数
        """
        self.consumer_name = consumer_name
        logger.info(f"👂 消费者 '{consumer_name}' 开始监听流: {self.stream_key}")

        while True:
            try:
                response = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=consumer_name,
                    streams={self.stream_key: ">"},
                    count=1,
                    block=block,
                )

                if not response:
                    continue

                for stream, messages in response:
                    for msg_id, raw_data in messages:
                        task_name = ''
                        try:
                            if 'body' in raw_data:
                                message = json.loads(raw_data["body"])
                            else:
                                message = json.loads(raw_data["data"])
                            task_name = message["task"]
                            args = message.get("args", ())
                            kwargs = message.get("kwargs", {})

                            logger.info(f"📩 执行任务: {task_name}({args}, {kwargs})")

                            # 查找任务
                            func = _task_registry.get(task_name)
                            if not func:
                                raise ValueError(f"任务未注册: {task_name}")

                            result = func(*args, **kwargs)
                            logger.info(f"📩 执行任务 prepare")
                            if asyncio.iscoroutine(result):
                                logger.info(f"📩 执行任务 start")
                                await result
                            logger.info(f"📩 执行任务 finished: {task_name}, result: {result}")

                            if auto_ack:
                                _background_loop = asyncio.get_running_loop()
                                if _background_loop:
                                    # _background_loop.run_until_complete(self.redis.xack(self.stream_key, self.group_name, msg_id))
                                    await self.redis.xack(self.stream_key, self.group_name, msg_id)
                        except JSONDecodeError as je:
                            logger.warning(f"❌ 执行任务失败 JSONDecodeError  {task_name}: {je}, give up message")
                            if auto_ack:
                                await self.redis.xack(self.stream_key, self.group_name, msg_id)
                        except Exception as e:
                            if str(e).__contains__('is bound to a different event loop') or str(e).__contains__('attached to a different loop'):
                                logger.warning(f" 执行任务失败 {task_name}: {e}")
                            else:
                                logger.warning(f"❌ 执行任务失败 {task_name}: {e}")
                                await self._handle_failure(msg_id, raw_data, int(raw_data.get("retry_count", "0")), e)
            except Exception as e:
                logger.error(f"❌ 消费错误: {e}")
                await asyncio.sleep(1)


    async def _handle_failure(self, msg_id: str, raw_data: dict, retry_count: int, e: Exception):
        """处理失败消息：重试或进入死信队列"""
        retry_count += 1
        if retry_count < self.max_retry:
            # 重新入队（可加延迟）
            new_msg = {
                **raw_data,
                "retry_count": str(retry_count),
                "failed_at": asyncio.get_event_loop().time(),
            }
            await self.redis.xadd(self.stream_key, new_msg)
            logger.warning(f"🔁 消息 {msg_id} 重试 {retry_count}/{self.max_retry}")
        else:
            # 进入死信队列
            await self.redis.xadd(
                self.dlq_stream,
                {"original_id": msg_id, "data": raw_data["data"], "final_error": str(e)},
            )
            await self.redis.xack(self.stream_key, self.group_name, msg_id)
            logger.error(f"💀 消息 {msg_id} 达到最大重试次数，已进入死信队列")


# 全局队列实例（由外部设置）
_redis_client: RedisClient = None
_task_queue: RedisStreamQueue = None

def set_task_queue(redis: RedisClient, queue: RedisStreamQueue):
    global _task_queue
    global _redis_client
    global redis_client
    _task_queue = queue
    _redis_client = redis
    redis_client = redis

def get_task_queue() -> tuple[RedisClient, RedisStreamQueue]:
    global  _redis_client, _task_queue
    if _task_queue is None:
        # 从配置创建
        _redis_client = thread_local.redis_client
        _task_queue = RedisStreamQueue(
            redis_tool=_redis_client.async_client,
            stream_key="drill:stream",
            group_name="drill-group",
            dlq_stream="drill:dlq",
            max_retry=2,
        )
        set_task_queue(_redis_client, _task_queue)
    return _redis_client, _task_queue

def queue_task(func: Callable) -> Callable:
    """
    Celery 风格的 @queue_task 装饰器
    支持普通函数和 async 函数
    """
    #if not _task_queue:
    #    raise RuntimeError("未设置任务队列实例，请先调用 set_task_queue()")

    # 生成任务名
    task_name = f"{func.__module__}.{func.__name__}"

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        return await func(*args, **kwargs)

    def delay(*args, **kwargs) -> asyncio.Task:
        """
        异步提交任务
        :return: asyncio.Task（非 awaitable，仅表示已提交）
        """
        if not _task_queue:
            raise RuntimeError("任务队列未初始化")

        # 构造消息体
        message = {
            "task": task_name,
            "args": args,
            "kwargs": kwargs,
        }

        # 提交到 Redis Stream
        asyncio.create_task(_task_queue.produce(message))
        return None  # delay 不返回结果

    #async def apply_async(args=None, kwargs=None, **options) -> None:
    async def apply_async(*args, **kwargs) -> None:
        """
        更灵活的异步提交（支持 options，如 delay、countdown 等）
        """
        args = args or ()
        kwargs = kwargs or {}
        # 支持简单延迟（示例）
        countdown = kwargs.get("countdown", 0)
        if countdown > 0:
            await asyncio.sleep(countdown)
        await _task_queue.produce({
            "task": task_name,
            "args": args,
            "kwargs": kwargs,
        })

    # 绑定 delay 和 apply_async
    if asyncio.iscoroutinefunction(func):
        wrapper = async_wrapper
    else:
        wrapper = sync_wrapper

    wrapper.delay = delay
    wrapper.apply_async = apply_async
    wrapper._is_task = True
    wrapper.task_name = task_name

    # 注册到队列（可选：用于自动发现）
    _task_registry[task_name] = func

    return wrapper

# 任务注册表（用于消费者查找）
_task_registry: Dict[str, Callable] = {}


# ======================
# 便捷函数（供 handler 使用）
# ======================

def redis_get(key: str) -> Optional[str]:
    client = get_redis_client()
    if not client:
        return None
    try:
        return client.get(key)
    except Exception as e:
        logger.warning(f"[redis_get] Redis GET failed for {key}: {e}")
        return None


def redis_set(key: str, value: str, ex: Optional[int] = None) -> bool:
    client = get_redis_client()
    if not client:
        return False
    try:
        client.set(key, value, ex=ex)
        return True
    except Exception as e:
        logger.warning(f"[redis_set] Redis SET failed for {key}: {e}")
        return False


def redis_append_json_list(key: str, items: list, ex: Optional[int] = None) -> bool:
    """Append items to a JSON list stored in Redis."""
    client = get_redis_client()
    if not client:
        return False
    try:
        existing_json = client.get(key) or "[]"
        existing = json.loads(existing_json)
        existing.extend(items)
        client.set(key, json.dumps(existing, ensure_ascii=False), ex=ex)
        return True
    except Exception as e:
        logger.warning(f"[redis_append_json_list] Failed for {key}: {e}")
        return False
