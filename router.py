import os
import json
import redis
import urllib3
import base64

# 환경변수 선언부 (가장 위)
REDIS_HOST = os.environ.get("REDIS_HOST", "master.candiy-api-prod-load-cache.draade.apn2.cache.amazonaws.com")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
TRANSACTION_TIMEOUT = int(os.environ.get("TRANSACTION_TIMEOUT", 300))
SERVICE_ENV = os.environ.get("SERVICE_ENV", "staging")  # 예: local, staging, produnction 등

# Redis 클라이언트 초기화 (decode_responses=True 로 str 반환)
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True);


# HTTP 클라이언트
http = urllib3.PoolManager()

def get_worker_for_transaction_id(transaction_id: str):
    try:
        return r.get(f"candiy-api:{SERVICE_ENV}:transaction_id:{transaction_id}")
    except Exception as e:
        print(f"Redis error getting worker for transaction {transaction_id}: {e}")
        return None

def get_active_workers():
    try:
        keys = r.keys(f"candiy-api:{SERVICE_ENV}:active-server:*")
        workers = {}
        for key in keys:
            value = r.get(key)
            if value:
                workers[key] = value
        return workers
    except Exception as e:
        print(f"Redis error getting active workers: {e}")
        return {}

def get_low_load_worker(workers: dict):
    if not workers:
        return None
    
    min_worker = None
    min_count = float('inf')
    
    for worker_key in workers.keys():
        transaction_keys = r.keys(worker_key.replace("active-server", "active-transaction") + ":transaction_id:*")
        count = len(transaction_keys)
        if count < min_count:
            min_count = count
            min_worker = workers[worker_key]
    
    return min_worker

def get_transaction_id_worker_server_url(transaction_id: str):
    worker_host = get_worker_for_transaction_id(transaction_id)
    if not worker_host:
        return None
    active_server = r.get(worker_host)
    return active_server

def lambda_handler(event, context):
    try:
        path = event.get("path")
        method = event.get("httpMethod")
        headers = event.get("headers", {})
        body = event.get("body", "")
        is_base64_encoded = event.get("isBase64Encoded", False)
        if is_base64_encoded and body:
            body = base64.b64decode(body).decode('utf-8')

        # JSON body 파싱 시도
        try:
            body_json = json.loads(body) if body else {}
        except Exception:
            body_json = {}

        workers = get_active_workers()

        # transactionId 추출 (multiFactorInfo.transactionId)
        tid = None
        if isinstance(body_json, dict):
            mfi = body_json.get("multiFactorInfo")
            if mfi:
                tid = mfi.get("transactionId")

        worker_server_url = None
        if tid:
            worker_server_url = get_transaction_id_worker_server_url(tid)
            if not worker_server_url:
                worker_server_url = get_low_load_worker(workers)
        else:
            worker_server_url = get_low_load_worker(workers)

        if not worker_server_url:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "No available worker"}),
                "headers": {"Content-Type": "application/json"}
            }

        target_url = f"http://{worker_server_url}{path}"

        response = http.request(
            method=method,
            url=target_url,
            body=body if body else None,
            headers=headers,
            timeout=60.0,
            retries=False
        )

        resp_body = response.data.decode('utf-8')

        return {
            "statusCode": response.status,
            "body": resp_body,
            "headers": dict(response.headers),
            "isBase64Encoded": False
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }