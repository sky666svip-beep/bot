import unittest
from app import create_app, db
from app.config import Config
from app.models import User, UserHistory
from flask_login import current_user

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class AuthTestCase(unittest.TestCase):
    def setUp(self):
        # 使用测试配置创建应用，此时 db.init_app 会使用内存数据库
        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # 创建表（在内存数据库中）
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def register(self, username, password, confirm):
        return self.client.post('/api/register', data=dict(
            username=username,
            password=password,
            confirm=confirm
        ), follow_redirects=True)

    def login(self, username, password):
        return self.client.post('/api/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.client.post('/api/logout', follow_redirects=True)

    def test_register_and_login(self):
        # 1. 注册
        response = self.register('testuser', 'password', 'password')
        self.assertEqual(response.status_code, 200)
        user = User.query.filter_by(username='testuser').first()
        self.assertIsNotNone(user)
        self.assertTrue(user.check_password('password'))
        
        # 2. 登出
        self.logout()
        
        # 3. 登录
        response = self.login('testuser', 'password')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'testuser', response.data)

    def test_page_protection(self):
        # 未登录访问受保护页面，应重定向到登录页 (302)
        response = self.client.get('/api/history')
        self.assertEqual(response.status_code, 302) 
        self.assertIn('/login', response.location)

    def test_user_isolation(self):
        # 用户 A
        self.register('userA', 'password', 'password')
        
        # A 添加一条历史
        h1 = UserHistory(question='Q1', user_id=1)
        db.session.add(h1)
        db.session.commit()
        
        # A 查看历史
        response = self.client.get('/api/history')
        self.assertIn(b'Q1', response.data)
        
        self.logout()
        
        # 用户 B
        self.register('userB', 'password', 'password')
        
        # B 查看历史，不应该看到 Q1
        response = self.client.get('/api/history')
        self.assertNotIn(b'Q1', response.data)

if __name__ == '__main__':
    unittest.main()
