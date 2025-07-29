// API 설정을 동적으로 관리하는 공통 설정 파일
(function() {
    // 현재 도메인을 기반으로 API_BASE_URL 설정
    function getApiBaseUrl() {
        // 개발 환경에서는 localhost:8000 사용
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return 'http://localhost:8000';
        }
        
        // 프로덕션 환경에서는 현재 도메인 사용
        const protocol = window.location.protocol;
        const hostname = window.location.hostname;
        const port = window.location.port ? `:${window.location.port}` : '';
        
        return `${protocol}//${hostname}${port}`;
    }
    
    // 전역 변수로 설정
    window.API_BASE_URL = getApiBaseUrl();
    
    // 콘솔에 현재 설정 출력 (디버깅용)
    console.log('API_BASE_URL 설정됨:', window.API_BASE_URL);
})(); 