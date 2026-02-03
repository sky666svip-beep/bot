import os
import json
import logging
from dashscope import MultiModalConversation
from openai import OpenAI

# 配置 API Key
DASHSCOPE_API_KEY = "sk-4d7affd10cd14f2897a79263310c5d9e"
# dashscope SDK 需要设置 api_key
import dashscope
dashscope.api_key = DASHSCOPE_API_KEY

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    timeout=60.0
)

def _call_qwen_json(prompt, system_role="你是一个严谨的助手，只输出 JSON。", model="qwen-plus"):
    """
    """
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
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logging.error(f"LLM Call Error: {e}")
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
    2. 请严格按以下 JSON 格式输出：
    {{
      "category": "数学",
      "type": "题目类型",
      "answer": "准确答案内容",
      "reason": "简略的解题思路和知识点分析"
    }}
    """
    return _call_qwen_json(prompt, system_role="解题专家")

def solve_with_vision(image_path):
    """视觉搜题：直接调用 VL 模型，移除复杂的正则兜底"""
    try:
        image_uri = f"file://{os.path.abspath(image_path)}"
        prompt = """
        你是一个全能解题助手。请识别图片中的题目，并直接给出答案和解析。
        【重要】请严格只输出标准 JSON 格式，不要输出 Markdown 标记。
        格式要求：
        {
          "answer": "最终答案",
          "reason": "简略的解题步骤和思路",
          "category": "从[数学, 物理, 化学, 英语, 语文, 历史, 地理, 生物, 计算机, 其他]中选择一个"
        }
        """
        messages = [{
            "role": "user",
            "content": [
                {"image": image_uri},
                {"text": prompt}
            ]
        }]
        
        resp = MultiModalConversation.call(model='qwen-vl-plus', messages=messages)
        if resp.status_code == 200 and resp.output.choices:
            content = resp.output.choices[0].message.content
            if isinstance(content, list):
                raw_text = "".join([item.get('text', '') for item in content])
            else:
                raw_text = str(content)
                
            clean_content = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_content)
        else:
            raise Exception(resp.message)
            
    except Exception as e:
        logging.error(f"Vision Error: {e}")
        return {"answer": "识别失败", "reason": str(e), "category": "其他"}

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
    try:
        image_uri = f"file://{os.path.abspath(image_path)}"
        resp = MultiModalConversation.call(
            model='qwen-vl-plus',
            messages=[{"role": "user", "content": [{"image": image_uri}, {"text": "OCR提取图片文字，保持段落，不要废话，直接输出文本。"}]}]
        )
        if resp.status_code == 200 and resp.output.choices:
            content = resp.output.choices[0].message.content
            if isinstance(content, list):
                raw_text = "".join([item.get('text', '') for item in content])
            else:
                raw_text = str(content)
            return raw_text.strip()
        return ""
    except Exception as e:
        logging.error(f"OCR Error: {e}")
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
    要求：深入探讨思想内涵、时代背景、艺术风格及文学史地位。
    
    输出 JSON：
    {{ 
        "title": "...", 
        "author": "...", 
        "content": "...", 
        "translation": "...", 
        "appreciation": "...", 
        "annotations": [ {{ "word": "...", "note": "..." }} ] 
    }}
    """
    return _call_qwen_json(prompt, system_role="古诗词鉴赏专家")