import os
import uuid
from flask import Blueprint, request, jsonify
from app.models import UserHistory
from app.extensions import db
from app.services.answer_engine import solve_pipeline
from app.services.llm_service import solve_with_vision
from flask_login import login_required, current_user

search_bp = Blueprint('search', __name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'instance', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}

def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set

# ----------------------------------------------------------------
# 核心路由：语义搜索接口 (ML 矩阵架构)
# ----------------------------------------------------------------
@search_bp.route('/search', methods=['POST'])
def search_question():
    user_query = request.json.get('query', '').strip()
    if not user_query:
        return jsonify({"success": False, "message": "请输入题目"})
    
    # 获取当前用户ID（如果已登录）
    user_id = current_user.id if current_user.is_authenticated else None
    
    # Pipeline 内部已处理核心逻辑与入库，传入 user_id 用于保存历史
    result = solve_pipeline(user_query, user_id=user_id)
    
    # 获取刚刚存入的记录 ID (增加 user_id 过滤以防只会拿到别人的)
    query = UserHistory.query.filter_by(question=user_query)
    if user_id:
        query = query.filter_by(user_id=user_id)
        
    last_rec = query.order_by(UserHistory.id.desc()).first()

    return jsonify({
        "success": True,
        "data": {
            **result,
            "id": last_rec.id if last_rec else None,
            "is_mistake": last_rec.is_mistake if last_rec else False
        }
    })

@search_bp.route('/solve', methods=['POST'])
@login_required
def solve():
    """传统 Pipeline 接口,solve_pipeline 通常内部集成了数据库检索 + AI 生成"""
    data = request.json
    return jsonify(solve_pipeline(data.get('question', ''), data.get('options', []), user_id=current_user.id))

@search_bp.route('/solve-image', methods=['POST'])
@login_required
def solve_image():
    """视觉路由：图片搜题 (Vision ML)"""
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': '无效图片文件'}), 400
    if not allowed_file(file.filename, ALLOWED_IMAGE_EXTS):
        return jsonify({'error': '不支持的图片格式'}), 400

    temp_path = os.path.join(UPLOAD_FOLDER, f"vision_{uuid.uuid4()}.jpg")
    file.save(temp_path)

    try:
        # 1. 调用视觉引擎识别
        ai_res = solve_with_vision(temp_path)
        
        # 2. 返回规范化的 JSON，并交由前端处理入库 (分离解耦)
        # 注：为了完全兼容您现有的实现，原本的数据库入库也在此一并保留
        history = UserHistory(
            question="[图片搜题]",
            answer=ai_res.get('answer', '未识别出答案'),
            reason=ai_res.get('reason', '无解析'),
            source="图片搜题",
            category=ai_res.get('category', '其他'),
            user_id=current_user.id
        )
        db.session.add(history)
        db.session.commit()
        
        return jsonify({
            'id': history.id,
            'answer': history.answer,
            'reason': history.reason,
            'category': history.category,
            'source': '图片搜题'
        })
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)