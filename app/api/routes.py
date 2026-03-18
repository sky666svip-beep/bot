import os
import uuid
import logging
import fitz
import json
import re
from flask import Blueprint, request, jsonify
from docx import Document
from sqlalchemy import func, or_
from werkzeug.exceptions import HTTPException
from app.models import UserHistory, QuestionBank, Poetry, PoetryAnalysis, Formula, Vocabulary, Idiom
from app.extensions import db
from app.services.llm_service import extract_text_from_image, analyze_essay, generate_study_plan, generate_exam_questions, generate_poetry_analysis
from flask_login import login_required, current_user

api_bp = Blueprint('api', __name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'instance', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 安全配置：允许的文件后缀
ALLOWED_IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}
ALLOWED_DOC_EXTS = {'pdf', 'docx', 'txt'}

def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set

@api_bp.errorhandler(Exception)
def handle_global_error(e):
    """统一拦截 API 异常，防止对外抛出 500 HTML页面"""
    logging.error(f"API Error: {str(e)}", exc_info=True)
    code = e.code if isinstance(e, HTTPException) else 500
    return jsonify({"success": False, "message": "服务器内部错误" if code == 500 else str(e)}), code

# 历史记录路由
@api_bp.route('/history', methods=['GET'])
@login_required
def get_history():
    histories = UserHistory.query.filter_by(user_id=current_user.id)\
        .order_by(UserHistory.created_at.desc()).limit(10).all()
    return jsonify([h.to_dict() for h in histories])

@api_bp.route('/history-data', methods=['GET'])
@login_required
def get_history_data():
    filter_mistake = request.args.get('filter') == 'mistake'
    query = UserHistory.query.filter_by(user_id=current_user.id)
    if filter_mistake:
        query = query.filter_by(is_mistake=True)
    
    limit = 200 if filter_mistake else 50
    histories = query.order_by(UserHistory.created_at.desc()).limit(limit).all()
    return jsonify([h.to_dict() for h in histories])

@api_bp.route('/history/<int:hid>/toggle', methods=['POST'])
@login_required
def toggle_history_status(hid):
     #切换历史记录的错题(mistake)状态,添加or删除错题
    record = UserHistory.query.get_or_404(hid)
    
    # 权限校验：只能修改自己的记录
    if record.user_id != current_user.id:
        return jsonify({"success": False, "message": "无权操作"}), 403
        
    record.is_mistake = not record.is_mistake
    db.session.commit()
    return jsonify({"success": True, "new_status": record.is_mistake})

# 文档上传路由
@api_bp.route('/upload-doc', methods=['POST'])
def upload_document():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({"success": False, "message": "无效文件"})
    if not allowed_file(file.filename, ALLOWED_DOC_EXTS):
        return jsonify({"success": False, "message": "不支持的文件格式"}), 400

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
@login_required
def get_dashboard_data():
    # 1. 热力图
    daily = db.session.query(func.date(UserHistory.created_at), func.count(UserHistory.id))\
        .filter(UserHistory.user_id == current_user.id)\
        .group_by(func.date(UserHistory.created_at)).all()
    heatmap = [[str(d), c] for d, c in daily]
    
    # 2. 饼图SELECT category, COUNT(*) FROM user_history GROUP BY category
    cats = db.session.query(UserHistory.category, func.count(UserHistory.id))\
        .filter(UserHistory.user_id == current_user.id)\
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
    if not allowed_file(file.filename, ALLOWED_IMAGE_EXTS):
        return jsonify({'success': False, 'message': '不支持的图片格式'})
    
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
@login_required
def analyze_weakness_api():
    """智能分析错题本：统计最近50条错题，找出高频学科/标签"""
    mistakes = UserHistory.query.filter_by(is_mistake=True, user_id=current_user.id)\
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
@login_required
def submit_simulation_api():
    """提交并保存考试结果 (批量插入版)"""
    from app.services.nlp_service import nlp_engine
    
    data = request.json or {}
    results = data.get('results', [])
    if not results:
        return jsonify({"success": True, "saved_ids": []})
        
    saved_ids = []
    history_records = []
    new_questions = []
    
    # 1. 提取文本并批量进行 Embedding 编码，避免 N+1
    texts_to_encode = [nlp_engine.clean_prefix(item.get('question', '')) for item in results]
    std_texts = [nlp_engine.standardize_text(t) for t in texts_to_encode]
    
    if nlp_engine.model:
        embeddings = nlp_engine.model.encode(std_texts, batch_size=32, convert_to_numpy=True, normalize_embeddings=True)
    else:
        embeddings = [[] for _ in results]
        
    # 2. 组装对象
    for i, item in enumerate(results):
        # 历史记录
        history = UserHistory(
            question=item.get('question'), answer=item.get('answer'), reason=item.get('reason'),
            source='模拟考试', category=item.get('category', '其他'), is_mistake=False, user_id=current_user.id
        )
        history_records.append(history)
        
        # 题库记录
        opts = item.get('options')
        new_q = QuestionBank(
            question=texts_to_encode[i], std_q=std_texts[i], answer=item.get('answer'),
            reason=item.get('reason'), options=json.dumps(opts, ensure_ascii=False) if opts else None,
            category=item.get('category', '模拟考试'), embedding=json.dumps(embeddings[i].tolist()) if len(embeddings[i])>0 else None
        )
        new_questions.append(new_q)
        
    # 3. 批量提交入库
    db.session.add_all(history_records)
    db.session.flush() # 获得历史记录id
    for i, history in enumerate(history_records):
        saved_ids.append({"temp_id": results[i].get('temp_id'), "db_id": history.id})
        
    db.session.bulk_save_objects(new_questions)
    db.session.commit()
    
    # 4. 热更新显存矩阵，使新提交的题目立即可搜
    for q in new_questions:
        if q.embedding:
            nlp_engine.add_to_index(q.question, json.loads(q.embedding), q.answer, q.reason, q.options)

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
    if not isinstance(gen, dict) or 'error' in gen or not gen.get('title') or not gen.get('content'):
        return jsonify({"success": False, "message": "未找到相关诗词或解析失败"})

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

