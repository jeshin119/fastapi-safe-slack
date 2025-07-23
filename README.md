# Safe Slack API

워크스페이스 기반 협업 플랫폼 API입니다. FastAPI와 SQLAlchemy를 사용하여 구현되었습니다.

## 주요 기능

- **🔐 사용자 인증**: JWT 기반 인증, 회원가입, 로그인, 초대코드 관리
- **🧭 워크스페이스 관리**: 워크스페이스 생성, 멤버 관리, 가입 요청/승인
- **💬 채널 관리**: 공개/비공개 채널 생성, 멤버 관리, 입장 요청/승인
- **📁 파일 관리**: 권한 기반 파일 업로드, 다운로드, 조회
- **🎫 권한 관리**: 직급 기반 접근 제어, 계약직 기간 관리

## 기술 스택

- **Backend**: FastAPI, Uvicorn
- **Database**: AWS RDS, MySQL, SQLAlchemy ORM
- **Authentication**: JWT (python-jose)
- **File Storage**: AWS S3 (boto3)
- **Email**: SMTP (aiosmtplib) (업데이트 예정)

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

# AWS S3 설정
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=safe-slack-files

# 이메일 설정
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

## API 명세서

### 🔐 인증 (Authentication)

#### 로그인
- `POST /auth/login`
- 인증: 없음
- 요청:
```json
{
  "email": "hong@example.com",
  "password": "1234"
}
```
- 응답:
```json
{
  "access_token": "<JWT>",
  "token_type": "bearer"
}
```

#### 회원가입
- `POST /auth/signup`
- 인증: 없음
- 설명: 신규 워크스페이스 생성 또는 초대코드로 가입
- 규칙: `workspace_name` 또는 `invite_code` 중 하나 필수

요청 A: 새 워크스페이스 생성
```json
{
  "name": "홍길동",
  "email": "hong@example.com",
  "password": "1234"
}
```

#### 초대 코드 생성 (관리자 전용)
- `POST /auth/invite-codes-create`
- 인증: 필요 (워크스페이스 관리자만)
- 요청:
```json
{
  "expires_at": "2025-08-01T23:59:59"
}
```

#### 초대 코드 목록 조회 (관리자 전용)
- `POST /auth/invite-codes-list`
- 인증: 필요 (워크스페이스 관리자만)
- 요청:
```json
{
  "workspace_name": "오픈AI"
}
```

### 🧭 워크스페이스 (Workspaces)

#### 워크스페이스 생성
- `POST /workspaces/create`
- 인증: 필요
- 설명: 생성하면 관리자
- 요청:
```json
{
  "workspace_name": "오픈AI"
}
```

#### 워크스페이스 가입 요청
- `POST /workspaces/join-request`
- 인증: 필요
- 설명: 단순히 해당 워크스페이스에 참여 요청만 전송
- 요청:
```json
{
  "invite_code": "XYZ123",
  "role_name": "대리"
}
```

#### 워크스페이스 가입 요청 목록 조회 (관리자 전용)
- `POST /workspaces/join-requests-list`
- 인증: 필요 (워크스페이스 관리자만)
- 요청:
```json
{
  "workspace_name": "오픈AI"
}
```

#### 워크스페이스 요청 승인 (관리자 전용)
- `POST /workspaces/approve`
- 인증: 필요 (워크스페이스 관리자만)
- 설명: 승인 시 관리자가 역할과 계약 정보를 설정
- 요청:
```json
{
  "request_id": 1,
  "user_name": "이파견",
  "role_name": "대리",
  "is_contractor": true,
  "expires_at": "2025-08-01T23:59:59"
}
```

#### 워크스페이스 멤버 목록 조회
- `POST /workspaces/members`
- 인증: 필요
- 요청:
```json
{
  "workspace_name": "오픈AI"
}
```

### 💬 채널 (Channels)

#### 채널 생성
- `POST /channels/create`
- 인증: 로그인한 유저 모두 가능
- 요청:
```json
{
  "workspace_name": "오픈AI",
  "channel_name": "디자인",
  "is_public": false
}
```

#### 채널 목록 조회
- `POST /channels/list`
- 인증: 로그인한 유저 모두 가능
- 설명: 사용자가 접근 가능한 채널만 반환 (public + 가입된 private)
- 요청:
```json
{
  "workspace_name": "오픈AI"
}
```

