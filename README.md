# Candiy API Router

AWS Lambda 기반 API 로드 밸런서로, Redis를 사용하여 워커 서버들 간의 트래픽을 지능적으로 분산합니다.

## 주요 기능

- **트랜잭션 기반 라우팅**: 동일한 트랜잭션 ID는 같은 워커로 라우팅
- **부하 기반 분산**: 활성 트랜잭션이 가장 적은 워커 선택
- **자동 장애 복구**: 사용 가능한 워커가 없을 경우 에러 응답

## 아키텍처

```
Client → AWS Lambda (API Gateway) → Redis (워커 정보) → Backend Workers
```

## 환경 변수

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `REDIS_HOST` | `master.candiy-api-prod-load-cache.draade.apn2.cache.amazonaws.com` | Redis 호스트 |
| `REDIS_PORT` | `6379` | Redis 포트 |
| `REDIS_DB` | `0` | Redis 데이터베이스 번호 |
| `TRANSACTION_TIMEOUT` | `300` | 트랜잭션 타임아웃 (초) |
| `SERVICE_ENV` | `staging` | 서비스 환경 (local, staging, production) |

## Redis 키 구조

- `candiy-api:{SERVICE_ENV}:transaction_id:{transaction_id}` - 트랜잭션 ID와 워커 매핑
- `candiy-api:{SERVICE_ENV}:active-server:*` - 활성 워커 서버 정보
- `candiy-api:{SERVICE_ENV}:active-transaction:*` - 활성 트랜잭션 정보

## 라우팅 로직

1. 요청 body에서 `multiFactorInfo.transactionId` 추출
2. 트랜잭션 ID가 있으면 기존 할당된 워커로 라우팅
3. 트랜잭션 ID가 없거나 할당된 워커가 없으면 부하가 낮은 워커 선택
4. 선택된 워커로 HTTP 요청 프록시

## 배포

AWS Lambda로 배포하여 사용합니다.

```bash
# 의존성 설치
pip install redis urllib3

# ZIP 패키지 생성 후 Lambda에 업로드
```

## 에러 처리

- 사용 가능한 워커가 없으면 500 에러 반환
- 워커 서버 오류 시 해당 상태 코드 반환
- 예외 발생 시 500 에러와 에러 메시지 반환