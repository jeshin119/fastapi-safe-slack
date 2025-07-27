from fastapi import HTTPException, status


def raise_not_found(message: str = "리소스를 찾을 수 없습니다."):
    """
    404 Not Found 예외를 발생시킵니다.
    
    Args:
        message: 에러 메시지
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=message
    )


def raise_forbidden(message: str = "접근 권한이 없습니다."):
    """
    403 Forbidden 예외를 발생시킵니다.
    
    Args:
        message: 에러 메시지
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message
    )


def raise_bad_request(message: str = "잘못된 요청입니다."):
    """
    400 Bad Request 예외를 발생시킵니다.
    
    Args:
        message: 에러 메시지
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message
    )


def raise_unauthorized(message: str = "인증이 필요합니다."):
    """
    401 Unauthorized 예외를 발생시킵니다.
    
    Args:
        message: 에러 메시지
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message
    )


def raise_internal_server_error(message: str = "내부 서버 오류가 발생했습니다."):
    """
    500 Internal Server Error 예외를 발생시킵니다.
    
    Args:
        message: 에러 메시지
    """
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=message
    )


def raise_conflict(message: str = "리소스 충돌이 발생했습니다."):
    """
    409 Conflict 예외를 발생시킵니다.
    
    Args:
        message: 에러 메시지
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=message
    )


def raise_workspace_not_found():
    """워크스페이스를 찾을 수 없는 경우의 예외"""
    raise_not_found("워크스페이스를 찾을 수 없습니다.")


def raise_channel_not_found():
    """채널을 찾을 수 없는 경우의 예외"""
    raise_not_found("채널을 찾을 수 없습니다.")


def raise_file_not_found():
    """파일을 찾을 수 없는 경우의 예외"""
    raise_not_found("파일을 찾을 수 없습니다.")


def raise_user_not_found():
    """사용자를 찾을 수 없는 경우의 예외"""
    raise_not_found("사용자를 찾을 수 없습니다.")


def raise_workspace_access_denied():
    """워크스페이스 접근 권한이 없는 경우의 예외"""
    raise_forbidden("워크스페이스에 접근할 권한이 없습니다.")


def raise_channel_access_denied():
    """채널 접근 권한이 없는 경우의 예외"""
    raise_forbidden("채널에 접근할 권한이 없습니다.")


def raise_file_access_denied():
    """파일 접근 권한이 없는 경우의 예외"""
    raise_forbidden("파일에 접근할 권한이 없습니다.")


def raise_admin_required():
    """관리자 권한이 필요한 경우의 예외"""
    raise_forbidden("관리자 권한이 필요합니다.")


def raise_duplicate_workspace():
    """워크스페이스 이름 중복의 예외"""
    raise_bad_request("이미 존재하는 워크스페이스 이름입니다.")


def raise_duplicate_channel():
    """채널 이름 중복의 예외"""
    raise_bad_request("이미 존재하는 채널명입니다.")


def raise_duplicate_email():
    """이메일 중복의 예외"""
    raise_bad_request("이미 등록된 이메일입니다.")


def raise_invalid_credentials():
    """잘못된 인증 정보의 예외"""
    raise_unauthorized("이메일 또는 비밀번호가 올바르지 않습니다.")


def raise_invalid_token():
    """잘못된 토큰의 예외"""
    raise_unauthorized("유효하지 않은 토큰입니다.")


def raise_invalid_role():
    """잘못된 역할의 예외"""
    raise_bad_request("유효하지 않은 직급명입니다.")


def raise_invalid_date_format():
    """잘못된 날짜 형식의 예외"""
    raise_bad_request("유효하지 않은 날짜 형식입니다.")


def raise_file_too_large():
    """파일이 너무 큰 경우의 예외"""
    raise_bad_request("파일 크기는 10MB를 초과할 수 없습니다.")


def raise_unsupported_file_type():
    """지원하지 않는 파일 형식의 예외"""
    raise_bad_request("지원하지 않는 파일 형식입니다.")


def raise_contract_period_not_started():
    """계약 기간이 시작되지 않은 경우의 예외"""
    raise_forbidden("계약 기간이 시작되지 않았습니다.")


def raise_contract_period_expired():
    """계약 기간이 종료된 경우의 예외"""
    raise_forbidden("계약 기간이 종료되었습니다.")


def raise_file_access_period_not_started():
    """파일 접근 기간이 시작되지 않은 경우의 예외"""
    raise_forbidden("파일 접근 기간이 시작되지 않았습니다.")


def raise_file_access_period_expired():
    """파일 접근 기간이 종료된 경우의 예외"""
    raise_forbidden("파일 접근 기간이 종료되었습니다.") 