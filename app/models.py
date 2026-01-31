#
from datetime import datetime
from app.extensions import db

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

class UserHistory(db.Model):
    """
    用户搜题历史表
    """
    __tablename__ = 'user_history'

    id = db.Column(db.Integer, primary_key=True)
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