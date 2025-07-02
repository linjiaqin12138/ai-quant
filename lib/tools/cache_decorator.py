# d:\Project\quant\lib\tools\cache_decorator.py
import functools
import json
from datetime import datetime, timedelta
from typing import Callable, Any, Optional, TypeVar, ParamSpec
import inspect

P = ParamSpec("P")
R = TypeVar("R")

from lib.logger import logger
from lib.adapter.database import create_transaction
from lib.adapter.database.kv_store import Value

# 内存缓存存储
# 结构: {cache_key: (data, expire_time)}
memory_cache: dict[str, tuple[Any, datetime]] = {}


def generate_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """
    根据函数及其参数生成一个唯一的、可重复的缓存键。
    尝试使用JSON序列化参数，如果失败则使用repr。
    """
    try:
        # 绑定参数到签名以处理默认值和名称
        sig = inspect.signature(func)
        bound_args = sig.bind_partial(
            *args, **kwargs
        )  # Use bind_partial before apply_defaults
        bound_args.apply_defaults()
        # 创建一个包含函数限定名和排序后参数的列表
        key_parts = [func.__module__, func.__qualname__]
        for k, v in sorted(bound_args.arguments.items()):
            if k == "self":  # 会导致key的名字中出现地址，每次运行都不一样
                continue
            try:
                # 对值进行JSON序列化以获得稳定表示
                # sort_keys确保字典顺序一致
                arg_repr = json.dumps(
                    v, sort_keys=True, default=str
                )  # default=str处理datetime等
            except TypeError:
                # 如果JSON序列化失败，回退到repr
                arg_repr = repr(v)
            key_parts.append(f"{k}={arg_repr}")
        # 使用不太可能出现在repr中的分隔符连接各部分
        return "||".join(key_parts)
    except Exception as e:
        logger.error(
            f"Error generating cache key for {func.__name__}: {e}", exc_info=True
        )
        # 回退到不太可靠但总能工作的键
        return f"{func.__module__}.{func.__qualname__}:{repr(args)}:{repr(kwargs)}"


