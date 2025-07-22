from flask import Blueprint, jsonify
from flask_pydantic import validate

from app.logger import logger
from app.services.ai import add_ai_trade_task
from app.schemas.ai import TradeAdviceReq

tool_bp = Blueprint('tool', __name__)

@tool_bp.route('/tool/', methods=['POST'])
@validate(body=TradeAdviceReq)
def ai_trade_route(body: TradeAdviceReq):
    task_id = add_ai_trade_task(req=body)
    logger.info("Trade advice task created with ID: %s", task_id)
    return jsonify({"task_id": task_id}), 202
