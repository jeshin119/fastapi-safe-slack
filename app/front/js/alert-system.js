// ============================
// Alert 시스템 - app/front/js/alert-system.js
// ============================

class AlertSystem {
    constructor() {
        this.init();
    }

    init() {
        // 인라인 CSS 주입
        this.injectCSS();
        
        // 기존 alert 함수 백업 및 오버라이드
        this.overrideNativeAlert();
        
        // 키보드 이벤트 설정
        this.setupKeyboardEvents();
    }

    // 인라인 CSS 주입
    injectCSS() {
        const head = document.head || document.getElementsByTagName('head')[0];
        if (!head) return;
        
        // 이미 CSS가 주입되었는지 확인
        if (document.getElementById('alert-system-inline-css')) return;

        const style = document.createElement('style');
        style.id = 'alert-system-inline-css';
        style.textContent = `
            /* Alert Modal Styles */
            .alert-modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10000;
                animation: fadeIn 0.2s ease;
            }

            .alert-modal-content {
                background: white;
                border-radius: 12px;
                padding: 30px;
                min-width: 320px;
                max-width: 500px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                animation: slideIn 0.3s ease;
            }

            .alert-modal-icon {
                font-size: 48px;
                margin-bottom: 15px;
            }

            .alert-modal-title {
                font-size: 20px;
                font-weight: 600;
                margin: 0 0 15px 0;
                color: #333;
            }

            .alert-modal-message {
                font-size: 16px;
                line-height: 1.5;
                margin: 0 0 25px 0;
                color: #666;
                word-break: keep-all;
            }

            .alert-modal-button {
                background: #007bff;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 16px;
                cursor: pointer;
                margin: 0 5px;
                min-width: 80px;
                transition: all 0.2s ease;
            }

            .alert-modal-button:hover {
                background: #0056b3;
                transform: translateY(-1px);
            }

            .alert-modal-button.success {
                background: #28a745;
            }

            .alert-modal-button.success:hover {
                background: #1e7e34;
            }

            .alert-modal-button.error {
                background: #dc3545;
            }

            .alert-modal-button.error:hover {
                background: #c82333;
            }

            .alert-modal-button.warning {
                background: #ffc107;
                color: #212529;
            }

            .alert-modal-button.warning:hover {
                background: #e0a800;
            }

            .alert-modal-button.cancel {
                background: #6c757d;
            }

            .alert-modal-button.cancel:hover {
                background: #545b62;
            }

            .alert-modal-buttons {
                display: flex;
                justify-content: center;
                gap: 10px;
            }

            /* Toast Styles */
            .toast-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10001;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }

            .toast {
                background: white;
                border-radius: 8px;
                padding: 16px;
                min-width: 300px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                display: flex;
                align-items: center;
                gap: 12px;
                animation: toastSlideIn 0.3s ease;
                border-left: 4px solid #007bff;
            }

            .toast.success {
                border-left-color: #28a745;
            }

            .toast.error {
                border-left-color: #dc3545;
            }

            .toast.warning {
                border-left-color: #ffc107;
            }

            .toast-icon {
                font-size: 20px;
                flex-shrink: 0;
            }

            .toast-message {
                flex: 1;
                font-size: 14px;
                color: #333;
                word-break: keep-all;
            }

            .toast-close {
                background: none;
                border: none;
                font-size: 18px;
                cursor: pointer;
                color: #999;
                padding: 0;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 50%;
                transition: all 0.2s ease;
            }

            .toast-close:hover {
                background: #f0f0f0;
                color: #666;
            }

            /* Animations */
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            @keyframes slideIn {
                from { 
                    opacity: 0;
                    transform: scale(0.9) translateY(-20px);
                }
                to { 
                    opacity: 1;
                    transform: scale(1) translateY(0);
                }
            }

            @keyframes toastSlideIn {
                from {
                    opacity: 0;
                    transform: translateX(100%);
                }
                to {
                    opacity: 1;
                    transform: translateX(0);
                }
            }

            @keyframes toastSlideOut {
                from {
                    opacity: 1;
                    transform: translateX(0);
                }
                to {
                    opacity: 0;
                    transform: translateX(100%);
                }
            }

            /* 반응형 */
            @media (max-width: 480px) {
                .alert-modal-content {
                    margin: 20px;
                    min-width: auto;
                    width: calc(100% - 40px);
                }
                
                .toast {
                    margin: 0 10px;
                    min-width: auto;
                    width: calc(100% - 20px);
                }
                
                .toast-container {
                    right: 0;
                    left: 0;
                }
            }
        `;
        
        head.appendChild(style);
        console.log('🎨 Alert 시스템 인라인 CSS 주입 완료');
    }

