#app/services/answer_engine.py
import json
import re
from collections import Counter
import numpy as np
from .nlp_service import nlp_engine
from .llm_service import call_llm
from app.extensions import db
from app.models import QuestionBank, UserHistory

"""
 智能搜题管道：实现 标准化 -> 精确检索 -> 向量检索 -> 数字校验 -> AI 兜底
 """
def extract_core_numbers(text):
    """
    智能提取题目中的核心数字指纹
    """
    if not text:return []
    clean_text = nlp_engine.clean_prefix(text)
        # 提取题目本身数字
    nums = re.findall(r'\d+(?:\.\d+)?', clean_text)
    # 转换为 float，避免 "1" 和 "1.0" 因为字符串不匹配而导致误拦截
    return sorted([float(n) for n in nums])

def _parse_options(raw_opts):
    """辅助函数：安全地解析选项 JSON 字符串"""
    if not raw_opts:
        return None
    try:
        return json.loads(raw_opts) if isinstance(raw_opts, str) else raw_opts
    except Exception:
        return raw_opts

def is_semantically_identical(str1, str2):
    """
    字符级完全匹配校验 (辅助双重保障)
    """
    if not str1 or not str2:
        return False
    # 移除空格和标点，只保留汉字、字母、数字
    s1 = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', str1)
    s2 = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', str2)

    # 字符频次对比 (时间复杂度 O(N) 优于 sorted 的 O(N log N))
    return Counter(s1) == Counter(s2)

def fast_db_lookup(question_text, std_query=None):
    """
   极速检索模块 (数据库层)
    策略：预处理标准化 -> 数据库 B-Tree 索引查找
    """
    # 1. 获取标准化文本，优先使用传入值避免重复计算
    if not std_query:
        std_query = nlp_engine.standardize_text(question_text)

    if not std_query:
        return None

    # print(f"⚡ [极速检索] 查询指纹: {std_query[:30]}...")

    # 2. 数据库精确查询
    match = QuestionBank.query.filter_by(std_q=std_query).first()

    if match:
        print(f"✅ [极速检索] 命中数据库! ID: {match.id}")

        parsed_opts = _parse_options(match.options)

        return {
            "source": "本地题库 (精确匹配)",
            "answer": match.answer,
            "reason": match.reason,
            "options": parsed_opts,
            "match_score": 1.0,  # 绝对置信度
            "match_type": "Database Exact"
        }

    return None

