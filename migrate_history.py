import sys
import os
import sqlite3
from app import create_app, db
from app.models import User, UserHistory

def add_column_if_not_exists(app):
    db_path = os.path.join(app.root_path, '..', 'data', 'app.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 检查列是否存在
    cursor = c.execute('PRAGMA table_info(user_history)')
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'user_id' not in columns:
        print("Adding user_id column to user_history table...")
        try:
            c.execute('ALTER TABLE user_history ADD COLUMN user_id INTEGER')
            conn.commit()
            print("Column added successfully.")
        except Exception as e:
            print(f"Error adding column: {e}")
    else:
        print("Column user_id already exists.")
    conn.close()

def migrate():
    app = create_app()
    
    # 0. 手动修补数据库架构
    add_column_if_not_exists(app)
    
    with app.app_context():
        # 1. 创建 admin 用户
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Creating admin user...")
            admin = User(username='admin', is_admin=True)
            admin.set_password('admin123') # 设置一个初始密码，生产环境应修改
            db.session.add(admin)
            db.session.commit()
            print(f"Admin user created with ID: {admin.id}")
        else:
            print(f"Admin user already exists with ID: {admin.id}")
            
        # 2. 迁移历史记录
        print("Migrating history records...")
        # 查找所有 user_id 为空的记录
        null_history = UserHistory.query.filter(UserHistory.user_id == None).all()
        count = len(null_history)
        
        if count > 0:
            for h in null_history:
                h.user_id = admin.id
            db.session.commit()
            print(f"Successfully migrated {count} records to admin user.")
        else:
            print("No history records need migration.")

if __name__ == '__main__':
    migrate()
