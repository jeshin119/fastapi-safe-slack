from datetime import date, datetime, timedelta
from typing import Optional
from app.core.exception_utils import raise_invalid_date_format


def get_current_date() -> date:
    """
    현재 날짜를 반환합니다.
    
    Returns:
        date: 현재 날짜
    """
    return date.today()


def get_current_datetime() -> datetime:
    """
    현재 날짜와 시간을 반환합니다.
    
    Returns:
        datetime: 현재 날짜와 시간
    """
    return datetime.now()


def get_current_datetime_utc() -> datetime:
    """
    현재 UTC 날짜와 시간을 반환합니다.
    
    Returns:
        datetime: 현재 UTC 날짜와 시간
    """
    return datetime.utcnow()


def is_date_valid(date_str: str) -> bool:
    """
    날짜 문자열이 유효한지 확인합니다.
    
    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD 형식)
        
    Returns:
        bool: 유효한 경우 True
    """
    try:
        date.fromisoformat(date_str)
        return True
    except ValueError:
        return False


def parse_date(date_str: str) -> date:
    """
    날짜 문자열을 date 객체로 변환합니다.
    
    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD 형식)
        
    Returns:
        date: 날짜 객체
        
    Raises:
        HTTPException: 날짜 형식이 유효하지 않은 경우
    """
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise_invalid_date_format()


def parse_datetime(datetime_str: str) -> datetime:
    """
    날짜시간 문자열을 datetime 객체로 변환합니다.
    
    Args:
        datetime_str: 날짜시간 문자열 (ISO 형식)
        
    Returns:
        datetime: 날짜시간 객체
        
    Raises:
        HTTPException: 날짜시간 형식이 유효하지 않은 경우
    """
    try:
        return datetime.fromisoformat(datetime_str)
    except ValueError:
        raise_invalid_date_format()


def is_date_range_valid(start_date: date, end_date: date) -> bool:
    """
    날짜 범위가 유효한지 확인합니다.
    
    Args:
        start_date: 시작 날짜
        end_date: 종료 날짜
        
    Returns:
        bool: 시작 날짜가 종료 날짜보다 이전인 경우 True
    """
    return start_date <= end_date


def is_date_in_range(target_date: date, start_date: Optional[date], end_date: Optional[date]) -> bool:
    """
    대상 날짜가 지정된 범위 내에 있는지 확인합니다.
    
    Args:
        target_date: 확인할 날짜
        start_date: 시작 날짜 (None이면 제한 없음)
        end_date: 종료 날짜 (None이면 제한 없음)
        
    Returns:
        bool: 범위 내에 있는 경우 True
    """
    if start_date and target_date < start_date:
        return False
    if end_date and target_date > end_date:
        return False
    return True


def get_days_ago(days: int) -> date:
    """
    현재 날짜로부터 지정된 일수 이전의 날짜를 반환합니다.
    
    Args:
        days: 일수
        
    Returns:
        date: 계산된 날짜
    """
    return get_current_date() - timedelta(days=days)


def get_hours_ago(hours: int) -> datetime:
    """
    현재 시간으로부터 지정된 시간 이전의 시간을 반환합니다.
    
    Args:
        hours: 시간
        
    Returns:
        datetime: 계산된 시간
    """
    return get_current_datetime() - timedelta(hours=hours)


def format_date_for_display(target_date: date) -> str:
    """
    날짜를 표시용 문자열로 변환합니다.
    
    Args:
        target_date: 날짜
        
    Returns:
        str: YYYY-MM-DD 형식의 문자열
    """
    return target_date.isoformat()


def format_datetime_for_display(target_datetime: datetime) -> str:
    """
    날짜시간을 표시용 문자열로 변환합니다.
    
    Args:
        target_datetime: 날짜시간
        
    Returns:
        str: ISO 형식의 문자열
    """
    return target_datetime.isoformat()


def is_today(target_date: date) -> bool:
    """
    대상 날짜가 오늘인지 확인합니다.
    
    Args:
        target_date: 확인할 날짜
        
    Returns:
        bool: 오늘인 경우 True
    """
    return target_date == get_current_date()


def is_yesterday(target_date: date) -> bool:
    """
    대상 날짜가 어제인지 확인합니다.
    
    Args:
        target_date: 확인할 날짜
        
    Returns:
        bool: 어제인 경우 True
    """
    return target_date == get_days_ago(1)


def is_within_days(target_date: date, days: int) -> bool:
    """
    대상 날짜가 현재로부터 지정된 일수 이내인지 확인합니다.
    
    Args:
        target_date: 확인할 날짜
        days: 일수
        
    Returns:
        bool: 지정된 일수 이내인 경우 True
    """
    return target_date >= get_days_ago(days)


def is_within_hours(target_datetime: datetime, hours: int) -> bool:
    """
    대상 시간이 현재로부터 지정된 시간 이내인지 확인합니다.
    
    Args:
        target_datetime: 확인할 시간
        hours: 시간
        
    Returns:
        bool: 지정된 시간 이내인 경우 True
    """
    return target_datetime >= get_hours_ago(hours)


def get_date_difference(date1: date, date2: date) -> int:
    """
    두 날짜 간의 차이를 일수로 반환합니다.
    
    Args:
        date1: 첫 번째 날짜
        date2: 두 번째 날짜
        
    Returns:
        int: 일수 차이 (절댓값)
    """
    return abs((date1 - date2).days)


def get_datetime_difference(datetime1: datetime, datetime2: datetime) -> timedelta:
    """
    두 날짜시간 간의 차이를 반환합니다.
    
    Args:
        datetime1: 첫 번째 날짜시간
        datetime2: 두 번째 날짜시간
        
    Returns:
        timedelta: 시간 차이
    """
    return abs(datetime1 - datetime2) 