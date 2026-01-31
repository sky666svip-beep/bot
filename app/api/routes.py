#app/api/routes.py
import os
import uuid
import logging
import fitz
from flask import Blueprint, request, jsonify, render_template, current_app
from app.models import UserHistory, QuestionBank
from app.extensions import db
from app.services.answer_engine import solve_pipeline
from app.services.llm_service import solve_with_vision, extract_text_from_image, analyze_essay, generate_study_plan
from docx import Document
from sqlalchemy import func

# 定义两个蓝图
api_bp = Blueprint('api', __name__)
main = Blueprint('main', __name__)

# 定义上传文件夹路径
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'instance', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ----------------------------------------------------------------
# 1. 核心路由：语义搜索接口 (ML 矩阵架构)
# ----------------------------------------------------------------
@main.route('/search', methods=['POST'])
def search_question():
    data = request.get_json()
    user_query = data.get('query', '')
    if not user_query:
        return jsonify({"success": False, "message": "请输入题目"})

    try:
        # 1. 执行 pipeline
        # 注意：solve_pipeline 内部已经调用了 save_to_history 存入数据库
        result = solve_pipeline(user_query)

        # 2. 获取刚才存入的那条记录的 ID（为了让前端能收藏）
        # 我们按时间倒序查出最新的一条记录
        last_rec = UserHistory.query.filter_by(question=user_query).order_by(UserHistory.id.desc()).first()

        return jsonify({
            "success": True,
            "data": {
                "id": last_rec.id if last_rec else None,
                "question": user_query,
                "answer": result.get('answer'),
                "reason": result.get('reason'),
                "category": result.get('category'),
                "source": result.get('source'),
                "is_mistake": last_rec.is_mistake if last_rec else False,
                "score": result.get('score', 0.95)
            }
        })
    except Exception as e:
        logging.error(f"搜索过程出错: {e}")
        return jsonify({"success": False, "message": f"搜索失败: {str(e)}"})

# ----------------------------------------------------------------
# 2. 传统逻辑路由：基于 pipeline 的解答
# ----------------------------------------------------------------
@api_bp.route('/solve', methods=['POST'])
def solve():
    data = request.json
    question = data.get('question', '')
    options = data.get('options', [])

    # solve_pipeline 通常内部集成了 数据库检索 + AI 生成
    result = solve_pipeline(question, options)
    return jsonify(result)
# ----------------------------------------------------------------
# 3. 视觉路由：拍照搜题 (Vision ML)
# ----------------------------------------------------------------
@api_bp.route('/solve-image', methods=['POST'])
def solve_image():
    if 'file' not in request.files:
        return jsonify({'error': '未找到图片文件'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': '文件名为空'}), 400
    temp_filename = f"vision_{uuid.uuid4()}.jpg"
    temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
    try:
        file.save(temp_path)
        # 1. 调用视觉引擎
        ai_res = solve_with_vision(temp_path)
        # 2. 健壮性处理：确保 ai_res 是字典
        if not isinstance(ai_res, dict):
            # 如果 AI 返回了纯字符串，手动构造字典
            ai_res = {
                "answer": str(ai_res),
                "reason": "AI 未按格式返回解析",
                "category": "其他"
            }
        # 3. 存储至数据库
        history = UserHistory(
            question="[图片搜题]",
            answer=ai_res.get('answer', '未识别出答案'),
            reason=ai_res.get('reason', '未识别出解析'),
            source="图片搜题",
            category=ai_res.get('category', '其他')
        )
        db.session.add(history)
        db.session.commit()
        # 4. 删除临时图片
        if os.path.exists(temp_path):
            os.remove(temp_path)
        # 5. 返回规范化的 JSON
        return jsonify({
            'id': history.id,
            'answer': history.answer,
            'reason': history.reason,
            'category': history.category,
            'source': '图片搜题'
        })
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        logging.error(f"视觉解析链路异常: {str(e)}")
        return jsonify({'error': f"识别失败: {str(e)}"}), 500
# ----------------------------------------------------------------
# 4. 历史记录路由
# ----------------------------------------------------------------
@api_bp.route('/history', methods=['GET'])
def get_history():
    histories = UserHistory.query.order_by(UserHistory.created_at.desc()).limit(10).all()
    return jsonify([h.to_dict() for h in histories])


@api_bp.route('/view-history')
def view_history():
    return render_template('history.html')


@api_bp.route('/history-data', methods=['GET'])
def get_history_data():
    filter_mistake = request.args.get('filter') == 'mistake'
    query = UserHistory.query
    
    if filter_mistake:
        query = query.filter_by(is_mistake=True)
        
    # 如果是查错题，应该给多一点，或者查全部
    limit = 200 if filter_mistake else 50
    histories = query.order_by(UserHistory.created_at.desc()).limit(limit).all()
    return jsonify([h.to_dict() for h in histories])

#文档处理
@main.route('/upload-doc', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "无文件上传"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "未选择文件"})

    filename = file.filename.lower()
    temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4()}_{file.filename}")
    file.save(temp_path)

    extracted_text = ""
    try:
        # --- 情况 A: 处理 PDF ---
        if filename.endswith('.pdf'):
            with fitz.open(temp_path) as doc:
                for page in doc:
                    extracted_text += page.get_text()

        # --- 情况 B: 处理 DOCX
        elif filename.endswith('.docx'):
            doc = Document(temp_path)
            # 提取所有段落的文本
            full_para_text = [para.text for para in doc.paragraphs]
            # 也可以提取表格中的文本
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        full_para_text.append(cell.text)
            extracted_text = "\n".join(full_para_text)
        # --- 情况 C: 处理纯文本 TXT ---
        elif filename.endswith('.txt'):
            with open(temp_path, 'r', encoding='utf-8') as f:
                extracted_text = f.read()
        else:
            os.remove(temp_path)
            return jsonify({"success": False, "message": "暂不支持该文件格式，请上传 PDF、DOCX 或 TXT"})
        os.remove(temp_path)
        if not extracted_text.strip():
            return jsonify({"success": False, "message": "未能从文档中提取到文字内容"})
        return jsonify({
            "success": True,
            "full_text": extracted_text
        })
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        return jsonify({"success": False, "message": f"解析出错: {str(e)}"})

