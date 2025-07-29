#!/usr/bin/env python3
"""
모든 HTML 파일에서 API_BASE_URL 하드코딩을 제거하고 config.js를 import하도록 수정하는 스크립트
"""

import os
import re
from pathlib import Path

def update_html_files():
    # front 디렉토리 경로
    front_dir = Path("app/front")
    
    # 모든 HTML 파일 찾기
    html_files = list(front_dir.rglob("*.html"))
    
    for html_file in html_files:
        print(f"처리 중: {html_file}")
        
        # 파일 읽기
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 변경사항 추적
        original_content = content
        
        # 1. API_BASE_URL 하드코딩 제거
        content = re.sub(
            r'const\s+API_BASE_URL\s*=\s*[\'"][^\'"]*[\'"];?\s*',
            '// API_BASE_URL은 config.js에서 자동으로 설정됨',
            content
        )
        
        # 2. window.API_BASE_URL || 'http://localhost:8000' 패턴 제거
        content = re.sub(
            r'window\.API_BASE_URL\s*\|\|\s*[\'"][^\'"]*[\'"]',
            'window.API_BASE_URL',
            content
        )
        
        # 3. config.js import 추가 (이미 있는지 확인)
        if 'config.js' not in content:
            # </body> 태그 바로 앞에 config.js import 추가
            if '</body>' in content:
                config_script = '    <script src="../../js/config.js"></script>\n'
                content = content.replace('</body>', f'{config_script}</body>')
            else:
                # </body>가 없으면 첫 번째 <script> 태그 앞에 추가
                script_match = re.search(r'<script>', content)
                if script_match:
                    config_script = '    <script src="../../js/config.js"></script>\n'
                    content = content[:script_match.start()] + config_script + content[script_match.start():]
        
        # 변경사항이 있으면 파일 저장
        if content != original_content:
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 수정 완료: {html_file}")
        else:
            print(f"ℹ️ 변경사항 없음: {html_file}")

if __name__ == "__main__":
    update_html_files()
    print("\n모든 파일 수정이 완료되었습니다!") 