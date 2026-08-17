"""accounts views - 注册、档案、仪表盘聚合"""

from datetime import timedelta
import urllib.parse
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q, Case, When, Value, IntegerField
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserProfile
from .serializers import UserProfileSerializer, RegisterSerializer
from .weather import fetch_weather, geocode, _fetch_json
from .ai_service import call_ai, AIError

from wardrobe.models import Clothing, OutfitLog
from food.models import Recipe, MealLog, ShoppingItem
from home.models import Expense, HouseTask, HomeInventory
from travel.models import Trip, CommuteLog


class AIRecommendView(APIView):
    """AI 智能推荐 - 使用用户配置的 API (URL + Key)

    POST /api/ai/recommend/  body: {"type": "wardrobe|food|travel", "extra": {...}}
    """

    def post(self, request):
        rtype = request.data.get("type", "")
        extra = request.data.get("extra") or {}
        profile = getattr(request.user, "profile", None)
        if not profile:
            return Response({"error": "用户档案不存在"}, status=400)
        if not profile.ai_api_key:
            return Response(
                {"error": "未配置 AI Key，请到「我的」页面填写 API 地址和 Key"},
                status=400,
            )

        system, prompt = self._build_prompt(request.user, profile, rtype, extra)
        try:
            text = call_ai(profile.ai_api_url, profile.ai_api_key, system, prompt)
        except AIError as e:
            return Response({"error": str(e)}, status=502)
        return Response({"result": text})

    def _build_prompt(self, user, profile, rtype, extra):
        if rtype == "wardrobe":
            system = (
                "你是个人穿搭顾问。根据用户衣柜和天气场合，推荐具体的搭配组合。"
                "回答用中文，简洁实用，直接给出 2-3 套搭配建议，每套含上装/下装/外套/鞋子及理由，不要客套话。"
            )
            clothes = Clothing.objects.filter(user=user)
            items = [
                f"{c.name}({c.get_category_display()}/{c.color}/{c.get_season_display()}"
                f"{'收藏' if c.is_favorite else ''})"
                for c in clothes[:40]
            ]
            user_prompt = (
                f"我的衣柜: {'、'.join(items) if items else '空'}\n"
                f"温度: {extra.get('temperature', '?')}°C, 场合: {extra.get('occasion', '日常')}\n"
                f"我的身高 {profile.height or '?'}cm, 体重 {profile.weight or '?'}kg\n"
                "请推荐搭配。"
            )
            return system, user_prompt

        if rtype == "food":
            system = (
                "你是美食营养顾问。根据用户食材库、饮食偏好和过敏情况，推荐菜谱和一周饮食建议。"
                "回答用中文，简洁实用，不要客套话。"
            )
            recipes = Recipe.objects.filter(Q(user=user) | Q(is_public=True))[:30]
            ritems = [
                f"{r.title}({r.category},约{r.cook_time or '?'}分钟)"
                for r in recipes
            ]
            user_prompt = (
                f"我的菜谱库: {'、'.join(ritems) if ritems else '空'}\n"
                f"饮食偏好: {profile.diet_preference or '无限制'}\n"
                f"过敏食物: {profile.allergy or '无'}\n"
                f"今日已记录 {MealLog.objects.filter(user=user).count()} 条餐食。\n"
                f"本月预算: {profile.monthly_budget or '未设置'} 元\n"
                "请推荐 3 道适合今天的菜（含理由），并给一句饮食建议。"
            )
            return system, user_prompt

        if rtype == "travel":
            system = (
                "你是旅行规划师。根据用户的行程和通勤情况，给出实用建议。"
                "回答用中文，简洁实用，不要客套话。"
            )
            trips = Trip.objects.filter(user=user).order_by("-start_date")[:5]
            titems = [
                f"{t.title}({t.destination},{t.start_date}~{t.end_date},{t.status})"
                for t in trips
            ]
            user_prompt = (
                f"我的行程: {'、'.join(titems) if titems else '暂无'}\n"
                f"通勤方式: {profile.commute_mode or '未设置'}，"
                f"通勤时长: {profile.commute_minutes or '?'} 分钟\n"
                f"即将出行: {extra.get('trip', '无')}\n"
                "请给出建议（行程准备/打包清单/通勤优化）。"
            )
            return system, user_prompt

        return (
            "你是生活助手，回答简洁实用。",
            f"用户问题: {rtype} {json.dumps(extra, ensure_ascii=False)}",
        )