@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    try:
        # 1. 热力图数据
        daily_stats = db.session.query(
            func.date(UserHistory.created_at).label('date'),
            func.count(UserHistory.id).label('count')
        ).group_by(func.date(UserHistory.created_at)).all()
        heatmap_data = [[str(day), count] for day, count in daily_stats]
        # 2. 饼图数据
        # SELECT category, COUNT(*) FROM user_history GROUP BY category
        cat_stats = db.session.query(
            UserHistory.category,
            func.count(UserHistory.id)
        ).group_by(UserHistory.category).all()
        # 转换为 ECharts 格式
        pie_data = [{"name": cat, "value": count} for cat, count in cat_stats]
        return jsonify({
            "heatmap": heatmap_data,
            "pie": pie_data
        })

    except Exception as e:
        logging.error(f"仪表盘数据错误: {e}")
        return jsonify({"heatmap": [], "pie": []})

@api_bp.route('/history/<int:hid>/toggle', methods=['POST'])
def toggle_history_status(hid):
    #切换历史记录的错题(mistake)状态
    data = request.get_json()
    target_type = data.get('type', 'mistake')
    record = UserHistory.query.get_or_404(hid)
    new_status = False
    if target_type == 'mistake' or target_type == 'favorite':
        record.is_mistake = not record.is_mistake
        new_status = record.is_mistake
    else:
        return jsonify({"success": False, "message": "无效的操作类型"}), 400
    db.session.commit()
    return jsonify({
        "success": True,
        "new_status": new_status,
        "type": "mistake"
    })
@main.route('/formulas')
def formulas():
    return render_template('formulas.html')

@main.route('/calculator')
def calculator_page():
    return render_template('calculator.html')
# === 作文批改 API ===
@main.route('/essay-correction')
def essay_correction_page():
    return render_template('essay.html')
@api_bp.route('/essay/correct', methods=['POST'])
def correct_essay_api():
    data = request.json
    text = data.get('text', '')
    essay_type = data.get('type', 'chinese')  # 'chinese' or 'english'
    if not text or len(text) < 5:
        return jsonify({"success": False, "message": "作文内容太短，请重新输入"})
    # 调用 llm_service 中的核心逻辑
    result = analyze_essay(text, essay_type)
    return jsonify({"success": True, "data": result})
# === 纯文字识别 API (供作文拍照使用) ===
@api_bp.route('/ocr-image', methods=['POST'])
def ocr_image_api():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '无文件'})
    file = request.files['file']
    # 复用现有的上传路径配置
    temp_filename = f"ocr_{uuid.uuid4()}.jpg"
    temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
    try:
        file.save(temp_path)
        extracted_text = extract_text_from_image(temp_path)
        return jsonify({'success': True, 'text': extracted_text})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
