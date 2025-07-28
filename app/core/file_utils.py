import os
import boto3
import urllib.parse
from fastapi import UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.core.exception_utils import raise_file_too_large, raise_unsupported_file_type
from typing import Set


def validate_file_size(file: UploadFile, max_size_mb: int = 10) -> bool:
    """
    파일 크기를 검증합니다.
    
    Args:
        file: 업로드된 파일
        max_size_mb: 최대 파일 크기 (MB)
        
    Returns:
        bool: 유효한 경우 True
        
    Raises:
        HTTPException: 파일이 너무 큰 경우
    """
    if file.size and file.size > max_size_mb * 1024 * 1024:
        raise_file_too_large()
    return True


def validate_file_extension(filename: str, allowed_extensions: Set[str] = None) -> bool:
    """
    파일 확장자를 검증합니다.
    
    Args:
        filename: 파일명
        allowed_extensions: 허용된 확장자 집합 (None이면 기본값 사용)
        
    Returns:
        bool: 유효한 경우 True
        
    Raises:
        HTTPException: 지원하지 않는 파일 형식인 경우
    """
    if allowed_extensions is None:
        allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.gif'}
    
    file_extension = os.path.splitext(filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise_unsupported_file_type()
    return True


def get_file_extension(filename: str) -> str:
    """
    파일명에서 확장자를 추출합니다.
    
    Args:
        filename: 파일명
        
    Returns:
        str: 파일 확장자 (소문자)
    """
    return os.path.splitext(filename)[1].lower()


def get_filename_without_extension(filename: str) -> str:
    """
    파일명에서 확장자를 제거합니다.
    
    Args:
        filename: 파일명
        
    Returns:
        str: 확장자가 제거된 파일명
    """
    return os.path.splitext(filename)[0]


def generate_unique_filename(original_filename: str, prefix: str = "") -> str:
    """
    고유한 파일명을 생성합니다.
    
    Args:
        original_filename: 원본 파일명
        prefix: 파일명 앞에 추가할 접두사
        
    Returns:
        str: 고유한 파일명
    """
    import uuid
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    extension = get_file_extension(original_filename)
    
    if prefix:
        return f"{prefix}_{timestamp}_{unique_id}{extension}"
    else:
        return f"{timestamp}_{unique_id}{extension}"


def upload_file_to_s3(file: UploadFile, filename: str) -> str:
    """
    파일을 S3에 업로드합니다.
    
    Args:
        file: 업로드할 파일
        filename: S3에 저장할 파일명
        
    Returns:
        str: S3 URL
    """
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # 파일 내용을 읽어서 S3에 업로드
        file_content = file.file.read()
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=filename,
            Body=file_content
        )
        
        # 파일 포인터를 다시 처음으로 되돌림
        file.file.seek(0)
        
        return f"https://s3.amazonaws.com/{settings.S3_BUCKET_NAME}/{filename}"
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 업로드 실패: {str(e)}"
        )


def download_file_from_s3(filename: str) -> StreamingResponse:
    """
    S3에서 파일을 다운로드합니다.
    
    Args:
        filename: S3에 저장된 파일명
        
    Returns:
        StreamingResponse: 파일 스트림 응답
        
    Raises:
        HTTPException: 파일을 찾을 수 없거나 다운로드 실패한 경우
    """
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        s3_obj = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=filename)
        file_stream = s3_obj["Body"]
        
        # 한글 파일명을 위한 URL 인코딩 처리
        encoded_filename = urllib.parse.quote(filename)
        
        return StreamingResponse(
            file_stream,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 다운로드 실패: {str(e)}"
        )


def delete_file_from_s3(filename: str) -> bool:
    """
    S3에서 파일을 삭제합니다.
    
    Args:
        filename: 삭제할 파일명
        
    Returns:
        bool: 삭제 성공 시 True
        
    Raises:
        HTTPException: 삭제 실패한 경우
    """
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=filename)
        return True
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 삭제 실패: {str(e)}"
        )


def get_file_size_mb(file_size_bytes: int) -> float:
    """
    바이트 단위 파일 크기를 MB 단위로 변환합니다.
    
    Args:
        file_size_bytes: 바이트 단위 파일 크기
        
    Returns:
        float: MB 단위 파일 크기
    """
    return file_size_bytes / (1024 * 1024)


def format_file_size(file_size_bytes: int) -> str:
    """
    파일 크기를 사람이 읽기 쉬운 형태로 포맷합니다.
    
    Args:
        file_size_bytes: 바이트 단위 파일 크기
        
    Returns:
        str: 포맷된 파일 크기 문자열
    """
    if file_size_bytes < 1024:
        return f"{file_size_bytes} B"
    elif file_size_bytes < 1024 * 1024:
        return f"{file_size_bytes / 1024:.1f} KB"
    elif file_size_bytes < 1024 * 1024 * 1024:
        return f"{file_size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{file_size_bytes / (1024 * 1024 * 1024):.1f} GB"


def is_image_file(filename: str) -> bool:
    """
    파일이 이미지인지 확인합니다.
    
    Args:
        filename: 파일명
        
    Returns:
        bool: 이미지 파일인 경우 True
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
    return get_file_extension(filename) in image_extensions


def is_document_file(filename: str) -> bool:
    """
    파일이 문서인지 확인합니다.
    
    Args:
        filename: 파일명
        
    Returns:
        bool: 문서 파일인 경우 True
    """
    document_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'}
    return get_file_extension(filename) in document_extensions


def is_video_file(filename: str) -> bool:
    """
    파일이 비디오인지 확인합니다.
    
    Args:
        filename: 파일명
        
    Returns:
        bool: 비디오 파일인 경우 True
    """
    video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'}
    return get_file_extension(filename) in video_extensions


def is_audio_file(filename: str) -> bool:
    """
    파일이 오디오인지 확인합니다.
    
    Args:
        filename: 파일명
        
    Returns:
        bool: 오디오 파일인 경우 True
    """
    audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'}
    return get_file_extension(filename) in audio_extensions


def get_mime_type(filename: str) -> str:
    """
    파일명에 따른 MIME 타입을 반환합니다.
    
    Args:
        filename: 파일명
        
    Returns:
        str: MIME 타입
    """
    extension = get_file_extension(filename)
    
    mime_types = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.mp4': 'video/mp4',
        '.mp3': 'audio/mpeg',
    }
    
    return mime_types.get(extension, 'application/octet-stream') 