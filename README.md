# Safe Slack API

워크스페이스 기반 협업 플랫폼 API입니다. FastAPI와 SQLAlchemy를 사용하여 구현되었습니다.

## 주요 기능

- **사용자 인증**: JWT 기반 인증, 회원가입, 로그인
- **워크스페이스 관리**: 워크스페이스 생성, 멤버 관리, 가입 요청/승인
- **채널 관리**: 공개/비공개 채널 생성, 멤버 관리
- **메시지**: 채널별 메시지 전송 및 조회
- **파일 관리**: 권한 기반 파일 업로드 및 조회
- **권한 관리**: 직급 기반 접근 제어, 계약직 기간 관리

## 기술 스택

- **Backend**: FastAPI, Uvicorn
- **Database**: MySQL, SQLAlchemy ORM
- **Authentication**: JWT (python-jose)
- **File Storage**: AWS S3 (boto3)
- **Email**: SMTP (aiosmtplib)

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 설정을 추가하세요:

```env
# 데이터베이스 설정
DB_USER=root
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=safe_slack

# JWT 설정
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AWS S3 설정 (선택사항)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=safe-slack-files

# 이메일 설정 (선택사항)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 3. 데이터베이스 초기화

```bash
python -m app.init_db
```

### 4. 서버 실행

```bash
python run.py
```

서버가 `http://localhost:8000`에서 실행됩니다.

## API 문서

서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 주요 API 엔드포인트

### 인증
- `POST /auth/signup` - 회원가입
- `POST /auth/login` - 로그인
- `POST /auth/request-verification` - 이메일 인증 요청
- `POST /auth/verify-email` - 이메일 인증 확인

### 워크스페이스
- `POST /workspaces/{workspace_id}/join-request` - 워크스페이스 참여 요청
- `POST /workspaces/{workspace_id}/approve/{user_id}` - 참여 요청 승인
- `GET /workspaces/{workspace_id}/channels` - 워크스페이스 채널 목록

### 채널
- `POST /channels` - 채널 생성
- `POST /channels/{channel_id}/join-request` - 채널 입장 요청
- `POST /channels/{channel_id}/approve/{user_id}` - 입장 요청 승인

### 메시지
- `POST /channels/{channel_id}/messages` - 메시지 전송
- `GET /channels/{channel_id}/messages` - 메시지 목록 조회

### 파일
- `POST /channels/{channel_id}/files` - 파일 업로드
- `GET /channels/{channel_id}/files` - 파일 목록 조회

## 프로젝트 구조

```
fastapi-safe-slack2/
├── app/
│   ├── main.py              # FastAPI 애플리케이션
│   ├── models/              # SQLAlchemy 등 ORM 모델
│   ├── schemas/             # Pydantic 스키마
│   ├── crud/                # 데이터 처리 로직
│   ├── api/                 # (미사용)
│   ├── core/                # 환경설정, 보안 등 공통 모듈
│   ├── db/                  # 데이터베이스 관련 파일
│   ├── tests/               # 테스트 코드
│   └── routers/             # API 라우터
├── requirements.txt         # 의존성 목록
├── run.py                  # 서버 실행 스크립트
└── README.md               # 프로젝트 문서
```

## 데이터베이스 스키마

주요 테이블:
- `users` - 사용자 정보
- `workspaces` - 워크스페이스
- `workspace_members` - 워크스페이스 멤버십
- `channels` - 채널
- `channel_members` - 채널 멤버십
- `messages` - 메시지
- `files` - 파일 정보
- `roles` - 직급 정보
- `invite_codes` - 초대코드 정보

## 보안 기능

- JWT 기반 인증
- 비밀번호 해싱 (bcrypt)
- 직급 기반 접근 제어
- 계약직 기간 관리
- 파일 업로드 제한

## 개발 환경 설정

1. Python 3.8+ 설치
2. MySQL 데이터베이스 설정
3. 가상환경 생성 및 활성화
4. 의존성 설치
5. 환경 변수 설정
6. 데이터베이스 초기화
7. 서버 실행

## 라이센스

MIT License 