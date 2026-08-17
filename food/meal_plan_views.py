"""智能配餐助手 - 按餐次从菜谱库自动搭配一整天

GET  /api/food/meal-plan/?date=YYYY-MM-DD
  -> { date, breakfast: [recipes], lunch: [...], dinner: [...], snack: [...] }
     各餐次的候选菜谱（按分类筛选，排除过敏食材）

POST /api/food/meal-plan/  body: {date, plan: {breakfast: [id,...], lunch: [...], ...}}
  -> 保存/覆盖当天该餐次的 MealLog，返回创建数
"""
import random

from django.db.models import Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Recipe, MealLog
from .serializers import RecipeSerializer


class MealPlanView(APIView):
    """配餐助手：候选池 + 一键生成"""

    def _pool(self, user, categories, limit=15):
        """按分类取候选菜谱，排除过敏食材"""
        qs = Recipe.objects.filter(
            Q(user=user) | Q(is_public=True), category__in=categories
        )
        allergy = getattr(user, "profile", None) and user.profile.allergy or ""
        if allergy:
            for item in allergy.split(","):
                item = item.strip()
                if item:
                    qs = qs.exclude(ingredients__icontains=item)
        return list(qs[:limit])

    def get(self, request):
        date = request.query_params.get("date") or timezone.now().date().isoformat()
        user = request.user

        def s(cats, limit=15):
            recs = self._pool(user, cats, limit)
            return RecipeSerializer(recs, many=True).data

        return Response(
            {
                "date": date,
                "breakfast": s(["主食", "汤品", "小吃"]),          # 粥面馒头
                "lunch": s(["家常菜", "汤品"]),                    # 荤素+汤
                "dinner": s(["家常菜", "凉菜", "主食", "汤品"]),   # 主+凉+主食
                "snack": s(["甜品", "小吃"]),                      # 甜品小吃
            }
        )

    def post(self, request):
        user = request.user
        date = request.data.get("date") or timezone.now().date().isoformat()
        plan = request.data.get("plan") or {}

        created = 0
        # 先删当天已有记录（覆盖式生成）
        MealLog.objects.filter(user=user, date=date).delete()
        for meal_type, ids in plan.items():
            if not isinstance(ids, list):
                continue
            for rid in ids[:5]:  # 每餐最多5道
                recipe = Recipe.objects.filter(
                    Q(user=user) | Q(is_public=True), id=rid
                ).first()
                if recipe:
                    MealLog.objects.create(
                        user=user, date=date, meal_type=meal_type, recipe=recipe
                    )
                    created += 1
        return Response({"message": f"已生成 {created} 道餐食", "created": created})

    def delete(self, request):
        """清空指定日期的全部餐食记录（恢复空白）"""
        user = request.user
        date = request.query_params.get("date") or request.data.get("date") or timezone.now().date().isoformat()
        count, _ = MealLog.objects.filter(user=user, date=date).delete()
        return Response({"message": f"已清空当天 {count} 道餐食", "deleted": count})


class MealPlanGenerateView(APIView):
    """一键生成：随机搭配一整天（早2+午3+晚3+加1）"""

    def get(self, request):
        user = request.user
        date = request.query_params.get("date") or timezone.now().date().isoformat()

        def pick(cats, n):
            recs = self._pool(user, cats, 30)
            random.shuffle(recs)
            return [{"id": r.id, "title": r.title} for r in recs[:n]]

        return Response(
            {
                "date": date,
                "plan": {
                    "breakfast": pick(["主食", "汤品", "小吃"], 2),
                    "lunch": pick(["家常菜", "汤品"], 3),
                    "dinner": pick(["家常菜", "凉菜", "主食"], 3),
                    "snack": pick(["甜品", "小吃"], 1),
                },
            }
        )

    def _pool(self, user, categories, limit=30):
        qs = Recipe.objects.filter(
            Q(user=user) | Q(is_public=True), category__in=categories
        )
        allergy = getattr(user, "profile", None) and user.profile.allergy or ""
        if allergy:
            for item in allergy.split(","):
                item = item.strip()
                if item:
                    qs = qs.exclude(ingredients__icontains=item)
        return list(qs[:limit])
