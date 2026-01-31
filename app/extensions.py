# app/extensions.py
from flask_sqlalchemy import SQLAlchemy

# 初始化扩展，但暂时不绑定 app
db = SQLAlchemy()