import boto3
import os
from botocore.exceptions import ClientError
from typing import Dict, List, Optional
import json
from datetime import datetime
from app.core.config import settings

class DynamoDBManager:
    def __init__(self):
        self.region = None
        self.table_name = None
        self.dynamodb = None
        self.table = None
        self._initialized = False
    
    def _initialize(self):
        """지연 초기화 - 실제 사용 시점에 초기화"""
        if self._initialized:
            return
            
        # 디버그: 환경변수 확인
        print("=== DynamoDB 초기화 시작 ===")
        print(f"DYNAMODB_REGION: {settings.DYNAMODB_REGION}")
        print(f"DYNAMODB_TABLE_NAME: {settings.DYNAMODB_TABLE_NAME}")
        print(f"DYNAMODB_USER_ACCESS_KEY_ID: {settings.DYNAMODB_USER_ACCESS_KEY_ID[:10]}..." if settings.DYNAMODB_USER_ACCESS_KEY_ID else "None")
        print(f"DYNAMODB_USER_SECRET_ACCESS_KEY: {settings.DYNAMODB_USER_SECRET_ACCESS_KEY[:10]}..." if settings.DYNAMODB_USER_SECRET_ACCESS_KEY else "None")
        
        self.region = settings.DYNAMODB_REGION or "ap-northeast-2"
        self.table_name = settings.DYNAMODB_TABLE_NAME or "testdb"
        
        # DynamoDB 클라이언트 설정 (config.py의 settings 사용)
        try:
            self.dynamodb = boto3.resource(
                'dynamodb',
                region_name=self.region,
                aws_access_key_id=settings.DYNAMODB_USER_ACCESS_KEY_ID,
                aws_secret_access_key=settings.DYNAMODB_USER_SECRET_ACCESS_KEY
            )
            print("DynamoDB 리소스 생성 성공")
        except Exception as e:
            print(f"DynamoDB 리소스 생성 실패: {e}")
            raise
        
        self.table = self.dynamodb.Table(self.table_name)
        self._ensure_table_exists()
        self._initialized = True
        print("=== DynamoDB 초기화 완료 ===")
    
    def _ensure_table_exists(self):
        """테이블이 존재하지 않으면 생성"""
        try:
            self.table.load()
            print(f"DynamoDB 테이블 '{self.table_name}' 연결 성공")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"테이블 '{self.table_name}'이 존재하지 않습니다. 생성합니다...")
                self._create_table()
            else:
                print(f"DynamoDB 연결 오류: {e}")
    
    def _create_table(self):
        """채팅 메시지 테이블 생성"""
        try:
            self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {
                        'AttributeName': 'channel_id',
                        'KeyType': 'HASH'  # Partition key
                    },
                    {
                        'AttributeName': 'message_id',
                        'KeyType': 'RANGE'  # Sort key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'channel_id',
                        'AttributeType': 'S'  # String 타입으로 변경
                    },
                    {
                        'AttributeName': 'message_id',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'user_id',
                        'AttributeType': 'S'  # String 타입으로 변경
                    },
                    {
                        'AttributeName': 'timestamp',
                        'AttributeType': 'S'
                    }
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'UserMessagesIndex',
                        'KeySchema': [
                            {
                                'AttributeName': 'user_id',
                                'KeyType': 'HASH'
                            },
                            {
                                'AttributeName': 'timestamp',
                                'KeyType': 'RANGE'
                            }
                        ],
                        'Projection': {
                            'ProjectionType': 'ALL'
                        },
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 10,
                    'WriteCapacityUnits': 10
                }
            )
            print(f"DynamoDB 테이블 '{self.table_name}' 생성 완료")
        except Exception as e:
            print(f"테이블 생성 오류: {e}")
    
    async def save_message(self, message_data: Dict) -> str:
        """메시지 저장"""
        self._initialize()
        
        try:
            # 고유한 message_id 생성 (채널ID_타임스탬프_사용자ID)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            message_id = f"{message_data['channel_id']}_{timestamp}_{message_data['user_id']}"
            
            item = {
                'channel_id': str(message_data['channel_id']),  # 문자열로 변환
                'message_id': message_id,
                'user_id': str(message_data['user_id']),  # 문자열로 변환
                'user_name': message_data['user_name'],
                'content': message_data['content'],
                'message_type': message_data.get('message_type', 'text'),
                'timestamp': datetime.now().isoformat(),
                'reply_to': message_data.get('reply_to'),
                'mentions': json.dumps(message_data.get('mentions', [])) if message_data.get('mentions') else None
            }
            
            self.table.put_item(Item=item)
            print(f"메시지 저장 완료: {message_id}")
            return message_id
            
        except Exception as e:
            print(f"메시지 저장 오류: {e}")
            return None
    
    async def get_messages(self, channel_id: int, limit: int = 50, last_key: Optional[str] = None) -> List[Dict]:
        """채널의 메시지 조회"""
        self._initialize()
        
        try:
            # Query를 사용하여 특정 채널의 메시지만 조회
            query_kwargs = {
                'KeyConditionExpression': boto3.dynamodb.conditions.Key('channel_id').eq(str(channel_id)),  # 문자열로 변환
                'Limit': limit,
                'ScanIndexForward': False  # 최신 메시지부터
            }
            
            if last_key:
                query_kwargs['ExclusiveStartKey'] = {'channel_id': str(channel_id), 'message_id': last_key}
            
            response = self.table.query(**query_kwargs)
            messages = response.get('Items', [])
            
            # 시간순 정렬 (최신순)
            messages.sort(key=lambda x: x['timestamp'], reverse=True)
            
            print(f"채널 {channel_id}에서 {len(messages)}개 메시지 조회 완료")
            return messages[:limit]
            
        except Exception as e:
            print(f"메시지 조회 오류: {e}")
            return []
    
    async def delete_message(self, channel_id: int, message_id: str, user_id: int) -> bool:
        """메시지 삭제 (작성자만 가능)"""
        self._initialize()
        
        try:
            # 메시지 조회
            response = self.table.get_item(
                Key={
                    'channel_id': str(channel_id),  # 문자열로 변환
                    'message_id': message_id
                }
            )
            
            if 'Item' not in response:
                return False
            
            item = response['Item']
            if item['user_id'] != str(user_id):  # 문자열로 비교
                return False  # 작성자가 아님
            
            # 메시지 삭제
            self.table.delete_item(
                Key={
                    'channel_id': str(channel_id),  # 문자열로 변환
                    'message_id': message_id
                }
            )
            print(f"메시지 삭제 완료: {message_id}")
            return True
            
        except Exception as e:
            print(f"메시지 삭제 오류: {e}")
            return False

# 전역 인스턴스
dynamodb_manager = DynamoDBManager() 