# === 公式大全模块 ===

@api_bp.route('/formulas', methods=['GET'])
def get_formulas():
    """获取公式列表（支持分页、筛选）"""
    # 筛选参数
    grade = request.args.get('grade', '')
    category = request.args.get('category', '')
    keyword = request.args.get('keyword', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Formula.query
    
    # 学段筛选
    if grade:
        query = query.filter(Formula.grade.like(f"%{grade}%"))
    # 学科筛选
    if category:
        query = query.filter(Formula.category == category)
    # 关键词搜索（名称模糊匹配）
    if keyword:
        query = query.filter(or_(
            Formula.name.like(f"%{keyword}%"),
            Formula.tags.like(f"%{keyword}%")
        ))
    
    # 分页
    pagination = query.order_by(Formula.id).paginate(page=page, per_page=per_page, error_out=False)
    
    # 获取所有学段和学科用于筛选器
    all_grades = db.session.query(Formula.grade).distinct().all()
    all_categories = db.session.query(Formula.category).distinct().all()
    
    return jsonify({
        "success": True,
        "data": [f.to_dict() for f in pagination.items],
        "total": pagination.total,
        "page": page,
        "pages": pagination.pages,
        "filters": {
            "grades": sorted(set(g[0] for g in all_grades if g[0])),
            "categories": sorted(set(c[0] for c in all_categories if c[0]))
        }
    })

@api_bp.route('/formulas/<int:id>', methods=['GET'])
def get_formula_detail(id):
    """获取单个公式详情"""
    formula = Formula.query.get(id)
    if not formula:
        return jsonify({"success": False, "message": "公式不存在"}), 404
    
    # 返回完整数据（包含 grade）
    data = formula.to_dict()
    data['grade'] = formula.grade
    return jsonify({"success": True, "data": data})

@api_bp.route('/formulas/search', methods=['POST'])
def search_formulas():
    """语义搜索公式"""
    from app.services.nlp_service import nlp_engine
    
    query_text = request.json.get('query', '').strip()
    category = request.json.get('category', '')
    grade = request.json.get('grade', '')

    if not query_text:
        return jsonify({"success": False, "message": "查询内容为空"})
        
    results = nlp_engine.search_formulas(query_text, category=category, grade=grade, top_k=5, threshold=0.5)
    
    if not results:
        return jsonify({"success": True, "data": [], "message": "无匹配公式"})
    
    return jsonify({"success": True, "data": results})

@api_bp.route('/formulas/explain', methods=['POST'])
def explain_formula():
    """公式智能助教：讲解 & 出题"""
    from app.services.llm_service import generate_formula_content
    from app.services.answer_engine import save_question_to_db
    
    data = request.json
    fid = data.get('id')
    mode = data.get('type', 'explain') # explain or example
    
    if not fid: 
        return jsonify({"success": False, "message": "Missing ID"})
        
    formula = Formula.query.get(fid)
    if not formula:
        return jsonify({"success": False, "message": "Formula not found"})
        
    # 构造上下文
    ctx = {
        "name": formula.name,
        "formula": formula.formula_text,
        "grade": formula.grade,
        "category": formula.category
    }
    
    # 调用 LLM
    result = generate_formula_content(ctx, mode)
    
    if mode == 'example':
        # 如果是生成例题，需要解析并入库
        # result 应该是一个 JSON dict
        if isinstance(result, dict):
            # 存入题库
            q_id = save_question_to_db(
                question=result.get('question'),
                answer=result.get('answer'),
                reason=result.get('reason'),
                options=result.get('options', []),
                category=formula.category
            )
            # 返回给前端展示，并附带题库ID（方便后续可能的跳转）
            return jsonify({"success": True, "data": result, "db_id": q_id})
        else:
            return jsonify({"success": False, "message": "生成格式错误"})
            
    else:
        # 讲解模式，直接返回 Markdown 文本
        return jsonify({"success": True, "data": result})

# === 单词消消乐 API ===
@api_bp.route('/words', methods=['GET'])
def get_random_words():
    """获取随机单词对"""
    try:
        count = request.args.get('count', 10, type=int)
        
        # 1. 查出最大 ID
        max_id = db.session.query(func.max(Vocabulary.id)).scalar()
        if not max_id:
            return jsonify({"success": True, "data": []})

        # 2. 生成随机 ID 列表
        import random
        random_ids = random.sample(range(1, max_id + 1), min(count, max_id))
        
        # 3. 使用 ID 列表精确查找
        words = Vocabulary.query.filter(Vocabulary.id.in_(random_ids)).all()
        
        # 如果查询结果数量不足，可以考虑补充一些数据，但这里简化处理

        return jsonify({
            "success": True,
            "data": [w.to_dict() for w in words]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@api_bp.route('/words/search', methods=['GET'])
def search_vocabulary():
    """模糊搜索单词字典"""
    try:
        keyword = request.args.get('keyword', '').strip()
        if not keyword:
            return jsonify({"success": True, "data": []})
        
        words = Vocabulary.query.filter(
            or_(
                Vocabulary.word.like(f"%{keyword}%"),
                Vocabulary.definition.like(f"%{keyword}%")
            )
        ).limit(20).all()
        
        return jsonify({
            "success": True,
            "data": [w.to_dict() for w in words]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# === 成语 PK API ===
@api_bp.route('/idioms/random', methods=['GET'])
def get_random_idioms():
    """获取随机成语"""
    try:
        count = request.args.get('count', 10, type=int)

        # 1. 查出最大 ID
        max_id = db.session.query(func.max(Idiom.id)).scalar()
        if not max_id:
            return jsonify({"success": True, "data": []})

        # 2. 生成随机 ID 列表
        import random
        random_ids = random.sample(range(1, max_id + 1), min(count, max_id))
        
        # 3. 使用 ID 列表精确查找
        idioms = Idiom.query.filter(Idiom.id.in_(random_ids)).all()
        
        return jsonify({
            "success": True,
            "data": [idiom.to_dict() for idiom in idioms]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@api_bp.route('/idioms/all', methods=['GET'])
def get_all_idioms():
    """获取成语列表（支持分页）"""
    try:
        offset = request.args.get('offset', 0, type=int)
        limit = request.args.get('limit', 50, type=int)
        idioms = Idiom.query.order_by(Idiom.id).offset(offset).limit(limit).all()
        
        return jsonify({
            "success": True,
            "data": [idiom.to_dict() for idiom in idioms]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@api_bp.route('/idioms/<int:id>', methods=['GET'])
def get_idiom_detail(id):
    """获取单个成语详情"""
    try:
        idiom = Idiom.query.get(id)
        if not idiom:
            return jsonify({"success": False, "message": "成语不存在"}), 404
            
        return jsonify({
            "success": True,
            "data": idiom.to_dict()
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@api_bp.route('/idioms/search', methods=['GET'])
def search_idioms():
    """搜索成语"""
    try:
        keyword = request.args.get('keyword', '').strip()
        if not keyword:
            return jsonify({"success": True, "data": []})
            
        # 移除关键词中的所有空格以便于拼音无缝搜索
        clean_keyword = keyword.replace(' ', '')
        
        idioms = Idiom.query.filter(
            or_(
                Idiom.word.like(f"%{keyword}%"),
                Idiom.abbreviation.like(f"{clean_keyword}%"),
                func.replace(Idiom.pinyin_r, ' ', '').like(f"{clean_keyword}%")
            )
        ).limit(20).all()
        
        return jsonify({
            "success": True,
            "data": [idiom.to_dict() for idiom in idioms]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@api_bp.route('/idioms/validate_chain', methods=['GET'])
def validate_idiom_chain():
    """
    验证成语接龙是否合法 (同音不同字)
    参数:
    - word: 用户输入的成语
    - target: 需要匹配的起始拼音 (上一个成语最后一个字的读音，无声调)
    """
    try:
        word = request.args.get('word', '').strip()
        target_pinyin = request.args.get('target', '').strip()
        
        if not word or not target_pinyin:
            return jsonify({"success": False, "message": "缺少必要的验证参数"}), 400
            
        # 1. 在词库中查找该成语
        idiom = Idiom.query.filter_by(word=word).first()
        if not idiom:
            return jsonify({
                "success": True, 
                "valid": False, 
                "reason": f"词库中未收录成语「{word}」"
            })
            
        # 2. 直接获取数据库中已有的首尾拼音字段
        first_pinyin = idiom.first
        last_pinyin = idiom.last
        
        if not first_pinyin or not last_pinyin:
            return jsonify({
                 "success": True,
                 "valid": False,
                 "reason": f"成语「{word}」拼音数据缺失，无法判定"
            })
        
        # 3. 比对目标拼音
        if first_pinyin.lower() == target_pinyin.lower():
            data = idiom.to_dict()
            data['last_pinyin'] = last_pinyin # 下拉提示
            
            return jsonify({
                "success": True,
                "valid": True,
                "data": data
            })
        else:
            return jsonify({
                "success": True,
                "valid": False,
                "reason": f"「{word}」读音为 {first_pinyin}，不满足以 {target_pinyin} 开头的条件"
            })
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})