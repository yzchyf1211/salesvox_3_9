"""
时间处理工具函数

提供时间字符串解析、duration计算等功能
"""

from datetime import datetime, timedelta


def parse_time_string(time_str: str) -> datetime:
    """
    解析时间字符串为datetime对象

    支持格式：
    - "HH:MM:SS" (如 "00:00:05")
    - "HH:MM:SS.mmm" (如 "00:00:05.000")

    Args:
        time_str: 时间字符串

    Returns:
        datetime: 解析后的datetime对象（日期部分为1900-01-01）

    Raises:
        ValueError: 时间字符串格式不正确
    """
    try:
        # 处理毫秒部分
        if "." in time_str:
            time_part, ms_part = time_str.split(".")
            # 确保毫秒部分有3位
            ms_part = ms_part.ljust(3, "0")[:3]
            time_str = f"{time_part}.{ms_part}"
            format_str = "%H:%M:%S.%f"
        else:
            format_str = "%H:%M:%S"

        # 解析时间，使用1900-01-01作为基准日期
        base_date = datetime(1900, 1, 1)
        time_obj = datetime.strptime(time_str, format_str).time()
        return datetime.combine(base_date, time_obj)

    except ValueError as e:
        raise ValueError(f"无法解析时间字符串 '{time_str}': {e}")


def calculate_duration(start_time: str, end_time: str) -> timedelta:
    """
    计算两个时间字符串之间的duration

    Args:
        start_time: 开始时间字符串 (如 "00:00:05.000")
        end_time: 结束时间字符串 (如 "00:00:10.500")

    Returns:
        timedelta: 时间差

    Raises:
        ValueError: 时间字符串格式不正确
    """
    start_dt = parse_time_string(start_time)
    end_dt = parse_time_string(end_time)

    # 如果结束时间小于开始时间，说明跨天了
    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    return end_dt - start_dt
