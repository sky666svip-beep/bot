import pandas as pd
import json
import os
import logging
import re
from tqdm import tqdm  # 建议安装：pip install tqdm
from app import create_app
from app.extensions import db
from app.models import QuestionBank
from app.services.nlp_service import nlp_engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_and_import(file_path):
    app = create_app()
    with app.app_context():
        if not os.path.exists(file_path):
            logging.error(f"找不到文件: {file_path}")
            return
        # 1. 加载数据
        df = pd.read_excel(file_path) if file_path.endswith('.xlsx') else pd.read_csv(file_path)
        option_cols = ['选项A', '选项B', '选项C', '选项D', '选项E', '选项F']

        print(f"\n🚀 正在通过 Qwen3-0.6B 引擎处理 {len(df)} 条题目...")

        prep_data = []  # 存放解析后的临时数据
        texts_to_encode = []  # 存放待批量编码的文本

        # 第一阶段：解析内容并计算
        for index, row in tqdm(df.iterrows(), total=len(df), desc="解析内容"):
            try:
                # 1. 获取并清洗原始题目
                q_raw = str(row.get('题目', '')).strip()
                if not q_raw: continue

                q_clean = nlp_engine.clean_prefix(q_raw)
                std_q_text = nlp_engine.standardize_text(q_raw)  # 指纹生成

                # 2. 提取答案与解析
                raw_answer = str(row.get('正确答案', '')).strip()
                reason = str(row.get('解析', '详见解析')).strip()

                # 3. 处理选项
                options_list = []
                for col in option_cols:
                    val = row.get(col)
                    if pd.notna(val) and str(val).strip():
                        options_list.append(str(val).strip())

                # 4. 处理多选答案映射
                final_answer = raw_answer
                if len(raw_answer) <= 6 and re.match(r'^[A-F, |]+$', raw_answer):
                    ans_keys = re.findall(r'[A-F]', raw_answer)
                    mapped = []
                    for key in ans_keys:
                        idx = ord(key) - ord('A')
                        if idx < len(options_list):
                            mapped.append(options_list[idx])
                    if mapped:
                        final_answer = " | ".join(mapped)
                prep_data.append({
                    "question": q_clean,  # 存入干净题目，解决数字匹配问题
                    "std_q": std_q_text,  # 存入标准指纹，解决极速检索问题
                    "answer": final_answer,
                    "reason": reason,
                    "options": json.dumps(options_list, ensure_ascii=False) if options_list else None
                })

                # 6. 收集待向量化的文本（同样用干净的题目，分数更稳）
                texts_to_encode.append(q_clean)

            except Exception as e:
                logging.error(f"第 {index} 行解析失败: {e}")

        # 第二阶段：批量向量化
        print(f"🧠 正在进行批量向量化 (Qwen3-0.6B)...")
        # 0.6B模型 batch_size 设为 32-64 (视显存而定)
        all_embeddings = nlp_engine.model.encode(
            texts_to_encode,
            batch_size=64,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        # 第三阶段：组合数据并批量入库
        print(f"💾 正在写入数据库...")
        question_objs = []
        for i, data in enumerate(prep_data):
            new_q = QuestionBank(
                question=data["question"],
                std_q=data["std_q"],
                answer=data["answer"],
                reason=data["reason"],
                options=data["options"],
                embedding=json.dumps(all_embeddings[i].tolist())  # 存入新维度的向量
            )
            question_objs.append(new_q)
        db.session.bulk_save_objects(question_objs)
        db.session.commit()
        print(f"✅ 导入成功！共录入 {len(question_objs)} 条题目。")


if __name__ == "__main__":
    # 删除旧的 choicebot.db
    clean_and_import("data/1.xlsx")