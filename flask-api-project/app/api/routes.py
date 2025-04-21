from flask import Blueprint, jsonify, request
from app.api.aisimtrade import req_hander
api = Blueprint('api', __name__)

@api.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@api.route('/ai/simtrade', methods=['POST'])
def ai_simulate_trade():
    """
    {
        "callbackUrl": "http://localhost:5000/ai/simtrade",
        "id": "50738043-a339-4508-bd73-4f3582088f7a",
        "market": "crypto",
        "symbol": "BTCUSDT",
        "riskPrefer": "成长投资",
        "strategyPrefer": "中长期",
        "llmSettings": [{
            "model": "gpt-3.5-turbo",
            "temperature": 0.2
        }],
        "historys": [
            {
                "timestamp": 1744277400,
                "action": "buy",
                "cost": 5000,
                "amount": null,
                "price": 33500,
                "reason": "BTC市场处于关键支撑位，RSI指标出现超卖信号，且成交量有所增加，是较好的买入时机。",
                "summary": "根据技术分析，比特币价格已经在33000-34000区间获得了良好支撑，MACD指标显示看涨背离，表明短期可能有反弹机会。考虑到整体市场情绪有所改善，建议以当前价格分配部分资金买入BTC。"
            }
            ...
        ],
        "holdAmount": 0,
        "remaining": 0
        }
    """
    data = request.json
    req_hander(reqBody=data)
    return {}, 202

@api.route('/data/<int:data_id>', methods=['GET'])
def get_data(data_id):
    # Here you would typically retrieve the data from a database
    return jsonify({"data_id": data_id, "data": "Sample data"}), 200

@api.route('/data/<int:data_id>', methods=['DELETE'])
def delete_data(data_id):
    # Here you would typically delete the data from a database
    return jsonify({"message": "Data deleted", "data_id": data_id}), 204