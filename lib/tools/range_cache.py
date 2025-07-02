import functools
import inspect
import json  # Added for stable key generation
from datetime import datetime
from typing import Callable, Any, Optional, List, Tuple, Dict, TypeVar

from lib.logger import logger
from lib.utils.time import dt_to_ts, ts_to_dt
from lib.adapter.lock import with_lock
from lib.adapter.database import create_transaction, DbTransaction

# Removed: from lib.tools.cache_decorator import generate_cache_key as default_key_generator

# Define a generic type for remote fetch data typee
T = TypeVar("T")

# Define types for the injected functions
# Metadata structure stored in the KV store (Simplified: only query_range)
CacheMetadata = Dict[str, List[int]]  # e.g., {'query_range': [start_ts, end_ts]}
GetCacheDataFunc = Callable[
    [DbTransaction, datetime, datetime], List[T]
]  # Function to get actual data items from cache storage
StoreDataFunc = Callable[
    [DbTransaction, List[T]], None
]  # Function to store actual data items
# Removed: KeyGeneratorFunc = Callable[[Callable, tuple, dict], str]


def _generate_range_cache_key(
    func: Callable, bound_args: inspect.BoundArguments, key_param_names: List[str]
) -> str:
    """
    Generates a cache key based on the function and specified parameter values.
    """
    try:
        # key_parts = [func.__module__, func.__qualname__]
        key_parts = []
        arguments = bound_args.arguments
        for name in sorted(key_param_names):  # Sort names for consistency
            if name in arguments:
                value = arguments[name]
                try:
                    # Use JSON dumps for stable representation of values
                    arg_repr = json.dumps(value, sort_keys=True, default=str)
                except TypeError:
                    arg_repr = repr(value)  # Fallback to repr
                key_parts.append(f"{name}={arg_repr}")
            else:
                # Handle case where a specified key parameter might not be present
                # (e.g., if it has a default and wasn't provided)
                # This might indicate an issue with the key_param_names list or function call
                logger.warning(
                    f"Key parameter '{name}' not found in arguments for {func.__qualname__}. Skipping."
                )
                key_parts.append(f"{name}=<NOT_FOUND>")  # Indicate missing param in key

        return "||".join(key_parts)
    except Exception as e:
        logger.error(
            f"Error generating range cache key for {func.__name__}: {e}", exc_info=True
        )
        # Fallback key using repr of specified args only
        fallback_parts = [func.__module__, func.__qualname__]
        for name in sorted(key_param_names):
            if name in arguments:
                fallback_parts.append(f"{name}={repr(arguments[name])}")
            else:
                fallback_parts.append(f"{name}=<NOT_FOUND>")
        return "||".join(fallback_parts)


