# init_db.py
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    # 强制删除所有旧表（如果有的话）
    db.drop_all()
    # 根据最新的 models.py 创建所有新表
    db.create_all()
    print("✅ 数据库已重新初始化！")