# Safe Slack API

워크스페이스 기반 협업 플랫폼 API입니다. FastAPI와 SQLAlchemy를 사용하여 구현되었습니다.

## 프로젝트 문서

- **프로젝트 기술서**: [OneDrive 링크](https://onedrive.live.com/personal/1256b1ecd2fa9385/_layouts/15/Doc.aspx?sourcedoc=%7B5f02ae56-ea15-4b92-bec8-f28a5470d8c0%7D&action=default&redeem=aHR0cHM6Ly8xZHJ2Lm1zL3AvYy8xMjU2YjFlY2QyZmE5Mzg1L0VWYXVBbDhWNnBKTHZzanlpbFJ3Mk1BQnhrUFQyLU5YVktqaVpYb3NWalJHbXc_ZT1yemM2RFU&slrid=d08cbca1-e0f3-d000-a469-b20e49f8d1a6&originalPath=aHR0cHM6Ly8xZHJ2Lm1zL3AvYy8xMjU2YjFlY2QyZmE5Mzg1L0VWYXVBbDhWNnBKTHZzanlpbFJ3Mk1BQnhrUFQyLU5YVktqaVpYb3NWalJHbXc_cnRpbWU9QTVFMnlsUGQzVWc&CID=6d134b8d-e10c-4aa3-a5af-3d9bff69e578&_SRM=0:G:40&file=1%ec%a1%b0%20AWS%20%ea%b8%b0%eb%b0%98%20%eb%b3%b4%ec%95%88%20%ea%b0%95%ed%99%94%20%ed%98%91%ec%97%85%ed%88%b4.pptx)
- **Terraform code**: [GitHub Repository](https://github.com/j1nseop/Terraform-eks)
- **API 명세서**: [Postman Documentation](https://documenter.getpostman.com/view/46454605/2sB3B7NDYM)
- **화면기획서**: [Figma Design](https://www.figma.com/design/ynWWgfetCF9Z4kNvp9UsgJ/aws-%EB%B3%B4%EC%95%88-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8-2%EC%B0%A8?node-id=0-1&t=B4JgkOdj2m98knfl-1)
- **ERD**: [ERDCloud](https://www.erdcloud.com/d/esyuuB6DMhpTR7oED)

## 🚀 주요 기능

### 🔐 사용자 인증
- JWT 기반 보안 인증 시스템
- 회원가입, 로그인, 비밀번호 재설정
- 이메일 인증 및 계정 설정
- 초대코드 기반 워크스페이스 가입

### 🧭 워크스페이스 관리
- 워크스페이스 생성 및 설정
- 멤버 관리 (직급별 권한 관리)
- 가입 요청/승인 시스템
- 계약직 기간 관리

### 💬 채널 관리
- 공개/비공개 채널 생성
- 실시간 채팅 기능
- 채널 멤버 관리
- 입장 요청/승인 시스템

### 📁 파일 관리
- 권한 기반 파일 업로드/다운로드
- AWS S3 연동 파일 저장
- 직급별 접근 제어
- 파일 유효기간 설정

### 🎫 권한 관리
- 직급 기반 세밀한 접근 제어
- 관리자 전용 기능
- 계약직 기간 자동 관리

## 🛠️ 기술 스택

### Backend
- **Framework**: FastAPI, Uvicorn
- **Database**: MySQL, SQLAlchemy ORM (비동기)
- **Authentication**: JWT (python-jose, PyJWT)
- **File Storage**: AWS S3 (boto3)
- **Chat Storage**: AWS DynamoDB
- **Password Hashing**: bcrypt

### Frontend
- **Language**: HTML5, CSS3, JavaScript (ES6+)
- **Architecture**: Single Page Application (SPA)
- **Styling**: Custom CSS with modern design
- **Components**: Modular component-based structure

### Infrastructure
- **Cloud**: AWS (S3, DynamoDB)
- **Infrastructure as Code**: Terraform (별도 저장소)
- **Database**: MySQL (로컬 또는 AWS RDS)

## 📚 API 문서

### 상세 API 명세서
📋 [Postman API 명세서](https://documenter.getpostman.com/view/46454605/2sB3B7NDYM)에서 전체 API 엔드포인트와 요청/응답 예시를 확인하세요.

### 주요 API 엔드포인트

| 기능 | 엔드포인트 | 설명 |
|------|------------|------|
| 🔐 인증 | `/auth/*` | 로그인, 회원가입, 초대코드 관리 |
| 🧭 워크스페이스 | `/workspaces/*` | 워크스페이스 생성, 멤버 관리 |
| 💬 채널 | `/channels/*` | 채널 생성, 멤버 관리, 채팅 |
| 📁 파일 | `/channels/*/files` | 파일 업로드, 다운로드, 관리 |
| 💬 채팅 | `/chat/*` | 실시간 채팅 기능 |

## 📁 프로젝트 구조

```
fastapi-safe-slack2/
├── 📂 app/
│   ├── 🐍 main.py                    # FastAPI 애플리케이션 진입점
│   ├── 📂 models/                    # SQLAlchemy ORM 모델
│   │   ├── user.py                   # 사용자 모델
│   │   ├── workspace.py              # 워크스페이스 모델
│   │   ├── channel.py                # 채널 모델
│   │   ├── file.py                   # 파일 모델
│   │   └── invite_code.py            # 초대코드 모델
│   ├── 📂 schemas/                   # Pydantic 스키마 (API 요청/응답)
│   ├── 📂 routers/                   # API 라우터
│   │   ├── auth.py                   # 인증 관련 API
│   │   ├── workspaces.py             # 워크스페이스 관리 API
│   │   ├── channels.py               # 채널 관리 API
│   │   ├── files.py                  # 파일 관리 API
│   │   └── chat.py                   # 채팅 API
│   ├── 📂 core/                      # 환경설정, 보안 등 공통 모듈
│   ├── 📂 db/                        # 데이터베이스 연결 및 설정
│   ├── 📂 front/                     # 프론트엔드 (SPA)
│   │   ├── 🎨 css/                   # 스타일시트
│   │   │   ├── common.css            # 공통 스타일
│   │   │   ├── index.css             # 메인 페이지 스타일
│   │   │   ├── auth.css              # 인증 페이지 스타일
│   │   │   ├── workspace-main.css    # 워크스페이스 메인 스타일
│   │   │   ├── chat.css              # 채팅 스타일
│   │   │   ├── file.css              # 파일 관리 스타일
│   │   │   └── admin-*.css           # 관리자 페이지 스타일
│   │   ├── 📜 js/                    # JavaScript 파일
│   │   │   ├── config.js             # 설정 파일
│   │   │   └── alert-system.js       # 알림 시스템
│   │   ├── 📄 index.html             # 메인 페이지
│   │   └── 📂 pages/                 # 페이지별 HTML
│   │       ├── 📂 auth/              # 인증 관련 페이지
│   │       │   ├── login.html        # 로그인
│   │       │   ├── signup.html       # 회원가입
│   │       │   ├── password-reset.html # 비밀번호 재설정
│   │       │   └── account-setup.html # 계정 설정
│   │       ├── 📂 workspace/         # 워크스페이스 페이지
│   │       │   ├── workspace-main.html # 워크스페이스 메인
│   │       │   ├── workspace-select.html # 워크스페이스 선택
│   │       │   ├── chat.html         # 채팅 페이지
│   │       │   ├── file.html         # 파일 관리
│   │       │   └── channel-add.html  # 채널 추가
│   │       └── 📂 admin/             # 관리자 페이지
│   │           ├── admin-main.html   # 관리자 메인
│   │           ├── admin-members.html # 멤버 관리
│   │           ├── admin-channels.html # 채널 관리
│   │           └── admin-ws-settings.html # 워크스페이스 설정
│   └── init_db.py                    # 데이터베이스 초기화
├── 📄 requirements.txt               # Python 의존성 목록
├── 🐍 setup_database.py             # 데이터베이스 테이블 생성 스크립트
├── 🚀 run.py                        # 서버 실행 스크립트
└── 📖 README.md                     # 프로젝트 문서
```

## 🗄️ 데이터베이스 스키마

### 주요 테이블 구조

| 테이블 | 설명 | 주요 필드 |
|--------|------|-----------|
| `users` | 사용자 정보 | id, email, name, password_hash |
| `workspaces` | 워크스페이스 | id, name, created_at |
| `workspace_members` | 워크스페이스 멤버십 | user_id, workspace_id, role_name, is_contractor, expires_at |
| `workspace_join_requests` | 워크스페이스 가입 요청 | id, user_id, workspace_id, role_name, status |
| `channels` | 채널 | id, name, workspace_id, is_public, created_by |
| `channel_members` | 채널 멤버십 | user_id, channel_id, joined_at |
| `channel_join_requests` | 채널 입장 요청 | id, user_id, channel_id, status |
| `files` | 파일 정보 | id, filename, file_path, channel_id, uploaded_by, min_role_name, valid_from, valid_to |
| `roles` | 직급 정보 | id, name, hierarchy_level |
| `invite_codes` | 초대코드 | id, code, workspace_id, expires_at, created_by |

### JWT 토큰 구조

```json
{
  "user_id": 1,
  "user_email": "hong@example.com",
  "user_name": "홍길동",
  "exp": 1734567890,
  "iat": 1734481490
}
```

## 🔒 보안 기능

### 인증 및 권한 관리
- **JWT 기반 인증**: 안전한 토큰 기반 인증
- **비밀번호 해싱**: bcrypt를 사용한 안전한 비밀번호 저장
- **직급 기반 접근 제어**: 세밀한 권한 관리 시스템
- **계약직 기간 관리**: 자동 만료 처리

### 데이터 보안
- **파일 업로드 제한**: 파일 타입 및 크기 검증
- **권한 기반 파일 접근**: 직급별 파일 접근 제어
- **워크스페이스/채널별 격리**: 데이터 접근 범위 제한
- **AWS S3 연동**: 안전한 클라우드 파일 저장

## 🚀 개발 환경 설정

### 필수 요구사항
- **Python**: 3.8 이상
- **MySQL**: 8.0 이상 (로컬 설치 필요)
- **AWS 계정**: S3, DynamoDB 사용을 위해 필요

### ⚠️ 중요 사항
이 프로젝트는 **완전한 로컬 개발 환경 구성이 필요**합니다:
- MySQL 서버 설치 및 실행
- AWS 계정 및 서비스 설정 (S3, DynamoDB)
- 환경 변수 파일 직접 생성

### 빠른 시작

1. **저장소 클론**
   ```bash
   git clone <repository-url>
   cd fastapi-safe-slack2
   ```

2. **가상환경 생성 및 활성화**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

4. **데이터베이스 및 테이블 생성**
   ```bash
   # Python 스크립트로 데이터베이스와 테이블 자동 생성
   python setup_database.py
   ```

5. **AWS 서비스 설정**
   - S3 버킷 생성 (파일 저장용)
   - DynamoDB 테이블 생성 (채팅 메시지용) - 자동 생성됨
   - IAM 사용자 생성 및 권한 설정

6. **환경 변수 설정**
   - `.env` 파일 생성하고 위의 환경 변수 설정 참조

7. **서버 실행**
   ```bash
   python run.py
   ```

### 접속 정보
- **웹 애플리케이션**: `http://localhost:8000`
- **API 문서**: `http://localhost:8000/docs`
- **ReDoc 문서**: `http://localhost:8000/redoc`

### 추가 설정이 필요한 이유
이 프로젝트는 실제 운영 환경과 유사한 설정이 필요합니다:
- 클라우드 파일 저장소 (AWS S3)
- 실시간 채팅 메시지 저장소 (AWS DynamoDB)
- 프로덕션급 데이터베이스 (MySQL)

## 📄 라이센스

라이센스 미정 - 추후 결정 예정