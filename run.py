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

if __name__ == '__main__':
    # 启动 Flask
    app.run(debug=True, host='0.0.0.0', port=5000)