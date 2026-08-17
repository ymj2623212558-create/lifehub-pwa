"""food urls"""

from django.urls import path
from .views import (
    RecipeListCreateView,
    RecipeDetailView,
    MealLogListCreateView,
    MealLogDetailView,
    ShoppingItemListCreateView,
    ShoppingItemDetailView,
    FoodSuggestView,
)
from .meal_plan_views import MealPlanView, MealPlanGenerateView

urlpatterns = [
    path("recipes/", RecipeListCreateView.as_view(), name="recipe-list"),
    path("recipes/<int:pk>/", RecipeDetailView.as_view(), name="recipe-detail"),
    path("meals/", MealLogListCreateView.as_view(), name="meal-list"),
    path("meals/<int:pk>/", MealLogDetailView.as_view(), name="meal-detail"),
    path(
        "meal-plan/", MealPlanView.as_view(), name="meal-plan"
    ),
    path(
        "meal-plan/generate/",
        MealPlanGenerateView.as_view(),
        name="meal-plan-generate",
    ),
    path("shopping/", ShoppingItemListCreateView.as_view(), name="shopping-list"),
    path(
        "shopping/<int:pk>/",
        ShoppingItemDetailView.as_view(),
        name="shopping-detail",
    ),
    path("suggest/", FoodSuggestView.as_view(), name="food-suggest"),
]