class WeatherView(APIView):
    """实时天气 + 未来7天预报（Open-Meteo，无需 key）

    GET /api/weather/?city=北京&hourly=1
    """

    def get(self, request):
        city = request.query_params.get("city") or ""
        if not city and hasattr(request.user, "profile") and request.user.profile.city:
            city = request.user.profile.city
        if not city:
            city = "北京"  # 兜底默认城市，避免新用户看不到天气
        with_hourly = request.query_params.get("hourly") == "1"

        # 双通道自动切换: 中国天气网(国内官方,主) -> Open-Meteo(国外,备)
        from .cnweather import fetch_weather as fetch_cnweather
        from .weather import fetch_weather as fetch_openmeteo

        data = fetch_cnweather(city, with_hourly=with_hourly)
        if data is None:
            data = fetch_openmeteo(city, with_hourly=with_hourly)
        if not data:
            return Response({"error": f"获取 {city} 天气失败，请检查城市名或网络"}, status=502)

        # 中国天气网无逐小时数据时，用 Open-Meteo 补充
        if with_hourly and (not data.get("hourly")):
            hourly_data = fetch_openmeteo(city, with_hourly=True)
            if hourly_data and hourly_data.get("hourly"):
                data["hourly"] = hourly_data["hourly"]

        # 今天只有低温时用实时温度补最高温
        if data.get("daily") and data.get("current") and data["current"].get("temp") is not None:
            if data["daily"] and data["daily"][0].get("tmax") is None:
                data["daily"][0]["tmax"] = round(data["current"]["temp"])
        return Response(data)


class WeatherCitiesView(APIView):
    """常用城市列表（天气频道城市切换）"""

    CITIES = [
        {"name": "北京", "lat": 39.9042, "lon": 116.4074},
        {"name": "上海", "lat": 31.2304, "lon": 121.4737},
        {"name": "广州", "lat": 23.1291, "lon": 113.2644},
        {"name": "深圳", "lat": 22.5431, "lon": 114.0579},
        {"name": "杭州", "lat": 30.2741, "lon": 120.1551},
        {"name": "成都", "lat": 30.5728, "lon": 104.0668},
        {"name": "武汉", "lat": 30.5928, "lon": 114.3055},
        {"name": "重庆", "lat": 29.5630, "lon": 106.5516},
        {"name": "西安", "lat": 34.3416, "lon": 108.9398},
        {"name": "南京", "lat": 32.0603, "lon": 118.7969},
        {"name": "长沙", "lat": 28.2282, "lon": 112.9388},
        {"name": "青岛", "lat": 36.0671, "lon": 120.3826},
        {"name": "厦门", "lat": 24.4798, "lon": 118.0894},
        {"name": "昆明", "lat": 25.0389, "lon": 102.7183},
        {"name": "哈尔滨", "lat": 45.8038, "lon": 126.5350},
    ]

    def get(self, request):
        return Response(self.CITIES)


class WeatherSearchView(APIView):
    """城市搜索（Open-Meteo geocoding 代理）

    GET /api/weather/search/?q=苏州
    """

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"error": "缺少搜索关键词"}, status=400)

        # 通道1: 中国天气网城市搜索（国内稳定）
        try:
            from .cnweather import search_city
            results = search_city(q)
            if results:
                return Response(results[:5])
        except Exception:
            pass

        # 通道2: Open-Meteo geocoding（备用）
        try:
            url = (
                "https://geocoding-api.open-meteo.com/v1/search"
                f"?name={urllib.parse.quote(q)}&count=5&language=zh&format=json"
            )
            data = _fetch_json(url)
            results = []
            for r in data.get("results") or []:
                results.append(
                    {
                        "name": r.get("name", q),
                        "lat": r.get("latitude"),
                        "lon": r.get("longitude"),
                        "admin1": r.get("admin1", ""),
                        "country": r.get("country", ""),
                    }
                )
            return Response(results)
        except Exception:
            return Response({"error": "城市搜索失败，请检查网络"}, status=502)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )


class UserProfileView(APIView):
    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return Response(UserProfileSerializer(profile).data)

    def put(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PasswordChangeView(APIView):
    def post(self, request):
        user = request.user
        new = request.data.get("new_password", "")
        if len(new) < 6:
            return Response({"error": "新密码至少6位"}, status=400)
        user.set_password(new)
        user.save()
        return Response({"message": "密码修改成功"})


class DashboardView(APIView):
    """仪表盘聚合 - 返回四模块概览数据"""

    def get(self, request):
        user = request.user
        today = timezone.now().date()
        month_start = today.replace(day=1)

        # 衣
        wardrobe_count = Clothing.objects.filter(user=user).count()
        today_outfit = OutfitLog.objects.filter(user=user, date=today).first()
        recent_outfits = OutfitLog.objects.filter(user=user).count()

        # 食
        today_meals = MealLog.objects.filter(user=user, date=today)
        # 餐次顺序: 早餐 < 午餐 < 晚餐 < 宵夜
        today_meals = today_meals.annotate(
            meal_order=Case(
                When(meal_type="breakfast", then=Value(0)),
                When(meal_type="lunch", then=Value(1)),
                When(meal_type="dinner", then=Value(2)),
                When(meal_type="snack", then=Value(3)),
                default=Value(9),
                output_field=IntegerField(),
            )
        ).order_by("meal_order", "id")
        today_meals_list = [
            {
                "meal_type": m.meal_type,
                "recipe_title": m.recipe.title if m.recipe else (m.custom_food or ""),
            }
            for m in today_meals
        ]
        recipe_count = Recipe.objects.filter(Q(user=user) | Q(is_public=True)).count()
        pending_shopping = ShoppingItem.objects.filter(
            user=user, is_purchased=False
        ).count()

        # 住
        month_expenses = Expense.objects.filter(user=user, date__gte=month_start)
        month_total = month_expenses.aggregate(total=Sum("amount"))["total"] or 0
        category_breakdown = {}
        for cat in month_expenses.values("category").annotate(total=Sum("amount")):
            category_breakdown[cat["category"]] = float(cat["total"])

        # 近30天每日支出趋势
        trend_start = today - timedelta(days=29)
        daily = (
            Expense.objects.filter(user=user, date__gte=trend_start)
            .extra(select={"day": "strftime('%%m-%%d', date)"})
            .values("day")
            .annotate(total=Sum("amount"))
            .order_by("day")
        )
        expense_trend = [{"day": d["day"], "total": float(d["total"])} for d in daily]

        pending_tasks = HouseTask.objects.filter(user=user, is_done=False).count()
        overdue_tasks = HouseTask.objects.filter(
            user=user, is_done=False, next_due_date__lt=today
        )
        overdue_task_list = [
            {"title": t.title, "due_date": str(t.next_due_date)}
            for t in overdue_tasks[:10]
        ]
        low_stock = (
            HomeInventory.objects.filter(user=user)
            .extra(where=["quantity <= min_quantity"])
            .count()
        )
        low_stock_list = [
            {"name": i.name, "quantity": float(i.quantity), "unit": i.unit}
            for i in HomeInventory.objects.filter(user=user)
            .extra(where=["quantity <= min_quantity"])[:10]
        ]
        expiring_soon = [
            {"name": i.name, "expiry_date": str(i.expiry_date)}
            for i in HomeInventory.objects.filter(
                user=user, expiry_date__isnull=False, expiry_date__lte=today + timedelta(days=7)
            )[:10]
        ]

        # 行
        upcoming_trips = Trip.objects.filter(
            user=user, start_date__gte=today, status="planned"
        ).order_by("start_date")[:3]
        commute_this_week = CommuteLog.objects.filter(
            user=user, date__gte=today - timedelta(days=7)
        ).count()

        return Response(
            {
                "user": {
                    "username": user.username,
                    "nickname": getattr(user, "profile", None)
                    and user.profile.nickname
                    or user.username,
                },
                "wardrobe": {
                    "total_clothes": wardrobe_count,
                    "today_outfit_logged": bool(today_outfit),
                    "total_outfits": recent_outfits,
                },
                "food": {
                    "today_meals": today_meals_list,
                    "recipe_count": recipe_count,
                    "pending_shopping": pending_shopping,
                },
                "home": {
                    "month_expense": float(month_total),
                    "category_breakdown": category_breakdown,
                    "expense_trend": expense_trend,
                    "pending_tasks": pending_tasks,
                    "overdue_tasks": len(overdue_task_list),
                    "overdue_task_list": overdue_task_list,
                    "low_stock_items": low_stock,
                    "low_stock_list": low_stock_list,
                    "expiring_soon": expiring_soon,
                },
                "travel": {
                    "upcoming_trips": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "destination": t.destination,
                            "start_date": str(t.start_date),
                            "end_date": str(t.end_date),
                            "days": t.duration_days,
                        }
                        for t in upcoming_trips
                    ],
                    "commute_this_week": commute_this_week,
                },
                "date": str(today),
            }
        )