    // 기존 alert 함수 오버라이드
    overrideNativeAlert() {
        // 원본 함수 백업
        window.originalAlert = window.alert;
        window.originalConfirm = window.confirm;
        
        // alert 대체
        window.alert = (message) => {
            this.showAlert(message, 'info', '알림');
        };
        
        // confirm 대체 (Promise 기반)
        window.confirm = (message) => {
            return this.showConfirm(message, '확인');
        };
    }

    // 메인 Alert 함수
    showAlert(message, type = 'info', title = null) {
        // 타입별 설정
        const config = this.getTypeConfig(type, message);
        const finalTitle = title || config.title;
        
        // 기존 모달 제거
        this.closeModal();
        
        // 모달 생성
        const modal = this.createModal(config.icon, finalTitle, message, config.buttonClass);
        document.body.appendChild(modal);
        
        // 표시
        modal.style.display = 'flex';
    }

    // Toast 알림
    showToast(message, type = 'info', duration = 3000) {
        const config = this.getTypeConfig(type, message);
        
        // 토스트 컨테이너 확인/생성
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        // 토스트 생성
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <div class="toast-icon">${config.icon}</div>
            <div class="toast-message">${message}</div>
            <button class="toast-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        container.appendChild(toast);
        
        // 자동 제거
        const autoRemove = setTimeout(() => {
            toast.style.animation = 'toastSlideOut 0.3s ease forwards';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, duration);
        
        // 클릭시 즉시 제거
        toast.addEventListener('click', (e) => {
            if (e.target.classList.contains('toast-close')) return;
            clearTimeout(autoRemove);
            toast.style.animation = 'toastSlideOut 0.3s ease forwards';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        });
    }

    // Confirm 다이얼로그 (Promise 기반)
    showConfirm(message, title = '확인') {
        return new Promise((resolve) => {
            // 기존 모달 제거
            this.closeModal();
            
            // 확인 모달 생성
            const modal = document.createElement('div');
            modal.className = 'alert-modal-overlay';
            modal.innerHTML = `
                <div class="alert-modal-content">
                    <div class="alert-modal-icon">❓</div>
                    <h2 class="alert-modal-title">${title}</h2>
                    <p class="alert-modal-message">${message}</p>
                    <div class="alert-modal-buttons">
                        <button class="alert-modal-button" onclick="window.alertSystem.resolveConfirm(true)">확인</button>
                        <button class="alert-modal-button cancel" onclick="window.alertSystem.resolveConfirm(false)">취소</button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            modal.style.display = 'flex';
            
            // Promise resolver 저장
            this.confirmResolver = resolve;
        });
    }

    // Confirm 결과 처리
    resolveConfirm(result) {
        if (this.confirmResolver) {
            this.confirmResolver(result);
            this.confirmResolver = null;
        }
        this.closeModal();
    }

    // 타입별 설정 반환
    getTypeConfig(type, message) {
        // 메시지 내용으로 타입 자동 감지
        if (type === 'auto') {
            type = this.detectTypeFromMessage(message);
        }
        
        const configs = {
            success: {
                icon: '✅',
                title: '성공',
                buttonClass: 'success'
            },
            error: {
                icon: '❌',
                title: '오류',
                buttonClass: 'error'
            },
            warning: {
                icon: '⚠️',
                title: '경고',
                buttonClass: 'warning'
            },
            info: {
                icon: 'ℹ️',
                title: '알림',
                buttonClass: ''
            }
        };
        
        return configs[type] || configs.info;
    }

    // 메시지 내용으로 타입 자동 감지
    detectTypeFromMessage(message) {
        const lowerMessage = message.toLowerCase();
        
        // 성공 키워드
        const successPatterns = [
            '성공', '완료', '생성되었습니다', '저장되었습니다', '업로드', '승인', 
            '등록되었습니다', '전송되었습니다', '추가되었습니다', '변경되었습니다',
            '🎉', '✅', '👍', '수정되었습니다', '연결되었습니다'
        ];
        
        // 에러 키워드
        const errorPatterns = [
            '실패', '오류', '에러', '없습니다', '불가능', '거부', '차단',
            '만료', '초과', '부족', '연결 실패', '인증 실패', '권한이 없습니다',
            '❌', '⚠️', '잘못된', '올바르지 않', '찾을 수 없습니다'
        ];
        
        // 경고 키워드
        const warningPatterns = [
            '정말', '확인', '삭제', '주의', '경고', '위험', '되돌릴 수 없습니다',
            '영구적으로', '제거', '초기화', '취소', '중요한', '신중하게'
        ];
        
        // 패턴 매칭
        if (successPatterns.some(pattern => lowerMessage.includes(pattern))) {
            return 'success';
        }
        
        if (errorPatterns.some(pattern => lowerMessage.includes(pattern))) {
            return 'error';
        }
        
        if (warningPatterns.some(pattern => lowerMessage.includes(pattern))) {
            return 'warning';
        }
        
        return 'info';
    }

    // 모달 생성
    createModal(icon, title, message, buttonClass) {
        const modal = document.createElement('div');
        modal.className = 'alert-modal-overlay';
        modal.innerHTML = `
            <div class="alert-modal-content">
                <div class="alert-modal-icon">${icon}</div>
                <h2 class="alert-modal-title">${title}</h2>
                <p class="alert-modal-message">${message}</p>
                <button class="alert-modal-button ${buttonClass}" onclick="window.alertSystem.closeModal()">확인</button>
            </div>
        `;
        
        // 배경 클릭으로 닫기
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });
        
        return modal;
    }

    // 모달 닫기
    closeModal() {
        const existingModal = document.querySelector('.alert-modal-overlay');
        if (existingModal) {
            existingModal.style.animation = 'fadeIn 0.2s ease reverse';
            setTimeout(() => {
                if (existingModal.parentNode) {
                    existingModal.parentNode.removeChild(existingModal);
                }
            }, 200);
        }
    }

    // 키보드 이벤트 설정
    setupKeyboardEvents() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }
}

// ============================
// 전역 함수들 (기존 코드 호환성)
// ============================

// 메인 Alert 함수들
function showAlert(message, type = 'auto', title = null) {
    window.alertSystem.showAlert(message, type, title);
}

function showToast(message, type = 'auto', duration = 3000) {
    window.alertSystem.showToast(message, type, duration);
}

function showConfirm(message, title = '확인') {
    return window.alertSystem.showConfirm(message, title);
}

// 타입별 전용 함수들
function showSuccess(message, title = '성공') {
    showAlert(message, 'success', title);
}

function showError(message, title = '오류') {
    showAlert(message, 'error', title);
}

function showWarning(message, title = '경고') {
    showAlert(message, 'warning', title);
}

function showInfo(message, title = '알림') {
    showAlert(message, 'info', title);
}

// ============================
// 초기화
// ============================
document.addEventListener('DOMContentLoaded', function() {
    // Alert 시스템 초기화
    window.alertSystem = new AlertSystem();
    
    console.log('🎨 Alert 시스템이 로드되었습니다!');
});

// 즉시 초기화 (DOMContentLoaded 이전에도 작동)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (!window.alertSystem) {
            window.alertSystem = new AlertSystem();
        }
    });
} else {
    window.alertSystem = new AlertSystem();
}