# === 作文批改 API ===
# app/api/routes.py (追加以下路由)

# === 学习计划页面 ===
@main.route('/study_plan')
def study_plan_page():
    return render_template('study_plan.html')


@api_bp.route('/study-plan/generate', methods=['POST'])
def generate_plan_api():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "无数据"})

    # 简单的参数校验
    required = ['grade', 'duration']
    for field in required:
        if field not in data:
            return jsonify({"success": False, "message": f"缺少必填项: {field}"})

    result = generate_study_plan(data)
    return jsonify({"success": True, "data": result})


# app/api/routes.py (追加以下内容)

@api_bp.route('/study-plan/weakness-analysis', methods=['GET'])
def analyze_weakness_api():
    """
    智能分析错题本：统计最近50条错题，找出高频学科/标签
    """
    try:
        # 查询最近 50 条错题
        mistakes = UserHistory.query.filter_by(is_mistake=True) \
            .order_by(UserHistory.created_at.desc()).limit(50).all()

        if not mistakes:
            return jsonify({"success": False, "message": "错题本空空如也，暂无法分析哦~"})

        # 简单的统计逻辑：统计 category (学科) 出现次数
        cat_counts = {}
        for m in mistakes:
            cat = m.category or "其他"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        # 排序取前 3
        sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        top_cats = [cat for cat, count in sorted_cats]

        # 构造智能描述
        weakness_desc = f"根据错题数据，您在【{', '.join(top_cats)}】学科上遇到困难较多，建议重点突破。"

        return jsonify({"success": True, "weakness": weakness_desc})
    except Exception as e:
        return jsonify({"success": False, "message": f"分析失败: {str(e)}"})


# === 模拟考试模块 ===
@main.route('/simulation-exam')
def simulation_exam_page():
    return render_template('simulation_exam.html')

@api_bp.route('/simulation/generate', methods=['POST'])
def generate_simulation_api():
    """生成试题接口"""
    data = request.json
    # data: { subject, grade, keypoint, types[], count }
    
    if not data:
        return jsonify({"success": False, "message": "通过参数为空"})

    try:
        from app.services.llm_service import generate_exam_questions
        questions = generate_exam_questions(data)
        return jsonify({"success": True, "questions": questions})
    except Exception as e:
        return jsonify({"success": False, "message": f"生成失败: {str(e)}"})

@api_bp.route('/simulation/submit', methods=['POST'])
def submit_simulation_api():
    """提交并保存考试结果"""
    data = request.json
    # data: { results: [ {question, answer, reason, my_answer, is_correct, category} ] }
    
    if not data or 'results' not in data:
        return jsonify({"success": False, "message": "无提交数据"})
    
    saved_ids = []
    try:
        user_results = data['results']
        for item in user_results:
            # 存入 UserHistory
            # source 标记为 '模拟考试'
            history = UserHistory(
                question=item.get('question'),
                answer=item.get('answer'),
                reason=item.get('reason'),
                source='模拟考试',
                category=item.get('category', '其他'),
                is_mistake=not item.get('is_correct', True) # 如果答错了，是否自动加入错题本？
                # 需求描述说“手动标记作答错误的题目”... “自动将本次测试的所有题目...存入UserHistory”
                # “支持用户手动将错题一键添加至错题本”
                # 所以这里默认 is_mistake=False，由用户手动点收藏/错题
            )
            # 修正：需求说“用户需要手动标记作答错误的题目”，但又说“自动将本次测试...存入”，
            # 一般逻辑是存入所有记录。至于是否是错题，通过 toggle 接口控制。
            # 这里我们先把 is_mistake 设为 False，让用户自己点星星比较保险，也符合 "手动" 的描述。
            # 并在前端提供 "一键全部加入错题" 或者单个加入。
            # 实际上，如果已经提交，前端展示结果时，每个题目卡片上应该有个 "加入错题本" 按钮。
            
            history.is_mistake = False 
            
            db.session.add(history)
            db.session.flush() # 获取 ID
            saved_ids.append({
                "temp_id": item.get('temp_id'), # 前端传来的临时ID，方便对应
                "db_id": history.id
            })
            
        db.session.commit()
        return jsonify({"success": True, "saved_ids": saved_ids})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"})