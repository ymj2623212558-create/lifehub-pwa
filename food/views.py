"""food views"""

from django.db.models import Q, Sum
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Recipe, MealLog, ShoppingItem
from .serializers import RecipeSerializer, MealLogSerializer, ShoppingItemSerializer


class RecipeListCreateView(generics.ListCreateAPIView):
    serializer_class = RecipeSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Recipe.objects.filter(Q(user=user) | Q(is_public=True))
        category = self.request.query_params.get("category")
        search = self.request.query_params.get("search")
        max_time = self.request.query_params.get("max_time")
        if category:
            qs = qs.filter(category=category)
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(tags__icontains=search)
                | Q(ingredients__icontains=search)
            )
        if max_time:
            try:
                qs = qs.filter(cook_time__lte=int(max_time))
            except ValueError:
                pass
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RecipeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RecipeSerializer

    def get_queryset(self):
        user = self.request.user
        return Recipe.objects.filter(Q(user=user) | Q(is_public=True))


class MealLogListCreateView(generics.ListCreateAPIView):
    serializer_class = MealLogSerializer

    def get_queryset(self):
        from django.db.models import Case, When, Value, IntegerField

        qs = MealLog.objects.filter(user=self.request.user)
        date = self.request.query_params.get("date")
        meal_type = self.request.query_params.get("meal_type")
        if date:
            qs = qs.filter(date=date)
        if meal_type:
            qs = qs.filter(meal_type=meal_type)
        # 餐次顺序: 早餐 < 午餐 < 晚餐 < 宵夜
        order = Case(
            When(meal_type="breakfast", then=Value(0)),
            When(meal_type="lunch", then=Value(1)),
            When(meal_type="dinner", then=Value(2)),
            When(meal_type="snack", then=Value(3)),
            default=Value(9),
            output_field=IntegerField(),
        )
        return qs.order_by(order, "id")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MealLogDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MealLogSerializer

    def get_queryset(self):
        return MealLog.objects.filter(user=self.request.user)


class ShoppingItemListCreateView(generics.ListCreateAPIView):
    serializer_class = ShoppingItemSerializer

    def get_queryset(self):
        qs = ShoppingItem.objects.filter(user=self.request.user)
        purchased = self.request.query_params.get("purchased")
        if purchased is not None:
            qs = qs.filter(is_purchased=purchased == "true")
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ShoppingItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ShoppingItemSerializer

    def get_queryset(self):
        return ShoppingItem.objects.filter(user=self.request.user)


class FoodSuggestView(APIView):
    """根据用户偏好推荐菜谱"""

    def get(self, request):
        user = request.user
        preference = (
            getattr(user, "profile", None) and user.profile.diet_preference or ""
        )
        max_time = request.query_params.get("max_time", "60")

        qs = Recipe.objects.filter(Q(user=user) | Q(is_public=True))
        try:
            qs = qs.filter(cook_time__lte=int(max_time))
        except ValueError:
            pass

        # 根据偏好筛选
        if "素食" in preference:
            qs = qs.exclude(
                Q(ingredients__icontains="肉")
                | Q(ingredients__icontains="鱼")
                | Q(ingredients__icontains="虾")
            )
        elif "高蛋白" in preference:
            qs = qs.filter(
                Q(ingredients__icontains="鸡")
                | Q(ingredients__icontains="鱼")
                | Q(ingredients__icontains="蛋")
                | Q(ingredients__icontains="牛肉")
            )

        # 排除过敏食材
        allergy = getattr(user, "profile", None) and user.profile.allergy or ""
        if allergy:
            for item in allergy.split(","):
                item = item.strip()
                if item:
                    qs = qs.exclude(ingredients__icontains=item)

        recipes = qs.order_by("-is_public", "-created_at")[:10]
        return Response(
            {
                "preference": preference,
                "suggestions": RecipeSerializer(recipes, many=True).data,
            }
        )
