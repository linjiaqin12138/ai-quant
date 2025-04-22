#!/bin/bash

# 设置API基础URL
API_URL="http://localhost:5000/api/ai/trade-advice"

# 设置输出颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 测试函数
test_api() {
    local test_name=$1
    local payload=$2
    local expected_status=$3

    echo -e "\n${GREEN}Running test: ${test_name}${NC}"
    echo "Payload: $payload"
    
    # 发送请求并保存响应
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        $API_URL)

    # 提取状态码
    status_code=$(echo "$response" | tail -n1)
    # 提取响应体
    body=$(echo "$response" | sed '$d')

    echo "Response: $body"
    echo "Status code: $status_code"

    # 验证状态码
    if [ "$status_code" -eq "$expected_status" ]; then
        echo -e "${GREEN}✓ Test passed${NC}"
    else
        echo -e "${RED}✗ Test failed. Expected status $expected_status but got $status_code${NC}"
    fi
}

# 成功用例
valid_payload='{
    "symbol": "BTC/USDT",
    "market": "crypto",
    "riskPrefer": "risk_averse",
    "strategyPrefer": "long_term",
    "llmSettings": [{
        "model": "gpt-3.5-turbo",
        "temperature": 0.7
    }],
    "historys": [],
    "holdAmount": 0.1,
    "remaining": 1.0,
    "callbackUrl": "http://example.com",
    "id": "123"
}'

# 无效用例 - 缺少必需字段
invalid_payload='{
    "symbol": "BTC/USDT",
    "market": "crypto"
}'

# 无效用例 - 非法的风险偏好值
invalid_risk_payload='{
    "symbol": "BTC/USDT",
    "market": "crypto",
    "riskPrefer": "非法值",
    "strategyPrefer": "long_term",
    "llmSettings": [{
        "model": "gpt-3.5-turbo",
        "temperature": 0.7
    }],
    "historys": [],
    "holdAmount": 0.1,
    "remaining": 1.0,
    "callbackUrl": "http://example.com",
    "id": "123"
}'

# 运行测试
echo "Starting API tests..."

# 测试有效请求
test_api "Valid request" "$valid_payload" 202

# 测试无效请求 - 缺少字段
test_api "Invalid request - Missing fields" "$invalid_payload" 422

# 测试无效请求 - 非法的风险偏好值
test_api "Invalid request - Invalid risk prefer" "$invalid_risk_payload" 422

echo -e "\nAll tests completed!"