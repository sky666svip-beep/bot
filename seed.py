# seed.py
#import pandas as pd
from app import create_app
from app.extensions import db
from app.models import QuestionBank
from app.services.nlp_service import nlp_engine

app = create_app()
'''
import pandas as pd
# ... 前面的代码保持不变 ...
导入你自己的 Excel 题库
def seed_from_excel(file_path):
    df = pd.read_excel(file_path) # 假设列名是: 题目, 选项, 答案, 解析
    with app.app_context():
        for _, row in df.iterrows():
            # 选项处理：假设 Excel 里是用“|”分隔的 A|B|C|D
            options = row['选项'].split('|') 
            
            new_q = QuestionBank(
                question=row['题目'],
                answer=row['答案'],
                explanation=row['解析'],
                vector_data=nlp_engine.encode(row['题目']).cpu().numpy()
            )
            new_q.set_options(options)
            db.session.add(new_q)
        db.session.commit()
'''
print("Hello, World!")

def seed_data():
    with app.app_context():
        # 清空旧数据 (可选)
        # db.drop_all()
        # db.create_all()

        test_questions = [
            {
                "q": "中国的首都是哪里？",
                "o": ["上海", "北京", "广州", "深圳"],
                "a": "B",
                "e": "北京是中华人民共和国的首都。"
            },
            {
                "q": "机器学习中监督学习的代表算法是什么？",
                "o": ["K-Means", "逻辑回归", "PCA", "FP-Growth"],
                "a": "B",
                "e": "逻辑回归是经典的监督学习分类算法。"
            }
        ]

        for item in test_questions:
            # 检查是否已存在
            if not QuestionBank.query.filter_by(question=item['q']).first():
                new_q = QuestionBank(
                    question=item['q'],
                    answer=item['a'],
                    explanation=item['e'],
                    # 关键步骤：入库前先计算好向量
                    vector_data=nlp_engine.encode(item['q']).cpu().numpy()
                )
                new_q.set_options(item['o'])
                db.session.add(new_q)

        db.session.commit()
        print("✅ 测试数据导入成功！")


if __name__ == '__main__':
    seed_data()