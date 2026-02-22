# run.py 本地开发测试 sreve.py生产环境
import os
from dotenv import load_dotenv

os.environ['PYTHONDONTWRITEBYTECODE'] = '1'  # 禁止生成 .pyc 缓存，确保热重载始终读取最新源码

# 1. 显式加载 .env 文件，确保配置可用
load_dotenv()

from app import create_app, db
from app.models import QuestionBank
from app.services.nlp_service import nlp_engine
app = create_app()

with app.app_context():
    # 检查数据库是否有数据
    if QuestionBank.query.first():
        print(" 正在加载 NLP 显存索引...")
        # 传入模型类，读取数据构建矩阵
        nlp_engine.refresh_index(QuestionBank)
    else:
        print("⚠️ 数据库为空，跳过索引加载。请先运行 advanced_import.py")

if __name__ == '__main__':
    # 启动 Flask
    app.run(debug=True, host='0.0.0.0', port=5000)