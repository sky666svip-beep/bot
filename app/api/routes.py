import os
import uuid
import logging
import fitz
import json
import re
from flask import Blueprint, request, jsonify, render_template
from docx import Document
from sqlalchemy import func, or_
from app.models import UserHistory, QuestionBank, Poetry, PoetryAnalysis
from app.extensions import db
from app.services.answer_engine import solve_pipeline
from app.services.llm_service import solve_with_vision, extract_text_from_image, analyze_essay, generate_study_plan, generate_exam_questions, generate_poetry_analysis

api_bp = Blueprint('api', __name__)
main = Blueprint('main', __name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'instance', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------------------------------------------
# 1. 核心路由：语义搜索接口 (ML 矩阵架构)
# ----------------------------------------------------------------
@main.route('/search', methods=['POST'])
def search_question():
    user_query = request.json.get('query', '').strip()
    if not user_query:
        return jsonify({"success": False, "message": "请输入题目"})
    # Pipeline 内部已处理核心逻辑与入库
    result = solve_pipeline(user_query)
    
    # 获取刚刚存入的记录 ID
    last_rec = UserHistory.query.filter_by(question=user_query).order_by(UserHistory.id.desc()).first()

    return jsonify({
        "success": True,
        "data": {
            **result,
            "id": last_rec.id if last_rec else None,
            "is_mistake": last_rec.is_mistake if last_rec else False
        }
    })

@api_bp.route('/solve', methods=['POST'])
def solve():
    """传统 Pipeline 接口,solve_pipeline 通常内部集成了数据库检索 + AI 生成"""
    data = request.json
    return jsonify(solve_pipeline(data.get('question', ''), data.get('options', [])))

@api_bp.route('/solve-image', methods=['POST'])
def solve_image():
    """视觉路由：图片搜题 (Vision ML)"""
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': '无效图片文件'}), 400

    temp_path = os.path.join(UPLOAD_FOLDER, f"vision_{uuid.uuid4()}.jpg")
    file.save(temp_path)

    try:
        # 1. 调用视觉引擎识别
        ai_res = solve_with_vision(temp_path)
        
        # 2. 入库
        history = UserHistory(
            question="[图片搜题]",
            answer=ai_res.get('answer', '未识别出答案'),
            reason=ai_res.get('reason', '无解析'),
            source="图片搜题",
            category=ai_res.get('category', '其他')
        )
        db.session.add(history)
        db.session.commit()
        # 返回规范化的 JSON
        return jsonify({
            'id': history.id,
            'answer': history.answer,
            'reason': history.reason,
            'category': history.category,
            'source': '图片搜题'
        })
    finally:
        if os.path.exists(temp_path): os.remove(temp_path) # 删除临时图片

# 历史记录路由
@api_bp.route('/history', methods=['GET'])
def get_history():
    histories = UserHistory.query.order_by(UserHistory.created_at.desc()).limit(10).all()
    return jsonify([h.to_dict() for h in histories])

@api_bp.route('/history-data', methods=['GET'])
def get_history_data():
    filter_mistake = request.args.get('filter') == 'mistake'
    query = UserHistory.query
    if filter_mistake:
        query = query.filter_by(is_mistake=True)
    
    limit = 200 if filter_mistake else 50
    histories = query.order_by(UserHistory.created_at.desc()).limit(limit).all()
    return jsonify([h.to_dict() for h in histories])

@api_bp.route('/history/<int:hid>/toggle', methods=['POST'])
def toggle_history_status(hid):
     #切换历史记录的错题(mistake)状态,添加or删除错题
    record = UserHistory.query.get_or_404(hid)
    record.is_mistake = not record.is_mistake
    db.session.commit()
    return jsonify({"success": True, "new_status": record.is_mistake})

# 文档上传路由
@main.route('/upload-doc', methods=['POST'])
def upload_document():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({"success": False, "message": "无效文件"})

    temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4()}_{file.filename}")
    file.save(temp_path)
    
    try:
        ext = file.filename.lower().split('.')[-1]
        text = ""
        
        if ext == 'pdf':
            with fitz.open(temp_path) as doc:
                text = "".join([page.get_text() for page in doc])
        elif ext == 'docx':
            doc = Document(temp_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            for table in doc.tables:
                for row in table.rows:
                    text += "\n" + " ".join([cell.text for cell in row.cells])
        elif ext == 'txt':
            with open(temp_path, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            return jsonify({"success": False, "message": "不支持的格式"})

        if not text.strip():
            return jsonify({"success": False, "message": "文档内容为空"})
            
        return jsonify({"success": True, "full_text": text})
    except Exception as e:
        return jsonify({"success": False, "message": f"解析错误: {str(e)}"})
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    # 1. 热力图
    daily = db.session.query(func.date(UserHistory.created_at), func.count(UserHistory.id))\
        .group_by(func.date(UserHistory.created_at)).all()
    heatmap = [[str(d), c] for d, c in daily]
    
    # 2. 饼图SELECT category, COUNT(*) FROM user_history GROUP BY category
    cats = db.session.query(UserHistory.category, func.count(UserHistory.id))\
        .group_by(UserHistory.category).all()
    pie = [{"name": c, "value": n} for c, n in cats]
    
    return jsonify({"heatmap": heatmap, "pie": pie})

# === 作文批改API ===

@api_bp.route('/essay/correct', methods=['POST'])
def correct_essay_api():
    data = request.json or {}
    text = data.get('text', '')
    if len(text) < 5:
        return jsonify({"success": False, "message": "内容太短"})
    # 调用 llm_service 中的核心逻辑
    result = analyze_essay(text, data.get('type', 'chinese'))
    return jsonify({"success": True, "data": result})

# === 纯文字识别 API (供作文拍照批改使用) ===
@api_bp.route('/ocr-image', methods=['POST'])
def ocr_image_api():
    file = request.files.get('file')
    if not file: return jsonify({'success': False, 'message': '无文件'})
    
    temp_path = os.path.join(UPLOAD_FOLDER, f"ocr_{uuid.uuid4()}.jpg")
    file.save(temp_path)
    try:
        return jsonify({'success': True, 'text': extract_text_from_image(temp_path)})
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

# === 学习计划板块 ===

@api_bp.route('/study-plan/generate', methods=['POST'])
def generate_plan_api():
    data = request.json or {}
    if 'grade' not in data or 'duration' not in data:
        return jsonify({"success": False, "message": "缺少必要参数"})
    
    return jsonify({"success": True, "data": generate_study_plan(data)})

@api_bp.route('/study-plan/weakness-analysis', methods=['GET'])
def analyze_weakness_api():
    """智能分析错题本：统计最近50条错题，找出高频学科/标签"""
    mistakes = UserHistory.query.filter_by(is_mistake=True)\
        .order_by(UserHistory.created_at.desc()).limit(50).all()
        
    if not mistakes:
        return jsonify({"success": True, "weakness": "暂无错题数据"})
        
    # 简化统计逻辑
    counts = {}
    for m in mistakes:
        c = m.category or "其他"
        counts[c] = counts.get(c, 0) + 1
        
    top = sorted(counts, key=counts.get, reverse=True)[:3]
    return jsonify({"success": True, "weakness": f"建议重点突破：{', '.join(top)}"})

# === 模拟考试模块 ===
@api_bp.route('/simulation/generate', methods=['POST'])
def generate_simulation_api():
    """生成试题接口"""
    return jsonify({"success": True, "questions": generate_exam_questions(request.json)})

@api_bp.route('/simulation/submit', methods=['POST'])

def submit_simulation_api():
    """提交并保存考试结果"""
    data = request.json or {}
    results = data.get('results', [])
    saved_ids = []
    # 存入 UserHistory历史记录
    for item in results:
        history = UserHistory(
            question=item.get('question'),
            answer=item.get('answer'),
            reason=item.get('reason'),
            source='模拟考试',
            category=item.get('category', '其他'),
            is_mistake=False # 所以这里默认 is_mistake=False，由用户手动点收藏/错题
        )
        db.session.add(history)
        db.session.flush()
        saved_ids.append({"temp_id": item.get('temp_id'), "db_id": history.id})
        
    db.session.commit()
    return jsonify({"success": True, "saved_ids": saved_ids})

# === 古诗词鉴赏模块 ===

@api_bp.route('/poetry/search', methods=['POST'])
def search_poetry():
    keyword = request.json.get('keyword', '').strip()
    if not keyword:
        return jsonify({"success": False, "message": "关键词为空"})

    # 1. 查库 (Exact or Fuzzy模糊匹配 Title 或 Author)
    poetry = Poetry.query.filter(or_(Poetry.title == keyword, Poetry.author == keyword)).first()
    if not poetry:
        poetry = Poetry.query.filter(or_(Poetry.title.like(f"%{keyword}%"), Poetry.author.like(f"%{keyword}%"))).first()
    # 2. 如果库里有诗，检查是否有赏析
    if poetry:
        analysis = PoetryAnalysis.query.filter_by(poetry_id=poetry.id).first()
        if analysis:
            return jsonify({
                "success": True, 
                "source": "database",
                "data": {
                    "title": poetry.title,
                    "author": f"{poetry.dynasty or ''} {poetry.author}",
                    "content": poetry.content,
                    "translation": analysis.translation,
                    "appreciation": analysis.appreciation,
                    "annotations": analysis.to_dict()['annotations']
                }
            })

    # 2. LLM 生成
    gen = generate_poetry_analysis(keyword)
    if not gen or 'error' in gen:
        return jsonify({"success": False, "message": "未找到相关诗词"})

    # 3. 入库 (Trust Gen Data)
    if not poetry:
        # 简单提取朝代
        raw_auth = gen.get('author', '佚名')
        dynasty, author = "", raw_auth
        m = re.match(r'^\[(.*?)\]\s*(.*)', raw_auth)
        if m: dynasty, author = m.groups()
        
        poetry = Poetry(title=gen.get('title', keyword), author=author, dynasty=dynasty, content=gen.get('content', ''))
        db.session.add(poetry)
        db.session.flush()

    analysis = PoetryAnalysis(
        poetry_id=poetry.id,
        translation=gen.get('translation', ''),
        appreciation=gen.get('appreciation', ''),
        annotations=json.dumps(gen.get('annotations', []), ensure_ascii=False),
        title=poetry.title,
        author=poetry.author
    )
    db.session.add(analysis)
    db.session.commit()

    return jsonify({"success": True, "source": "llm", "data": gen})

# === 页面渲染路由 ===
@main.route('/view-history')
def view_history(): return render_template('history.html')
@main.route('/formulas')
def formulas(): return render_template('formulas.html')
@main.route('/calculator')
def calculator_page(): return render_template('calculator.html')
@main.route('/essay-correction')
def essay_correction_page(): return render_template('essay.html')
@main.route('/study_plan')
def study_plan_page(): return render_template('study_plan.html')
@main.route('/simulation-exam')
def simulation_exam_page(): return render_template('simulation_exam.html')
@main.route('/poetry')
def poetry_page(): return render_template('poetry.html')