#### 채널 삭제
- `DELETE /channels/:channel_name`
- 인증: 채널 생성자만

#### 채널 입장 요청
- `POST /channels/join-request`
- 인증: 로그인한 유저 모두 가능
- 설명: public 채널은 요청 시 바로 approved 되지만 private은 채널 관리자 승인 필요
- 요청:
```json
{
  "workspace_name": "오픈AI",
  "channel_name": "디자인"
}
```

#### 채널 입장 요청 목록 조회
- `POST /channels/request_list`
- 인증: 채널 관리자만
- 요청:
```json
{
  "workspace_name": "오픈AI"
}
```

#### 채널 입장 승인
- `POST /channels/approve`
- 인증: 채널 생성자만
- 요청:
```json
{
  "workspace_name": "오픈AI",
  "request_id": 1,
  "request_user_name": "김대리",
  "request_role_name": "대리",
  "channel_name": "디자인"
}
```

#### 채널 멤버 목록 조회
- `POST /channels/members_list`
- 인증: 채널 멤버만
- 요청:
```json
{
  "workspace_name": "오픈AI",
  "channel_name": "디자인"
}
```

#### 채널 나가기
- `POST /channels/leave`
- 인증: 채널 멤버만
- 요청:
```json
{
  "workspace_name": "오픈AI",
  "channel_name": "디자인"
}
```

### 📁 파일 (Files)

#### 파일 업로드
- `POST /channels/:channel_name/files`
- 인증: 필요
- Content-Type: multipart/form-data
- 필드:
  - `file`: 실제 파일
  - `min_role_name`: "과장" (최소 접근 가능한 역할명)
  - `valid_from`: "2025-07-20" (접근 시작일, 선택사항)
  - `valid_to`: "2025-07-31" (접근 종료일, 선택사항)
  - `description`: "파일 설명" (선택사항)

#### 파일 목록 조회
- `GET /channels/:channel_name/files`
- 인증: 필요
- 설명: 서버에서 JWT 기반 사용자 정보로 권한, 날짜 유효성 판단

#### 파일 다운로드
- `GET /files/:file_id/download`
- 인증: 필요
- 설명: 서버에서 권한 검증 후 S3 pre-signed URL 리다이렉트 또는 스트림 응답

#### 파일 삭제
- `DELETE /files/:file_id`
- 인증: 필요 (업로드한 본인 또는 채널 관리자)

## 프로젝트 구조

```
fastapi-safe-slack2/
├── app/
│   ├── main.py              # FastAPI 애플리케이션
│   ├── models/              # SQLAlchemy ORM 모델
│   ├── schemas/             # Pydantic 스키마
│   ├── routers/             # API 라우터
│   │   ├── auth.py          # 인증 관련 라우터
│   │   ├── workspaces.py    # 워크스페이스 관련 라우터
│   │   ├── channels.py      # 채널 관련 라우터
│   │   ├── files.py         # 파일 관련 라우터
│   │   └── messages.py      # 메시지 관련 라우터
│   ├── core/                # 환경설정, 보안 등 공통 모듈
│   ├── db/                  # 데이터베이스 관련 파일
│   └── init_db.py           # 데이터베이스 초기화
├── requirements.txt         # 의존성 목록
├── run.py                  # 서버 실행 스크립트
└── README.md               # 프로젝트 문서
```

## 데이터베이스 스키마

주요 테이블:
- `users` - 사용자 정보
- `workspaces` - 워크스페이스
- `workspace_members` - 워크스페이스 멤버십
- `workspace_join_requests` - 워크스페이스 가입 요청
- `channels` - 채널
- `channel_members` - 채널 멤버십
- `channel_join_requests` - 채널 입장 요청
- `messages` - 메시지
- `files` - 파일 정보
- `roles` - 직급 정보
- `invite_codes` - 초대코드 정보

## JWT 페이로드 예시

```json
{
  "user_id": 1,
  "user_email": "hong@example.com",
  "user_name": "홍길동",
  "exp": 1734567890,
  "iat": 1734481490
}
```

## 보안 기능

- JWT 기반 인증
- 비밀번호 해싱 (bcrypt)
- 직급 기반 접근 제어
- 계약직 기간 관리
- 파일 업로드 제한 및 권한 검증
- 워크스페이스/채널별 접근 제어

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