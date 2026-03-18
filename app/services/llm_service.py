import os
import json
import logging
import re
import time
from dashscope import MultiModalConversation
from openai import OpenAI

# 配置 API Key
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
# dashscope SDK 需要设置 api_key
import dashscope
dashscope.api_key = DASHSCOPE_API_KEY

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    timeout=60.0
)

def _extract_json_string(text):
    """
    强制从大模型输出的文本中提取合法的 JSON 字符串，
    处理可能携带的 Markdown 代码块或前后废话。
    """
    text = text.strip()
    # 尝试匹配最外层的花括号或方括号
    start_obj = text.find('{')
    end_obj = text.rfind('}')
    start_arr = text.find('[')
    end_arr = text.rfind(']')
    
    len_obj = end_obj - start_obj if start_obj != -1 and end_obj != -1 else -1
    len_arr = end_arr - start_arr if start_arr != -1 and end_arr != -1 else -1
    
    if len_obj > 0 and len_obj > len_arr:
        return text[start_obj:end_obj+1]
    elif len_arr > 0:
        return text[start_arr:end_arr+1]
        
    return text # 如果都没找到，返回原样交给 json.loads 去报错

def _call_qwen_json(prompt, system_role="你是一个严谨的助手，只输出 JSON。", model="qwen3.5-flash", max_retries=2):
    """
    通用大模型 JSON 调用接口，附带指数退避重试和 JSON 净化
    """
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_role},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            raw_content = response.choices[0].message.content
            clean_content = _extract_json_string(raw_content)
            return json.loads(clean_content)
        except Exception as e:
            logging.warning(f"LLM Call Error (Attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt) # 1s, 2s 避让
            else:
                logging.error(f"LLM Call Failed after {max_retries + 1} attempts.")
                return {} 

def call_llm(question, options=None, is_doc=False):
    """文本搜题"""
    categories = ["数学", "计算机", "物理", "化学", "地理", "历史", "语文", "英语","生物", "其他"]
    options_str = f"选项：{options}" if options else "（无选项，这是一道非选择题）"
    doc_context = "注意：以下内容提取自PDF/文档，可能包含乱码、页码或格式错位，请先理顺题目逻辑再回答。" if is_doc else ""
    
    prompt = f"""
    你是一个全能解题专家。{doc_context}请分析并回答以下题目。
    题目内容：{question}
    {options_str}
    
    要求：
    1. "category" 字段必须从以下列表中选一个最贴切的：{categories}
    2. 不要输出 Markdown 标记和除答案和解析以外的内容，请严格按以下 JSON 格式输出：
    {{
      "category": "数学",
      "type": "题目类型",
      "answer": "准确答案内容",
      "reason": "简短的解题步骤和思路"
    }}
    """
    return _call_qwen_json(prompt, system_role="解题专家")

def solve_with_vision(image_path):
    """视觉搜题：支持重试与JSON净化"""
    max_retries = 2
    image_uri = f"file://{os.path.abspath(image_path)}"
    prompt = """
    你是一个全能解题专家。请识别图片中的题目，并直接给出答案和解析。
    【重要】请严格只输出标准 JSON 格式，不要输出 Markdown 标记和除答案和解析以外的内容。
    格式要求：
    {
      "answer": "最终答案",
      "reason": "简短的解题步骤和思路",
      "category": "从[数学, 物理, 化学, 英语, 语文, 历史, 地理, 生物, 计算机, 其他]中选择一个"
    }
    """
    messages = [{
        "role": "user",
        "content": [{"image": image_uri}, {"text": prompt}]
    }]
    
    for attempt in range(max_retries + 1):
        try:
            resp = MultiModalConversation.call(model='qwen3-vl-flash', messages=messages)
            if resp.status_code == 200 and resp.output.choices:
                content = resp.output.choices[0].message.content
                raw_text = "".join([item.get('text', '') for item in content]) if isinstance(content, list) else str(content)
                clean_content = _extract_json_string(raw_text)
                return json.loads(clean_content)
            else:
                raise Exception(resp.message)
        except Exception as e:
            logging.warning(f"Vision Error (Attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries: time.sleep(1)
    
    return {"answer": "识别失败", "reason": "图片解析服务暂不可用，请稍后重试", "category": "其他"}

def analyze_essay(text, essay_type):
    """作文批改"""
    if essay_type == 'chinese':
        role = "资深语文老师"
        prompt = f"""
        请批改以下作文。要求输出为严格的 JSON 格式。
        包含字段：
        1. "score": 评分（优秀/良好/中等/及格/不及格）
        2. "summary": 总评
        3. "highlights": 亮点数组
        4. "suggestions": 建议数组

        作文内容：{text}
        """
    else:
        role = "Strict English Teacher"
        prompt = f"""
        Correct the essay. Return strictly in JSON format.
        Fields:
        1. "score": Grade (A/B/C/D/F)
        2. "corrections": Array of {{error, fix, explanation}}
        3. "enhancements": Array of {{original, improved}}
        4. "comment": Overall comment

        Essay Content:{text}
        """
    return _call_qwen_json(prompt, system_role=role)

def extract_text_from_image(image_path):
    """OCR 纯文本提取"""
    max_retries = 2
    image_uri = f"file://{os.path.abspath(image_path)}"
    
    for attempt in range(max_retries + 1):
        try:
            resp = MultiModalConversation.call(
                model='qwen3-vl-flash',
                messages=[{"role": "user", "content": [{"image": image_uri}, {"text": "OCR提取图片文字，保持段落，不要废话，直接输出文本。"}]}]
            )
            if resp.status_code == 200 and resp.output.choices:
                content = resp.output.choices[0].message.content
                if isinstance(content, list):
                    return "".join([item.get('text', '') for item in content]).strip()
                return str(content).strip()
            raise Exception(resp.message)
        except Exception as e:
            logging.warning(f"OCR Error (Attempt {attempt + 1}/{max_retries + 1}): {e}")
            if attempt < max_retries: time.sleep(1)
            
    return ""

def generate_study_plan(profile_data):
    """学习计划"""
    start_time = profile_data.get('startTime', '09:00')
    prompt = f"""
    请根据以下学生信息，制定一份详细的今日学习计划。
    画像：年级{profile_data.get('grade')}, 弱项{profile_data.get('weakness')}, 目标{profile_data.get('goal')}, 时长{profile_data.get('duration')}小时, 开始时间{start_time}
    
    要求：
    1. 时间从{start_time}开始推算。
    2. 严格输出 JSON：
    {{
        "analysis": "简短建议",
        "tasks": [
            {{ "time_range": "...", "subject": "...", "task": "...", "type": "刷题/复习/复盘", "priority": "High/Medium", "duration": 30, "method": "..." }}
        ]
    }}
    """
    return _call_qwen_json(prompt, system_role="学习规划师")

def generate_exam_questions(criteria):
    """自动出题"""
    prompt = f"""
    请根据要求生成微型测验题。
    要求：{criteria.get('grade')}{criteria.get('subject')}, 考点{criteria.get('keypoint')}, {criteria.get('count')}道
    题型：{', '.join(criteria.get('types', ['单选题']))}
    
    输出 JSON：
    {{
        "questions": [
            {{
                "type": "单选题", 
                "question": "...", 
                "options": ["A. x", "B. x"], 
                "answer": "...", 
                "reason": "..." 
            }}
        ]
    }}
    """
    result = _call_qwen_json(prompt, system_role="出题专家")
    return result.get('questions', [])

def generate_poetry_analysis(keyword):
    """古诗深度赏析"""
    prompt = f"""
    请生成深度古诗词赏析。
    关键词：{keyword}
    要求：深入探讨思想内涵、意象意境、语言风格及表达技巧。
    
    【重要】请严格只输出标准 JSON 格式，不要输出 Markdown 标记或任何其他解释性文字。"content"字段必须是完整的文章内容，不是选段。必须包含以下完整的结构：
    {{ 
        "title": "...", 
        "author": "...", 
        "content": "...", 
        "translation": "...", 
        "appreciation": "...", 
        "annotations": [ {{ "word": "...", "note": "..." }} ] 
    }}
    """
    # 古诗深度赏析需要较强的长文本推理和结构化输出能力，轻量级模型容易出现截断或字段丢失，这里显式指定使用 qwen-plus
    result = _call_qwen_json(prompt, system_role="古诗词鉴赏专家", model="qwen3.5-plus")
    if not isinstance(result, dict) or not result.get('title') or not result.get('content'):
        return {}
    return result

def generate_formula_content(formula_context, type="explain"):
    """
    公式智能辅助：答疑或出题
    formula_context: { name, formula, grade, ... }
    type: 'explain' | 'example'
    """
    if type == 'explain':
        prompt = f"""
        请用为学生讲解以下公式。
        公式名称：{formula_context.get('name')}
        公式内容：{formula_context.get('formula')}
        
        要求：
        1. 简短解释公式的核心含义和物理/几何意义。
        2. 举一个简短实例简单类比。
        3. 输出 Markdown 格式。
        
        请直接输出 Markdown 内容，不要包含 JSON 格式。
        """
        json_prompt = prompt + "\n\n请输出 JSON: { \"content\": \"markdown string...\" }"
        res = _call_qwen_json(json_prompt, system_role="金牌理科辅导员")
        return res.get('content', '解析生成失败')
        
    elif type == 'example':
        prompt = f"""
        请根据以下公式生成一道经典的 {formula_context.get('grade')} 难度例题。
        公式名称：{formula_context.get('name')}
        公式内容：{formula_context.get('formula')}
        
        要求：
        1. 题目要典型，考察公式的核心用法，不要出选择题。
        2. 必须包含简短的解析步骤。
        3. 输出 JSON 格式用于入库。
        
        输出 JSON 结构：
        {{
            "question": "题目题干...",
            "options": ["A. ...", "B. ...", "C. ...", "D. ..."] (如果是选择题，否则留空数组),
            "answer": "正确答案",
            "reason": "简短解析步骤...",
            "category": "{formula_context.get('category', '数学')}"
        }}
        """
        return _call_qwen_json(prompt, system_role="资深出题老师")