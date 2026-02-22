#
import json
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(db.Model, UserMixin):
    """用户表"""
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 与 UserHistory 的一对多关系
    histories = db.relationship('UserHistory', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class VerificationCode(db.Model):
    """验证码表"""
    __tablename__ = 'verification_code'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(10), nullable=False)
    purpose = db.Column(db.String(50), nullable=False, default='verify') # verify, reset_password
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)


class QuestionBank(db.Model):
    """
    题库表：存储题目原本内容 + qwen 1024维向量
    """
    __tablename__ = 'question_bank'
    id = db.Column(db.Integer, primary_key=True)
    # 1. 题目内容：建议用 Text，防止长题目被截断
    question = db.Column(db.Text, nullable=False, index=True)
    # 标准化题干指纹
    # 精确匹配，建立 B-Tree 索引
    # 长度建议 512 或 1024，视具体业务题目长度而定
    std_q = db.Column(db.String(1024), nullable=True, index=True)
    # 2. 答案：现在这里存储的是处理后的 "A. xxx | B. xxx" 或完整文本
    answer = db.Column(db.Text, nullable=False)

    # 3. 解析
    reason = db.Column(db.Text, default='暂无解析')

    # 4. 选项：存储原始 JSON 字符串 (["A. xx", "B. xx"])
    options = db.Column(db.Text)

    # 5. 向量字段
    embedding = db.Column(db.Text)

    # 6. 入库时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50), default='本地题库')

    def to_dict(self):
        return {
            'id': self.id,
            'question': self.question,
            'answer': self.answer,
            'reason': self.reason,
            'options': self.options
        }

class Poetry(db.Model):
    """
    古诗词基础表：存储原文信息
    """
    __tablename__ = 'poetry'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    dynasty = db.Column(db.String(50)) # 朝代
    content = db.Column(db.Text, nullable=False) # 原文
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 联合索引加速搜索
    __table_args__ = (
        db.Index('idx_poetry_title_author', 'title', 'author'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'dynasty': self.dynasty,
            'content': self.content
        }

class PoetryAnalysis(db.Model):
    """
    古诗词赏析表：存储分级赏析内容
    """
    __tablename__ = 'poetry_analysis'
    id = db.Column(db.Integer, primary_key=True)
    poetry_id = db.Column(db.Integer, db.ForeignKey('poetry.id'), nullable=False)
    
    translation = db.Column(db.Text) # 译文
    appreciation = db.Column(db.Text) # 赏析
    annotations = db.Column(db.Text) # 注释 (JSON string)
    
    # 冗余字段用于快速检索，避免每次都联表
    title = db.Column(db.String(255))
    author = db.Column(db.String(255))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_analysis_lookup', 'title', 'author'),
    )

    def to_dict(self):
        import json
        try:
            ants = json.loads(self.annotations) if self.annotations else []
        except:
            ants = []
            
        return {
            'id': self.id,
            'poetry_id': self.poetry_id,
            'translation': self.translation,
            'appreciation': self.appreciation,
            'annotations': ants,
            'title': self.title,
            'author': self.author
        }

class UserHistory(db.Model):
    """
    用户搜题历史表
    """
    __tablename__ = 'user_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    reason = db.Column(db.Text)
    is_mistake = db.Column(db.Boolean, default=False)  # 是否为错题

    # 来源标记：例如 "语义匹配" / "AI视觉" / "GPT生成"
    source = db.Column(db.String(50), default='unknown')

    # 记录时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50), default='其他')

    def to_dict(self):
        return {
            'id': self.id,
            'question': self.question,
            'answer': self.answer,
            'reason': self.reason,
            'source': self.source,
            'category': self.category,
            'is_mistake': self.is_mistake,
            'time': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

    # app/models.py (追加)

    # === 4. [新增] 公式大全表 ===
class Formula(db.Model):
        """
        公式大全表：支持语义检索和 LLM 讲解
        """
        __tablename__ = 'formulas'

        id = db.Column(db.Integer, primary_key=True)
        # [DELETE] code 字段已移除
        name = db.Column(db.String(100), nullable=False, index=True)  # 例如: 勾股定理

        # 分类
        category = db.Column(db.String(50))  # 科目
        grade = db.Column(db.String(20))  # 学段

        # 核心展示
        formula_text = db.Column(db.Text)  # 文本公式
        latex = db.Column(db.Text)  # Latex 源码

        # 复杂结构 (JSON 字符串)
        variables = db.Column(db.Text)  # 公式变量解释
        tags = db.Column(db.Text)  # 标签（'常用公式', '必背公式'）

        # 知识详情
        conditions = db.Column(db.Text)  # 适用条件
        notes = db.Column(db.Text)  # 公式备注
        derivation = db.Column(db.Text)  # 推导过程


        # 核心：语义向量
        embedding = db.Column(db.Text)

        created_at = db.Column(db.DateTime, default=datetime.utcnow)

        def to_dict(self):
            return {
                'id': self.id,
                'name': self.name,
                'category': self.category,
                'latex': self.latex,
                'formula': self.formula_text,
                'variables': json.loads(self.variables) if self.variables else [],
                'notes': self.notes,
                'conditions': self.conditions,
                'derivation': self.derivation,
                'tags': json.loads(self.tags) if self.tags else [],
            }

# === 5. [新增] 单词表 (映射现有表) ===
class Vocabulary(db.Model):
    """
    单词表：映射现有 vocabulary 表
    """
    __tablename__ = 'vocabulary'
    
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.Text, nullable=False, unique=True)
    phonetic = db.Column(db.Text)
    definition = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'word': self.word,
            'phonetic': self.phonetic,
            'definition': self.definition
        }

# === 6. [新增] 成语表 (映射现有表) ===
class Idiom(db.Model):
    """
    成语表：成语 PK 数据来源
    """
    __tablename__ = 'idiom'
    
    id = db.Column(db.Integer, primary_key=True)
    derivation = db.Column(db.Text)
    example = db.Column(db.Text)
    explanation = db.Column(db.Text)
    pinyin = db.Column(db.Text)
    word = db.Column(db.Text)
    abbreviation = db.Column(db.Text)
    pinyin_r = db.Column(db.Text)
    first = db.Column(db.Text)
    last = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'word': self.word,
            'pinyin': self.pinyin,
            'explanation': self.explanation,
            'derivation': self.derivation,
            'example': self.example,
            'first': self.first,
            'last': self.last
        }
