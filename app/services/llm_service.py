import re
import os
import json
import dashscope
import logging
from dashscope import MultiModalConversation
from openai import OpenAI
# 配置 API Key
DASHSCOPE_API_KEY = "sk-4d7affd10cd14f2897a79263310c5d9e"#sk-4d7affd10cd14f2897a79263310c5d9e
dashscope.api_key = DASHSCOPE_API_KEY

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    timeout=60.0
)
def call_llm(question, options=None, is_doc=False):
    """文本搜题逻辑"""
    categories = ["数学", "计算机", "物理", "化学", "地理", "历史", "语文", "英语","生物", "其他"]
    options_str = f"选项：{options}" if options else "（无选项，这是一道非选择题）"

    doc_context = "注意：以下内容提取自PDF/文档，可能包含乱码、页码或格式错位，请先理顺题目逻辑再回答。" if is_doc else ""
    prompt = f"""你是一个全能解题专家。{doc_context}请分析并回答以下题目。
题目内容：{question}
{options_str}
要求：
1. "category" 字段必须从以下列表中选一个最贴切的：{categories}
请严格按以下 JSON 格式输出：
{{
  "category": "数学",
  "type": "题目类型",
  "answer": "准确答案内容",
  "reason": "简略的解题思路和知识点分析"
}}"""
    try:
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": "你是一个严谨的答题专家，只输出 JSON 格式。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        # 清洗 Markdown 标记
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "")
        elif content.startswith("```"):
            content = content.replace("```", "")
        content = content.strip()
        return json.loads(content)
    except json.JSONDecodeError:
        print(f"❌ JSON 解析失败，原始返回: {response.choices[0].message.content}")
        return {"answer": "AI解析失败", "reason": "模型返回格式异常", "category": "其他"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"answer": "未知", "reason": f"AI 调用错误: {str(e)}"}