def solve_pipeline(question_text, options=None, user_id=None):
    print(f"🔎 正在处理题目: {question_text[:30]}...")
    # --- 第一步：标准化预处理  ---
    std_q = nlp_engine.standardize_text(question_text)
    #  阶段一：数据库极速精确匹配
    fast_result = fast_db_lookup(question_text, std_query=std_q)
    if fast_result:
        # 命中即终止，跳过后续所有向量计算和 AI 调用
        return fast_result
    #  阶段二：向量语义搜索
    print(f"🧹 标准化清洗: [{question_text}] -> [{std_q}]")
    # --- 第二步：尝试语义向量搜索 + 精确匹配 ---
    # threshold 调低，匹配会更准
    best_match, vector_score = nlp_engine.search_best_match(question_text, threshold=0.80)
    print(f"--- 搜索调试1 ---")
    if best_match:
        print(f"候选原始题目（未预处理）: {best_match['question']}")
        print(f"候选标准（预处理后）: {best_match.get('std_q', '无')}")
    print(f"----------------")

    if best_match:
        # 关键词二次校验 (Re-rank)
        final_score = nlp_engine.verify_match_quality(
            question_text,
            best_match['question'],
            vector_score
        )
        print(f"--- 搜索调试2 ---")
        print(f"向量原始分: {vector_score:.4f} -> 最终判定分: {final_score:.4f}")

        # 🛡最终门槛判定
        if final_score >= 0.80:
            user_nums = extract_core_numbers(question_text)
            match_nums = extract_core_numbers(best_match['question'])

            if user_nums != match_nums:
                print(f"⚠️ 拦截误报：数字不匹配，转由 AI 计算")
            else:
                # 只有数字匹配成功，才定义 match_type 并准备返回
                is_flip = is_semantically_identical(question_text, best_match['question'])
                if final_score >= 0.95 or is_flip:
                    match_type = "精确匹配"
                    final_score = 1.0
                else:
                    match_type = f"相似度 {round(final_score, 2)}"
                parsed_opts = _parse_options(best_match.get('options'))
                return {
                    "source": f"本地题库 ({match_type})",
                    "answer": best_match['answer'],
                    "reason": best_match['reason'],
                    "options": parsed_opts
                }
        else:
            print(f"📉 判定分不足 ({final_score:.4f} < 0.80)，放弃本地结果")
        # --- 第三步：AI 兜底解题 ---
    print("☁️ 正在调用 AI 实时解答...")
    try:
        ai_res = call_llm(question_text, options)
        ai_category = ai_res.get('category', '其他')
    except Exception as e:
        return {"answer": "出错", "reason": f"AI服务异常: {str(e)}", "source": "系统错误"}
    # --- 第四步：存入数据库与索引 ---
    
    ai_answer = ai_res.get('answer', '略')
    # 处理字典类型的答案
    if isinstance(ai_answer, dict):
        ai_answer = json.dumps(ai_answer, ensure_ascii=False)
        
    # 调用封装好的入库函数
    save_question_to_db(
        question=question_text, 
        answer=ai_answer, 
        reason=ai_res.get('reason', 'AI生成'), 
        options=options, 
        category=ai_category,
        std_q_text=std_q
    )
    
    # 存入历史记录 (这是 UserHistory, 区别于 QuestionBank)
    try:
        save_to_history(
            question_text,
            ai_answer,
            ai_res.get('reason'),
            f"AI {ai_res.get('type', '智能分析')}",
            ai_category,
            user_id=user_id
        )
        db.session.commit()
    except Exception as e:
        print(f"历史记录保存失败: {e}")
    return {
        "answer": ai_answer,  # 使用转化后的结果，保证接口返回类型一致
        "reason": ai_res.get('reason'),
        "category": ai_category,
        "source": f"AI {ai_res.get('type', '智能分析')}",
        "score": 0.85,
        "options": options
    }
def save_to_history(q, a, r, source, category='其他', user_id=None):
    """辅助函数：保存到用户历史表"""
    history = UserHistory(
        question=q,
        answer=a,
        reason=r,
        source=source,
        category=category,
        user_id=user_id
    )
    db.session.add(history)

def save_question_to_db(question, answer, reason, options=None, category='其他', std_q_text=None):
    """
    封装入库逻辑：去重检查 -> 生成向量 -> 存 SQL -> 更新显存索引
    供 solve_pipeline 和 formula_example_generation 共用
    """
    try:
        # 0. 计算标准化指纹并检查去重
        if not std_q_text:
            std_q_text = nlp_engine.standardize_text(question)
        existing = QuestionBank.query.filter_by(std_q=std_q_text).first()
        if existing:
            print(f"⚠️ [跳过入库] 题目已存在 ID: {existing.id} - {question[:20]}...")
            return existing.id
        
        # 1. 生成向量
        vector = nlp_engine.encode(question)
        
        # 处理字典类型的答案/选项
        if isinstance(answer, dict):
            answer = json.dumps(answer, ensure_ascii=False)
        opts_json = json.dumps(options, ensure_ascii=False) if options else None

        # 2. 存入 SQL 数据库
        new_q = QuestionBank(
            question=question,
            std_q=std_q_text,
            options=opts_json,
            answer=answer,
            reason=reason,
            category=category,
            embedding=json.dumps(vector.tolist() if isinstance(vector, np.ndarray) else vector) 
        )
        db.session.add(new_q)
        db.session.commit()
        
        # 3. 热更新显存索引
        nlp_engine.add_to_index(
            question=question,
            embedding=vector, 
            answer=answer, 
            reason=reason,
            options=options
        )
        print(f"💾 [入库成功] ID: {new_q.id} - {question[:20]}...")
        return new_q.id
    except Exception as e:
        db.session.rollback()
        print(f"❌ 入库失败: {e}")
        return None