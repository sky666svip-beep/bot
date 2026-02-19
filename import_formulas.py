import sys
import os
import re
import json
import logging
from datetime import datetime
# 公式入库
# 将项目根目录加入路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '')))

from app.extensions import db
from app.models import Formula
from app.services.nlp_service import nlp_engine
from app import create_app

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FormulaImporter:
    def __init__(self, js_filepath):
        self.filepath = js_filepath
        self.app = create_app()
        self.batch_size = 50
        self.str_map = {}

    def _extract_strings(self, content):
        """[第一步] 提取并保护所有字符串 (防止后续正则误伤)"""
        self.str_map = {}
        token_counter = 0

        def replace_callback(match):
            nonlocal token_counter
            quote = match.group(1) or match.group(3) or match.group(5)
            text = match.group(2) or match.group(4) or match.group(6) or ""

            # 还原转义
            if quote == "'":
                text = text.replace("\\'", "'").replace('"', '\\"')
            elif quote == "`":
                text = text.replace("\\`", "`").replace('"', '\\"')
                text = text.replace('\n', '\\n')

            final_json_str = json.dumps(text, ensure_ascii=False)
            token = f"__STR_{token_counter}__"
            self.str_map[token] = final_json_str
            token_counter += 1
            return token

        pattern = r"('((?:[^'\\]|\\.)*)')|" \
                  r"(\"((?:[^\"\\]|\\.)*)\")|" \
                  r"(`((?:[^`\\]|\\.)*)`)"
        return re.sub(pattern, replace_callback, content, flags=re.DOTALL)

    def _remove_calculator_block(self, content):
        """[物理剔除] 移除 calculator 块"""
        out = []
        i = 0
        n = len(content)

        while i < n:
            match = re.match(r'[\'"]?calculator[\'"]?\s*:', content[i:])
            if match:
                start_brace_idx = content.find('{', i + len(match.group(0)))
                if start_brace_idx != -1:
                    balance = 1
                    j = start_brace_idx + 1
                    while j < n and balance > 0:
                        if content[j] == '{':
                            balance += 1
                        elif content[j] == '}':
                            balance -= 1
                        j += 1
                    i = j
                    while i < n and content[i].isspace(): i += 1
                    if i < n and content[i] == ',': i += 1
                    continue
            out.append(content[i])
            i += 1
        return "".join(out)

    def _clean_js_to_list(self, file_content):
        logger.info("🧹 正在进行数据清洗 (V14 极简重构版)...")

        # 1. 移除注释
        content = re.sub(r'//.*', '', file_content)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # 2. 提取数组
        start_idx = content.find('[')
        end_idx = content.rfind(']')
        if start_idx == -1: return []
        content = content[start_idx: end_idx + 1]

        # 3. 保护字符串
        content = self._extract_strings(content)

        # 4. [物理删除字段]
        # 删除 subCategory
        content = re.sub(r'subCategory\s*:\s*__STR_\d+__\s*,?', '', content)
        # 删除 related: [...] (内容现在是 [__STR_1__, __STR_2__])
        # 使用非贪婪匹配删除整个数组
        content = re.sub(r'[\'"]?related[\'"]?\s*:\s*\[.*?\],?', '', content, flags=re.DOTALL)

        # 5. 删除 calculator
        content = self._remove_calculator_block(content)

        # 6. 修复 Keys
        content = re.sub(r'(?<!")\b(?!__STR_)([a-zA-Z0-9_]+)\s*:', r'"\1":', content)

        # 7. 处理尾随逗号
        content = re.sub(r',\s*([}\]])', r'\1', content)

        # 8. 还原字符串
        for token, json_str in self.str_map.items():
            content = content.replace(token, json_str)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 解析失败: {e}")
            start = max(0, e.pos - 50)
            end = min(len(content), e.pos + 50)
            logger.error(f"错误上下文: ...{content[start:end]}...")
            return []

    def _generate_embedding(self, item):
        """[极简语义] 只包含名称、条件、备注、变量"""
        variables_desc = ", ".join([f"{v.get('name')}代表{v.get('description')}" for v in item.get('variables', [])])

        semantic_text = f"""
        公式名称: {item.get('name')}
        适用条件: {item.get('conditions')}
        详细含义: {item.get('notes')}
        变量含义: {variables_desc}
        """
        # 移除了 derivation

        semantic_text = "\n".join([line.strip() for line in semantic_text.split('\n') if line.strip()])
        return nlp_engine.encode(semantic_text)

    def run(self):
        if not os.path.exists(self.filepath):
            logger.error(f"文件未找到: {self.filepath}")
            return

        with open(self.filepath, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        formulas_data = self._clean_js_to_list(raw_content)
        if not formulas_data: return

        with self.app.app_context():
            # 重建表结构
            # 注意：生产环境建议使用迁移工具，开发环境可直接 drop
            try:
                Formula.__table__.drop(db.engine)
                logger.info("🗑️ 旧表已删除")
            except:
                pass
            db.create_all()

            if nlp_engine.model is None: nlp_engine._load_model()

            logger.info(f"🚀 开始导入 {len(formulas_data)} 条公式...")
            total = len(formulas_data)
            processed = 0
            created = 0

            for i in range(0, total, self.batch_size):
                batch = formulas_data[i: i + self.batch_size]
                for item in batch:
                    try:
                        vector = self._generate_embedding(item)
                        # grade 可能是数组或字符串
                        grade = item.get('grade')
                        if isinstance(grade, list):
                            grade = ', '.join(grade)
                        
                        formula_data = {
                            #"code": item.get('id'),
                            "name": item.get('name'),
                            "category": item.get('category'),
                            "grade": grade,
                            "formula_text": item.get('formula'),
                            "latex": item.get('latex'),
                            "variables": json.dumps(item.get('variables', []), ensure_ascii=False),
                            "tags": json.dumps(item.get('tags', []), ensure_ascii=False),
                            # related_ids 已移除
                            "conditions": item.get('conditions'),
                            "notes": item.get('notes'),
                            "derivation": item.get('derivation', ''),
                            "embedding": json.dumps(vector)
                        }

                        db.session.add(Formula(**formula_data))
                        created += 1
                    except Exception as e:
                        logger.error(f"导入出错 {item.get('id')}: {e}")

                db.session.commit()
                processed += len(batch)
                logger.info(f"📊 进度: {processed}/{total}")

            logger.info(f"🎉 导入完成! 共新增: {created}")


if __name__ == '__main__':
    target_file = os.path.join(os.getcwd(), 'data/formulasDB.js')
    if len(sys.argv) > 1: target_file = sys.argv[1]
    FormulaImporter(target_file).run()