def solve_with_vision(image_path):
    """
    视觉引擎：发送图片给大模型，并强制解析 JSON
    """
    try:
        # 获取绝对路径
        abs_path = os.path.abspath(image_path)
        image_uri = f"file://{abs_path}"
        vision_prompt = """
        你是一个全能解题助手。请识别图片中的题目，并直接给出答案和解析。
        【重要】请严格只输出标准 JSON 格式，不要输出 Markdown 标记（如 ```json ... ```），也不要输出任何开场白。
        格式要求：
        {
          "answer": "这里写最终答案",
          "reason": "这里写解题步骤和思路",
          "category": "从[数学, 物理, 化学, 英语, 语文, 历史, 地理, 生物, 计算机, 其他]中选择一个"
        }
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"image": image_uri},
                    {"text": vision_prompt}
                ]
            }
        ]
        # 调用阿里 Qwen-VL 模型
        response = MultiModalConversation.call(
            model='qwen-vl-max',
            messages=messages
        )
        if response.status_code == 200:
            # 提取文本内容
            raw_content = ""
            if hasattr(response, 'output') and response.output.choices:
                content_data = response.output.choices[0].message.content
                if isinstance(content_data, list):
                    for item in content_data:
                        if 'text' in item:
                            raw_content += item['text']
                else:
                    raw_content = str(content_data)

            logging.info(f"模型原始返回: {raw_content}")
            # === JSON 清洗与解析逻辑 ===
            try:
                # 1. 尝试直接解析
                return json.loads(raw_content)
            except json.JSONDecodeError:
                # 2. 如果失败，尝试用正则提取 { ... } 之间的内容
                match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                if match:
                    clean_json = match.group()
                    return json.loads(clean_json)
                else:
                    # 3. 彻底解析失败，手动构造返回
                    return {
                        "answer": raw_content,
                        "reason": "模型返回格式非标准JSON，已直接显示原文。",
                        "category": "其他"
                    }
        else:
            raise Exception(f"Dashscope API Error: {response.message}")
    except Exception as e:
        logging.error(f"视觉识别失败: {str(e)}")
        return {
            "answer": "识别失败",
            "reason": f"系统错误: {str(e)}",
            "category": "其他"
        }
def analyze_essay(text, essay_type):
    """
    作文批改核心逻辑
    :param text: 作文文本
    :param essay_type: 'chinese' 或 'english'
    :return: 结构化的字典数据
    """
    if essay_type == 'chinese':
        prompt = f"""
        你是一位资深语文老师。请批改以下作文。
        要求输出为严格的 JSON 格式，不要包含 Markdown 代码块标记（如 ```json），直接返回 JSON 字符串。
        包含以下字段：
        1. "score": 评分（仅限：优秀、良好、中等、及格、不及格）
        2. "summary": 总评（100字左右，概括整体质量）
        3. "highlights": 亮点（数组，列出3个具体的优点，如修辞、立意、结构）
        4. "suggestions": 改进建议（数组，列出3个具体的修改方向）

        作文内容：
        {text}
        """
    else:  # english
        prompt = f"""
        You are a strict English teacher. Correct the following essay.
        Return strictly in JSON format, no Markdown code blocks.
        Fields required:
        1. "score": Grade (A, B, C, D, F)
        2. "corrections": Array of objects. Each object has "error" (original wrong text), "fix" (correct text), "explanation" (grammar/vocab rule).
        3. "enhancements": Array of objects. Each object has "original" (original sentence), "improved" (advanced expression).
        4. "comment": A short overall comment.

        Essay Content:
        {text}
        """
    try:
        # 使用你文件顶部定义的 client 直接调用
        completion = client.chat.completions.create(
            model="qwen-plus",
            messages=[{'role': 'user', 'content': prompt}]
        )
        response_text = completion.choices[0].message.content
        # 清洗Markdown 标记
        cleaned_text = response_text.strip().replace('```json', '').replace('```', '')
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"作文批改出错: {e}")
        return {
            "score": "评分失败",
            "summary": "AI 接口调用异常，请重试。",
            "highlights": [],
            "suggestions": [str(e)],
            "corrections": [],
            "enhancements": [],
            "comment": "AI processing failed."
        }
def extract_text_from_image(image_path):
    """
    OCR 识别：只提取文字，不解题，不总结
    """
    try:
        abs_path = os.path.abspath(image_path)
        image_uri = f"file://{abs_path}"
        ocr_prompt = """
        请严格按照图片内容，将所有文字完整提取出来。
        1. 保持原文的段落结构。
        2. 严禁进行总结、摘要、分析或评论。
        3. 不要包含任何 JSON 格式标记，直接输出纯文本内容。
        4. 如果图片包含手写体，请尽最大努力识别。
        """

        messages = [
            {
                "role": "user",
                "content": [
                    {"image": image_uri},
                    {"text": ocr_prompt}
                ]
            }
        ]

        # 调用视觉模型
        response = MultiModalConversation.call(
            model='qwen-vl-max',
            messages=messages
        )
        if response.status_code == 200:
            # 提取文本内容
            raw_content = ""
            if hasattr(response, 'output') and response.output.choices:
                content_data = response.output.choices[0].message.content
                if isinstance(content_data, list):
                    for item in content_data:
                        if 'text' in item:
                            raw_content += item['text']
                else:
                    raw_content = str(content_data)
            return raw_content.strip()
        else:
            raise Exception(f"Dashscope API Error: {response.message}")

    except Exception as e:
        logging.error(f"OCR 提取失败: {str(e)}")
        return f"图片文字识别失败: {str(e)}"


# app/services/llm_service.py

def generate_study_plan(profile_data):
    """
    根据用户画像生成个性化学习计划
    :param profile_data: 字典，包含 grade, subjects, weakness, duration, goal, startTime
    """
    try:
        # 获取用户设定的开始时间，默认为 09:00
        start_time = profile_data.get('startTime', '09:00')

        prompt = f"""
        你是一位资深的中小学学习规划师。请根据以下学生信息，制定一份详细的今日学习计划。

        【学生画像】
        - 年级：{profile_data.get('grade', '未知')}
        - 目标学科：{profile_data.get('subjects', '全科')}
        - 薄弱点：{profile_data.get('weakness', '无')}
        - 可用时长：{profile_data.get('duration', '2')}小时
        - 核心目标：{profile_data.get('goal', '日常巩固')}
        - **计划开始时间**：{start_time}

        【要求】
        1. **时间安排**：必须从"{start_time}"开始推算时间节点。
        2. 将总时长拆分为多个具体的任务模块（每个模块15-45分钟）。
        3. 必须包含“复习/预习”、“针对性刷题”、“错题整理”等环节。
        4. 针对薄弱点安排高优先级任务。
        5. **严格输出标准 JSON 格式**，不要包含 Markdown 标记。
        6. 请在学情分析中加入一句简短的、充满力量的鼓励语。
        【JSON结构示例】
        {{
            "analysis": "简短的学情分析建议（50字内）",
            "tasks": [
                {{
                    "time_range": "{start_time}-xx:xx", // 务必根据开始时间自动往后推算
                    "subject": "数学",
                    "task": "完成二次函数专项练习",
                    "type": "刷题", 
                    "priority": "High",  // High, Medium, Low
                    "duration": 30,      // 分钟
                    "method": "建议先复习公式，做完后立即对答案"
                }}
            ]
        }}
        """

        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": "你是一个严谨的学习规划AI，只输出JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()

        return json.loads(content)

    except Exception as e:
        logging.error(f"计划生成失败: {e}")
        # 兜底返回（保持格式稳健）
        return {
            "analysis": "AI 连接超时，已为您生成通用复习计划。",
            "tasks": [
                {"time_range": "第1阶段", "subject": "通用", "task": "回顾笔记与预习", "type": "复习",
                 "priority": "Medium", "duration": 30, "method": "快速浏览核心考点"},
                {"time_range": "第2阶段", "subject": "通用", "task": "学科作业/习题", "type": "刷题",
                 "priority": "High", "duration": 45, "method": "专注练习，计时完成"},
                {"time_range": "第3阶段", "subject": "通用", "task": "错题整理与复盘", "type": "复盘",
                 "priority": "High", "duration": 20, "method": "分析错误原因"}
            ]
        }

def generate_exam_questions(criteria):
    """
    生成模拟试题
    :param criteria: 字典，包含 subject, grade, types(list), count, keypoint
    """
    try:
        subject = criteria.get('subject', '通用')
        grade = criteria.get('grade', '通用')
        types = criteria.get('types', ['单选题'])
        count = criteria.get('count', 3)
        keypoint = criteria.get('keypoint', '综合')

        # 限制数量防止超时
        if count > 10: count = 10

        prompt = f"""
        你是一位{grade}{subject}出题专家。请根据以下要求生成一份微型测验题。
        
        【出题要求】
        1. 考察知识点：{keypoint}
        2. 题目数量：{count} 道
        3. 包含题型：{', '.join(types)}
        4. 难度：适中，贴合{grade}水平
        5. **严格输出标准 JSON 格式**，包含一个列表 `questions`。
        
        【JSON结构要求】
        {{
            "questions": [
                {{
                    "type": "单选题",  // 或 填空题, 判断题, 简答题
                    "question": "题目内容...",
                    "options": ["A. x", "B. x"], // 单选需此字段；简答题/填空题/判断题此项为null
                    "answer": "正确答案 (简答题提供参考要点)",
                    "reason": "简短解析"
                }},
                ...
            ]
        }}
        """

        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[
                {"role": "system", "content": "你是一个严谨的出题AI，只输出JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5, # 稍微增加创造性
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(content)
        return data.get('questions', [])

    except Exception as e:
        logging.error(f"出题失败: {e}")
        # 兜底数据
        return [
            {
                "type": "单选题",
                "question": f"({grade}{subject})关于{keypoint}，下列说法正确的是？(AI生成失败兜底题)",
                "options": ["A. 说法一", "B. 说法二", "C. 说法三", "D. 说法四"],
                "answer": "A",
                "reason": f"由于AI连接超时，这是系统自动生成的占位题目。错误信息: {str(e)}"
            }
        ]