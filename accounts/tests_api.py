"""LifeHub 核心 API 测试

覆盖: 注册 / 登录 / 权限保护 / 仪表盘 / 衣 食 住 行 四模块核心 CRUD
运行: python manage.py test
"""
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import UserProfile


def make_client(user=None):
    """返回已认证(或匿名)的 API client"""
    client = APIClient()
    if user:
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register(self):
        resp = self.client.post(
            "/api/auth/register/",
            {"username": "newuser", "password": "pass123456", "email": "n@e.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(username="newuser").exists())
        self.assertTrue(UserProfile.objects.filter(user__username="newuser").exists())

    def test_login_returns_jwt(self):
        User.objects.create_user(username="demo", password="demo123456")
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "demo", "password": "demo123456"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_login_wrong_password(self):
        User.objects.create_user(username="demo", password="demo123456")
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "demo", "password": "wrong"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_api_requires_auth(self):
        """未带 token 访问业务 API 应 401"""
        resp = self.client.get("/api/dashboard/")
        self.assertEqual(resp.status_code, 401)
        for path in ["/api/wardrobe/clothes/", "/api/food/recipes/",
                     "/api/home/expenses/", "/api/travel/trips/"]:
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 401, f"{path} 应拒绝匿名访问")


class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="demo", password="demo123456")
        self.client = make_client(self.user)

    def test_dashboard_aggregates(self):
        resp = self.client.get("/api/dashboard/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        for key in ["user", "wardrobe", "food", "home", "travel"]:
            self.assertIn(key, data)


class WardrobeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="demo", password="demo123456")
        self.client = make_client(self.user)

    def test_create_and_list_clothes(self):
        resp = self.client.post(
            "/api/wardrobe/clothes/",
            {"name": "白色T恤", "category": "top", "color": "白色",
             "season": "summer", "brand": "优衣库"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = self.client.get("/api/wardrobe/clothes/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)


class FoodTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="demo", password="demo123456")
        self.client = make_client(self.user)

    def test_create_recipe(self):
        resp = self.client.post(
            "/api/food/recipes/",
            {"title": "番茄炒蛋", "category": "家常菜", "cuisine": "中餐",
             "difficulty": 2, "cook_time": 15, "budget": "10.00",
             "ingredients": "番茄\n鸡蛋", "steps": "1.切番茄\n2.炒蛋\n3.合炒"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_recipe_suggest(self):
        resp = self.client.get("/api/food/suggest/")
        self.assertEqual(resp.status_code, 200)


class HomeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="demo", password="demo123456")
        self.client = make_client(self.user)

    def test_create_expense_and_summary(self):
        resp = self.client.post(
            "/api/home/expenses/",
            {"category": "food", "amount": "25.50", "title": "午饭", "date": "2026-08-16"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = self.client.get("/api/home/expenses/summary/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("total", resp.data)


class TravelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="demo", password="demo123456")
        self.client = make_client(self.user)

    def test_create_trip(self):
        resp = self.client.post(
            "/api/travel/trips/",
            {"title": "杭州三日游", "destination": "杭州",
             "start_date": "2026-08-30", "end_date": "2026-09-01"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = self.client.get("/api/travel/trips/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_commute_summary(self):
        resp = self.client.get("/api/travel/commute/summary/")
        self.assertEqual(resp.status_code, 200)
