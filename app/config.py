# 配置文件 (开发/生产环境配置)
# app/config.py
import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, '../data/app.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False