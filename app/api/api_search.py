import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import filetype
from app.models import UserHistory
from app.extensions import db
from app.services.answer_engine import solve_pipeline
from app.services.llm_service import solve_with_vision
from app.services.async_task import task_mgr
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

    user_id = current_user.id if current_user.is_authenticated else None
    app = current_app._get_current_object()

    def _search():
        result = solve_pipeline(user_query, user_id=user_id)
        # 获取刚刚存入的记录 ID
        query = UserHistory.query.filter_by(question=user_query)
        if user_id:
            query = query.filter_by(user_id=user_id)
        last_rec = query.order_by(UserHistory.id.desc()).first()
        return {
            "success": True,
            "data": {
                **result,
                "id": last_rec.id if last_rec else None,
                "is_mistake": last_rec.is_mistake if last_rec else False
            }
        }

    owner = str(user_id) if user_id else request.cookies.get('session', 'anon')
    task_id = task_mgr.submit(_search, app=app, owner=owner)
    return jsonify({"success": True, "task_id": task_id}), 202

@search_bp.route('/solve', methods=['POST'])
@login_required
def solve():
    """传统 Pipeline 接口"""
    data = request.json
    uid = current_user.id
    question = data.get('question', '')
    options = data.get('options', [])
    app = current_app._get_current_object()

    def _solve():
        return solve_pipeline(question, options, user_id=uid)

    task_id = task_mgr.submit(_solve, app=app, owner=str(uid))
    return jsonify({"success": True, "task_id": task_id}), 202

@search_bp.route('/solve-image', methods=['POST'])
@login_required
def solve_image():
    """视觉路由：图片搜题 (Vision ML)"""
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'success': False, 'message': '无效图片文件'}), 400
    if not allowed_file(file.filename, ALLOWED_IMAGE_EXTS):
        return jsonify({'success': False, 'message': '不支持的图片格式'}), 400

    # 安全提取原文件的真实后缀，防止统统保存为 .jpg 导致图片库解析报错
    safe_filename = secure_filename(file.filename) or "unnamed.jpg"
    ext = safe_filename.lower().split('.')[-1]
    
    temp_path = os.path.join(UPLOAD_FOLDER, f"vision_{uuid.uuid4()}.{ext}")
    file.save(temp_path)

    # 嗅探文件真实的 Magic Number，拦截伪装后缀的恶意文件
    kind = filetype.guess(temp_path)
    if kind is None or kind.extension not in ALLOWED_IMAGE_EXTS:
        os.remove(temp_path)
        return jsonify({'success': False, 'message': '伪装的图片文件已被拦截'}), 400

    uid = current_user.id
    app = current_app._get_current_object()

    def _solve_img():
        try:
            ai_res = solve_with_vision(temp_path)
            # 入库
            history = UserHistory(
                question="[图片搜题]",
                answer=ai_res.get('answer', '未识别出答案'),
                reason=ai_res.get('reason', '无解析'),
                source="图片搜题",
                category=ai_res.get('category', '其他'),
                user_id=uid
            )
            db.session.add(history)
            db.session.commit()
            return {
                'id': history.id,
                'answer': history.answer,
                'reason': history.reason,
                'category': history.category,
                'source': '图片搜题'
            }
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)

    task_id = task_mgr.submit(_solve_img, app=app, owner=str(uid))
    return jsonify({'success': True, 'task_id': task_id}), 202