def use_range_cache(
    get_data_by_cache: GetCacheDataFunc,
    store_data: StoreDataFunc,
    key_param_names: List[str],  # Changed from key_generator
    metadata_key_suffix: str = "::metadata",  # Suffix for the metadata key in KV store
    lock_key_suffix: str = "::lock",  # Suffix for the lock key
):
    """
    Decorator for caching functions that query data within a datetime range.

    Manages cache metadata (query range only) internally using the database
    key-value store. It fetches missing data around the cached query range
    if the requested range is not fully covered. Uses a lock to prevent
    race conditions during cache updates.

    The cache key is generated based on the function and the values of parameters
    specified in `key_param_names`.

    Assumes the decorated function has 'start: datetime' and 'end: datetime' parameters.

    Args:
        get_data_by_cache: Function to retrieve cached data items for the *original requested range*
                           after ensuring the range is cached.
        store_data: Function to store newly fetched data items within a DB transaction.
        key_param_names: A list of parameter names from the decorated function whose values
                         will be used to generate the cache key. Excludes 'start' and 'end'.
        metadata_key_suffix: Suffix appended to the base key to create the metadata storage key.
        lock_key_suffix: Suffix appended to the base key to create the lock key.
    """

    def decorator(func: Callable[..., List[T]]) -> Callable[..., List[T]]:
        sig = inspect.signature(func)
        # Validate key_param_names against function signature (excluding start/end)
        valid_params = set(sig.parameters.keys()) - {"start", "end"}
        for name in key_param_names:
            if name not in valid_params:
                raise TypeError(
                    f"key_param_name '{name}' is not a valid parameter of function {func.__name__} (excluding start/end)"
                )
        if "start" not in sig.parameters or "end" not in sig.parameters:
            raise TypeError(
                f"Decorated function {func.__name__} must accept 'start' and 'end' arguments."
            )
        if (
            sig.parameters["start"].annotation != datetime
            or sig.parameters["end"].annotation != datetime
        ):
            logger.warning(
                f"Parameters 'start' and 'end' in {func.__name__} should preferably be annotated with datetime."
            )

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> List[T]:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            start: datetime = bound_args.arguments["start"]
            end: datetime = bound_args.arguments["end"]
            start_ts = dt_to_ts(start)
            end_ts = dt_to_ts(end)

            if start_ts >= end_ts:
                raise ValueError("Start time must be before end time.")

            # Generate cache key using specified parameters
            base_key = _generate_range_cache_key(
                func, bound_args, key_param_names
            )  # Use the new helper
            metadata_key = f"{base_key}{metadata_key_suffix}"
            lock_key = f"{base_key}{lock_key_suffix}"  # Generate lock key
            logger.debug(
                f"Range cache check. Base key: {base_key}, Metadata key: {metadata_key}, Lock key: {lock_key}, Range: [{start}, {end})"
            )

            # --- Read Phase (Outside Lock) ---
            # ... (rest of the read phase code remains the same) ...
            metadata: Optional[CacheMetadata] = None
            try:
                with create_transaction() as db:
                    metadata = db.kv_store.get(metadata_key)
                    # 1. Check if cache fully covers the requested range (Read-only check)
                    if (
                        metadata
                        and metadata.get("query_range")
                        and metadata["query_range"][0] <= start_ts
                        and end_ts <= metadata["query_range"][1]
                    ):
                        logger.info(
                            f"Range cache HIT (Full - outside lock check): {base_key} for range [{start}, {end})"
                        )
                        return get_data_by_cache(db, start, end)
            except Exception as e:
                logger.warning(
                    f"Failed to read metadata outside lock for {metadata_key}: {e}. Proceeding to lock.",
                    exc_info=True,
                )

            logger.info(
                f"Range cache MISS or PARTIAL HIT or read failure: {base_key}. Acquiring lock for potential fetch."
            )

            @with_lock(
                lock_key, max_concurrent_access=1, timeout=300, expiration_time=300
            )
            def fetch_and_cache_with_lock():
                # ... (rest of the fetch_and_cache_with_lock function remains the same) ...
                with create_transaction() as db:
                    try:
                        metadata = db.kv_store.get(metadata_key)
                    except Exception as e:
                        logger.error(
                            f"Failed to read metadata *inside lock* for {metadata_key}: {e}. Assuming no cache.",
                            exc_info=True,
                        )
                        metadata = None

                    # Re-check coverage inside the lock
                    if (
                        metadata
                        and metadata.get("query_range")
                        and metadata["query_range"][0] <= start_ts
                        and end_ts <= metadata["query_range"][1]
                    ):
                        logger.info(
                            f"Range cache HIT (Full) *inside lock*: {base_key} for range [{start}, {end})"
                        )
                        # Pass db only if expected by the function
                        return get_data_by_cache(db, start, end)

                    logger.info(
                        f"Range cache MISS or PARTIAL HIT *inside lock*: {base_key}. Proceeding with fetch."
                    )

                    # 2. Determine range(s) to fetch based only on query_range
                    fetch_ranges: List[Tuple[datetime, datetime]] = []
                    current_metadata = (
                        metadata if metadata and "query_range" in metadata else None
                    )
                    # Initialize new_metadata based on current request if no cache exists
                    new_metadata: CacheMetadata = (
                        current_metadata.copy()
                        if current_metadata
                        else {"query_range": [start_ts, end_ts]}
                    )
                    target_query_range_start = start_ts
                    target_query_range_end = end_ts

                    if current_metadata is None:
                        logger.info(
                            f"No valid cache metadata found inside lock. Fetching initial range [{start}, {end})."
                        )
                        fetch_ranges.append((start, end))
                        # new_metadata is already set correctly
                    else:
                        cached_query_start_ts, cached_query_end_ts = current_metadata[
                            "query_range"
                        ]
                        target_query_range_start = min(start_ts, cached_query_start_ts)
                        target_query_range_end = max(end_ts, cached_query_end_ts)

                        # Fetch before cached range if needed
                        if start_ts < cached_query_start_ts:
                            fetch_start = start
                            fetch_end = ts_to_dt(cached_query_start_ts)
                            logger.info(
                                f"Fetching data before cache: [{fetch_start}, {fetch_end})"
                            )
                            fetch_ranges.append((fetch_start, fetch_end))

                        # Fetch after cached range if needed
                        if end_ts > cached_query_end_ts:
                            fetch_start = ts_to_dt(cached_query_end_ts)
                            fetch_end = end
                            logger.info(
                                f"Fetching data after cache: [{fetch_start}, {fetch_end})"
                            )
                            fetch_ranges.append((fetch_start, fetch_end))

                        # Update the query range in metadata to reflect the target range
                        new_metadata["query_range"] = [
                            int(target_query_range_start),
                            int(target_query_range_end),
                        ]  # Ensure int

                    for fr_start, fr_end in fetch_ranges:
                        logger.debug(
                            f"Calling original function {func.__name__} for range [{fr_start}, {fr_end})"
                        )
                        try:
                            # 修改原始函数的start和end参数为当前范围
                            call_kwargs = bound_args.arguments.copy()
                            call_kwargs["start"] = fr_start
                            call_kwargs["end"] = fr_end
                            current_new_data: List[T] = func(
                                **call_kwargs
                            )  # Call the original decorated function

                            if current_new_data:
                                logger.debug(
                                    f"Storing {len(current_new_data)} new items fetched for range [{fr_start}, {fr_end})."
                                )
                                store_data(db, current_new_data)  # Store fetched data
                            else:
                                logger.debug(
                                    f"No data returned by original function for range [{fr_start}, {fr_end})."
                                )

                        except Exception as e:
                            logger.error(
                                f"Error calling original function {func.__name__} or storing data for range [{fr_start}, {fr_end}): {e}",
                                exc_info=True,
                            )
                            # Rollback transaction and re-raise? Or just log and potentially leave cache inconsistent?
                            db.rollback()  # Rollback on error during fetch/store
                            raise  # Re-raise within lock

                    # 4. Update metadata KV store if necessary

                    logger.info(
                        f"Updating metadata for key {metadata_key} to {new_metadata} (inside lock)"
                    )
                    db.kv_store.set(metadata_key, new_metadata)

                    # Commit transaction if everything succeeded
                    db.commit()

                    # 5. Return data for the originally requested range (still inside lock)
                    logger.debug(
                        f"Retrieving final data for range [{start}, {end}) from cache via get_data_by_cache (inside lock)."
                    )
                    return get_data_by_cache(db, start, end)

            # Call the inner function that holds the lock logic
            return fetch_and_cache_with_lock()

        return wrapper

    return decorator
