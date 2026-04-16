import os
import uuid
import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import filetype
from app.models import UserHistory
from app.extensions import db
from app.services.answer_engine import solve_pipeline, save_question_to_db, save_to_history
from app.services.llm_service import solve_with_vision
from app.services.async_task import task_mgr
from flask_login import login_required, current_user
from app.services.nlp_service import nlp_engine

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
    if not nlp_engine.is_ready:
        return jsonify({"success": False, "message": "深度学习引擎初始化中，请等候数秒再尝试搜索..."}), 503

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
    if not nlp_engine.is_ready:
        return jsonify({"success": False, "message": "深度学习引擎初始化中，请稍后再试..."}), 503
        
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
    if not nlp_engine.is_ready:
        return jsonify({"success": False, "message": "引擎预热中，功能暂时不可用，请等候数秒..."}), 503

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
            # 提取识别出的题目文本
            question_text = ai_res.get('question', '[图片搜题]')
            ai_answer = ai_res.get('answer', '未识别出答案')
            ai_reason = ai_res.get('reason', '无解析')
            ai_category = ai_res.get('category', '其他')

            # 入库 QuestionBank（去重+向量索引），与文本搜题一致
            qb_id = save_question_to_db(
                question=question_text,
                answer=ai_answer,
                reason=ai_reason,
                category=ai_category
            )
            # 入库 UserHistory
            save_to_history(question_text, ai_answer, ai_reason, '图片搜题', ai_category, user_id=uid)
            db.session.commit()

            # 查最新 history 记录获取 id 和 is_mistake
            last_rec = UserHistory.query.filter_by(user_id=uid, question=question_text) \
                .order_by(UserHistory.id.desc()).first()

            return {
                'id': last_rec.id if last_rec else None,
                'question': question_text,
                'answer': ai_answer,
                'reason': ai_reason,
                'category': ai_category,
                'source': '图片搜题',
                'is_mistake': last_rec.is_mistake if last_rec else False
            }
        except Exception as e:
            logging.error(f"❌ [图片搜题] 异常: {e}", exc_info=True)
            raise
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)

    task_id = task_mgr.submit(_solve_img, app=app, owner=str(uid))
    return jsonify({'success': True, 'task_id': task_id}), 202