def use_cache(
    ttl_seconds: int,
    use_db_cache: bool = False,
    key_prefix: str = "cache",
    serializer: Optional[Callable[[Any], Value]] = None,
    deserializer: Optional[Callable[[Value], Any]] = None,
    key_generator: Callable[[Callable, tuple, dict], str] = generate_cache_key,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    一个装饰器，用于在内存和（可选）数据库键值存储中缓存函数结果。

    Args:
        ttl_seconds: 缓存条目的生存时间（秒）。
        use_db_cache: 是否使用数据库键值存储作为二级缓存。
                      需要 `create_transaction` 可用。
        key_prefix: 添加到数据库缓存键的前缀。
        key_generator: 用于从函数和参数生成缓存键的函数。
                       默认为使用函数名和参数的生成器。
        serializer: 在存储前序列化结果的函数（默认为JSON）。
                    对于复杂类型（如pandas DataFrame），可能需要自定义：
                    例: serializer=lambda df: df.to_json(orient='split')
        deserializer: 在检索后反序列化结果的函数（默认为JSON）。
                      对于复杂类型（如pandas DataFrame），可能需要自定义：
                      例: deserializer=lambda s: pd.read_json(s, orient='split')
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal use_db_cache  # 允许修改闭包中的use_db_cache
            now = datetime.now()
            cache_key = key_generator(func, args, kwargs)
            db_cache_key = f"{key_prefix}:{cache_key}"

            # 1. 检查内存缓存
            if cache_key in memory_cache:
                data, expire_time = memory_cache[cache_key]
                if expire_time > now:
                    logger.debug(f"Cache HIT (Memory): {cache_key}")
                    return data
                else:
                    logger.debug(f"Cache EXPIRED (Memory): {cache_key}")
                    del memory_cache[cache_key]  # 删除过期条目

            # 2. 检查数据库缓存 (如果启用且可用)
            if use_db_cache:
                try:
                    with create_transaction() as db:
                        cached_dict = db.kv_store.get(db_cache_key)
                        if cached_dict is not None:
                            try:
                                # 假设数据库存储 {'data_serialized': str | dict, 'expire_time': isoformat}
                                expire_time_iso = cached_dict.get("expire_time")
                                data_serialized = cached_dict.get("data_serialized")

                                if expire_time_iso and data_serialized:
                                    expire_time = datetime.fromisoformat(
                                        expire_time_iso
                                    )
                                    if expire_time > now:
                                        logger.debug(f"Cache HIT (DB): {db_cache_key}")
                                        result = (
                                            deserializer(data_serialized)
                                            if deserializer
                                            else data_serialized
                                        )
                                        # 更新内存缓存
                                        memory_cache[cache_key] = (result, expire_time)
                                        return result
                                    else:
                                        logger.debug(
                                            f"Cache EXPIRED (DB): {db_cache_key}"
                                        )
                                        db.kv_store.delete(db_cache_key)
                                        db.commit()
                                else:
                                    logger.warning(
                                        f"Cache CORRUPT (DB - missing fields): {db_cache_key}"
                                    )

                            except (json.JSONDecodeError, TypeError, ValueError) as e:
                                logger.error(
                                    f"Cache ERROR (DB Deserialize): {db_cache_key} - {e}",
                                    exc_info=True,
                                )
                                # 记录错误，视为缓存未命中
                except Exception as db_err:
                    logger.error(
                        f"Database error during cache check for {db_cache_key}: {db_err}",
                        exc_info=True,
                    )
                    # 如果数据库访问失败，暂时禁用该调用的数据库缓存
                    # 注意：这里修改 use_db_cache 只影响当前调用，不会持久影响装饰器配置
                    # 如果希望永久禁用，需要更复杂的逻辑或外部配置
                    pass  # 允许在DB错误时继续执行函数

            # 3. 缓存未命中 - 执行函数
            logger.debug(f"Cache MISS: {cache_key}. Executing function {func.__name__}")
            try:
                result = func(*args, **kwargs)
            except Exception as func_exc:
                logger.error(
                    f"Error executing decorated function {func.__name__}: {func_exc}",
                    exc_info=True,
                )
                raise  # 重新抛出异常，缓存不应隐藏执行错误

            # 4. 更新缓存
            expire_time = now + timedelta(seconds=ttl_seconds)

            # 更新内存缓存
            # 对于不可变结果可以直接存储，对于可变结果（如列表/字典）
            # 如果担心它们在缓存后被修改，应考虑存储其深拷贝 copy.deepcopy(result)
            memory_cache[cache_key] = (result, expire_time)
            logger.debug(f"Cache SET (Memory): {cache_key}")

            # 更新数据库缓存 (如果启用且可用)
            if use_db_cache:
                try:
                    serialized_result = serializer(result) if serializer else result
                    cache_data_to_store = {
                        "data_serialized": serialized_result,
                        "expire_time": expire_time.isoformat(),
                    }
                    with create_transaction() as db:
                        db.kv_store.set(db_cache_key, cache_data_to_store)
                        db.commit()  # 重要：提交事务
                        logger.debug(f"Cache SET (DB): {db_cache_key}")
                except Exception as e:
                    logger.error(
                        f"Cache ERROR (DB Serialize/Set): {db_cache_key} - {e}",
                        exc_info=True,
                    )
                    # 记录错误，但继续而不更新数据库缓存

            return result

        return wrapper

    return decorator


# 示例用法 (注释掉，因为这是库文件):
# @use_cache(ttl_seconds=300, use_db_cache=True)
# def fetch_some_data(param1: str, param2: int = 10):
#     print(f"Executing fetch_some_data with {param1}, {param2}")
#     # 模拟耗时操作
#     import time
#     time.sleep(1)
#     return {"result": f"Data for {param1}-{param2}", "timestamp": datetime.now()}

# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG)
#     # 假设数据库已设置并可用
#     print("First call:")
#     data1 = fetch_some_data("test", param2=20)
#     print(data1)
#     print("\nSecond call (should hit cache):")
#     data2 = fetch_some_data("test", param2=20)
#     print(data2)
#     print("\nThird call (different args):")
#     data3 = fetch_some_data("another_test")
#     print(data3)
