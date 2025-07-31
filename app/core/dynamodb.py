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
        # print("=== DynamoDB 초기화 시작 ===")
        # print(f"DYNAMODB_REGION: {settings.DYNAMODB_REGION}")
        # print(f"DYNAMODB_TABLE_NAME: {settings.DYNAMODB_TABLE_NAME}")
        # print(f"DYNAMODB_USER_ACCESS_KEY_ID: {settings.DYNAMODB_USER_ACCESS_KEY_ID[:10]}..." if settings.DYNAMODB_USER_ACCESS_KEY_ID else "None")
        # print(f"DYNAMODB_USER_SECRET_ACCESS_KEY: {settings.DYNAMODB_USER_SECRET_ACCESS_KEY[:10]}..." if settings.DYNAMODB_USER_SECRET_ACCESS_KEY else "None")
        
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
            # print("DynamoDB 리소스 생성 성공")
        except Exception as e:
            # print(f"DynamoDB 리소스 생성 실패: {e}")
            raise
        
        self.table = self.dynamodb.Table(self.table_name)
        self._ensure_table_exists()
        self._initialized = True
        # print("=== DynamoDB 초기화 완료 ===")
    
    def _ensure_table_exists(self):
        """테이블이 존재하지 않으면 생성"""
        try:
            self.table.load()
            # print(f"DynamoDB 테이블 '{self.table_name}' 연결 성공")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # print(f"테이블 '{self.table_name}'이 존재하지 않습니다. 생성합니다...")
                self._create_table()
            else:
                # print(f"DynamoDB 연결 오류: {e}")
                pass
    
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
                        'AttributeName': 'timestamp',
                        'KeyType': 'RANGE'  # Sort key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'channel_id',
                        'AttributeType': 'S'  # String 타입
                    },
                    {
                        'AttributeName': 'timestamp',
                        'AttributeType': 'S'  # String 타입
                    },
                    {
                        'AttributeName': 'user_id',
                        'AttributeType': 'S'  # String 타입
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
            # print(f"DynamoDB 테이블 '{self.table_name}' 생성 완료")
        except Exception as e:
            # print(f"테이블 생성 오류: {e}")
            pass
    
    def recreate_table(self):
        """테이블을 삭제하고 재생성 (주의: 모든 데이터가 삭제됩니다)"""
        self._initialize()
        
        try:
            # 테이블 삭제
            # print(f"테이블 '{self.table_name}' 삭제 중...")
            self.table.delete()
            
            # 삭제 완료까지 대기
            waiter = self.dynamodb.meta.client.get_waiter('table_not_exists')
            waiter.wait(TableName=self.table_name)
            # print(f"테이블 '{self.table_name}' 삭제 완료")
            
            # 테이블 재생성
            # print(f"테이블 '{self.table_name}' 재생성 중...")
            self._create_table()
            
            # 생성 완료까지 대기
            waiter = self.dynamodb.meta.client.get_waiter('table_exists')
            waiter.wait(TableName=self.table_name)
            # print(f"테이블 '{self.table_name}' 재생성 완료")
            
            # 테이블 객체 재설정
            self.table = self.dynamodb.Table(self.table_name)
            
        except Exception as e:
            # print(f"테이블 재생성 오류: {e}")
            raise
    
    async def save_message(self, message_data: Dict) -> str:
        """메시지 저장"""
        self._initialize()
        
        try:
            # 고유한 message_id 생성 (채널ID_타임스탬프_사용자ID)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            message_id = f"{message_data['channel_id']}_{timestamp}_{message_data['user_id']}"
            
            # ISO 형식의 timestamp (Sort Key용)
            iso_timestamp = datetime.now().isoformat()
            
            item = {
                'channel_id': str(message_data['channel_id']),  # 문자열로 변환
                'timestamp': iso_timestamp,  # Sort Key
                'message_id': message_id,  # 고유 ID
                'user_id': str(message_data['user_id']),  # 문자열로 변환
                'user_name': message_data['user_name'],
                'content': message_data['content'],
                'message_type': message_data.get('message_type', 'text'),
                'reply_to': message_data.get('reply_to'),
                'mentions': json.dumps(message_data.get('mentions', [])) if message_data.get('mentions') else None
            }
            
            self.table.put_item(Item=item)
            # print(f"메시지 저장 완료: {message_id}")
            return message_id
            
        except Exception as e:
            # print(f"메시지 저장 오류: {e}")
            return None
    
    async def get_messages(self, channel_id: int, limit: int = 50, last_key: Optional[str] = None) -> List[Dict]:
        """채널의 메시지 조회"""
        self._initialize()
        
        try:
            # Query를 사용하여 특정 채널의 메시지만 조회
            query_kwargs = {
                'KeyConditionExpression': boto3.dynamodb.conditions.Key('channel_id').eq(str(channel_id)),  # 문자열로 변환
                'Limit': limit,
                'ScanIndexForward': True  # 오래된 메시지부터 (시간순)
            }
            
            if last_key:
                query_kwargs['ExclusiveStartKey'] = {'channel_id': str(channel_id), 'timestamp': last_key}
            
            response = self.table.query(**query_kwargs)
            messages = response.get('Items', [])
            
            # 시간순 정렬 (오래된 순) - timestamp Sort Key로 이미 정렬됨
            # messages.sort(key=lambda x: x['timestamp'], reverse=False)  # 불필요
            
            # print(f"채널 {channel_id}에서 {len(messages)}개 메시지 조회 완료")
            return messages[:limit]
            
        except Exception as e:
            # print(f"메시지 조회 오류: {e}")
            return []

    async def get_latest_messages(self, channel_id: int, limit: int = 50) -> List[Dict]:
        """채널의 최신 메시지 조회 (시간순 정렬)"""
        self._initialize()
        
        try:
            # Query를 사용하여 특정 채널의 메시지만 조회
            query_kwargs = {
                'KeyConditionExpression': boto3.dynamodb.conditions.Key('channel_id').eq(str(channel_id)),
                'Limit': limit,
                'ScanIndexForward': False  # 최신 메시지부터 (역순)
            }
            
            response = self.table.query(**query_kwargs)
            messages = response.get('Items', [])
            
            # 시간순으로 정렬 (오래된 순)
            messages.sort(key=lambda x: x['timestamp'])
            
            # print(f"채널 {channel_id}에서 최신 {len(messages)}개 메시지 조회 완료")
            return messages[:limit]
            
        except Exception as e:
            # print(f"최신 메시지 조회 오류: {e}")
            return []

    async def get_messages_after_join(self, channel_id: int, join_timestamp: str, limit: int = 50) -> List[Dict]:
        """채널 가입 시간 이후의 메시지 조회"""
        self._initialize()
        
        try:
            # KeyConditionExpression을 사용하여 timestamp 범위를 직접 지정 (더 효율적)
            query_kwargs = {
                'KeyConditionExpression': (
                    boto3.dynamodb.conditions.Key('channel_id').eq(str(channel_id)) &
                    boto3.dynamodb.conditions.Key('timestamp').gte(join_timestamp)
                ),
                'Limit': limit,
                'ScanIndexForward': True  # 오래된 메시지부터 (시간순)
            }
            
            response = self.table.query(**query_kwargs)
            messages = response.get('Items', [])
            
            # print(f"채널 {channel_id}에서 가입 시간({join_timestamp}) 이후 {len(messages)}개 메시지 조회 완료")
            return messages[:limit]
            
        except Exception as e:
            # print(f"가입 시간 이후 메시지 조회 오류: {e}")
            return []

    async def get_older_messages(self, channel_id: int, before_timestamp: str, limit: int = 50) -> List[Dict]:
        """지정된 시간 이전의 더 오래된 메시지 조회"""
        self._initialize()
        
        try:
            # KeyConditionExpression을 사용하여 timestamp 범위를 직접 지정
            query_kwargs = {
                'KeyConditionExpression': (
                    boto3.dynamodb.conditions.Key('channel_id').eq(str(channel_id)) &
                    boto3.dynamodb.conditions.Key('timestamp').lt(before_timestamp)
                ),
                'Limit': limit,
                'ScanIndexForward': False  # 최신 메시지부터 (역순으로 가져와서 시간순 정렬)
            }
            
            response = self.table.query(**query_kwargs)
            messages = response.get('Items', [])
            
            # 시간순으로 정렬 (오래된 순)
            messages.sort(key=lambda x: x['timestamp'])
            
            # print(f"채널 {channel_id}에서 {before_timestamp} 이전 {len(messages)}개 메시지 조회 완료")
            return messages[:limit]
            
        except Exception as e:
            # print(f"이전 메시지 조회 오류: {e}")
            return []
    
    async def delete_message(self, channel_id: int, message_id: str, user_id: int) -> bool:
        """메시지 삭제 (작성자만 가능)"""
        self._initialize()
        
        try:
            # 메시지 조회 (message_id로 검색)
            response = self.table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('message_id').eq(message_id) & 
                                boto3.dynamodb.conditions.Attr('channel_id').eq(str(channel_id))
            )
            
            if not response.get('Items'):
                return False
            
            item = response['Items'][0]
            if item['user_id'] != str(user_id):  # 문자열로 비교
                return False  # 작성자가 아님
            
            # 메시지 삭제 (timestamp Sort Key 사용)
            self.table.delete_item(
                Key={
                    'channel_id': str(channel_id),  # 문자열로 변환
                    'timestamp': item['timestamp']
                }
            )
            # print(f"메시지 삭제 완료: {message_id}")
            return True
            
        except Exception as e:
            # print(f"메시지 삭제 오류: {e}")
            return False

    async def delete_channel_messages(self, channel_id: int) -> bool:
        """채널의 모든 메시지 삭제"""
        self._initialize()
        
        try:
            # 채널의 모든 메시지 조회
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('channel_id').eq(str(channel_id)),
                ProjectionExpression='timestamp'  # timestamp Sort Key만 가져오기
            )
            
            messages = response.get('Items', [])
            # print(f"채널 {channel_id}에서 조회된 메시지 수: {len(messages)}")
            
            if not messages:
                # print(f"채널 {channel_id}에 삭제할 메시지가 없습니다.")
                return True
            
            # 조회 결과 로깅 (디버깅용)
            # print(f"조회된 메시지들: {messages[:3]}...")  # 처음 3개만 출력
            
            # 모든 메시지 삭제
            with self.table.batch_writer() as batch:
                for message in messages:
                    if 'timestamp' not in message:
                        # print(f"timestamp가 없는 메시지: {message}")
                        continue
                    
                    try:
                        batch.delete_item(
                            Key={
                                'channel_id': str(channel_id),
                                'timestamp': message['timestamp']
                            }
                        )
                    except Exception as delete_error:
                        # print(f"메시지 삭제 실패 - channel_id: {channel_id}, timestamp: {message.get('timestamp')}, 오류: {delete_error}")
                        continue
            
            # print(f"채널 {channel_id}의 {len(messages)}개 메시지 삭제 완료")
            return True
            
        except Exception as e:
            # print(f"채널 메시지 삭제 오류: {e}")
            return False

# 전역 인스턴스
dynamodb_manager = DynamoDBManager() 