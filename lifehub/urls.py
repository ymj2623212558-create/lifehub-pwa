"""LifeHub URL 配置"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from accounts.views import (
    RegisterView,
    UserProfileView,
    DashboardView,
    PasswordChangeView,
    WeatherView,
    WeatherCitiesView,
    WeatherSearchView,
    AIRecommendView,
)
from accounts.upload_views import ImageUploadView
from accounts.backup_views import ExportDataView, ImportDataView

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # 认证
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/password/", PasswordChangeView.as_view(), name="password_change"),
    path("api/profile/", UserProfileView.as_view(), name="profile"),
    path("api/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("api/weather/", WeatherView.as_view(), name="weather"),
    path("api/weather/search/", WeatherSearchView.as_view(), name="weather_search"),
    path("api/weather/cities/", WeatherCitiesView.as_view(), name="weather_cities"),
    path("api/ai/recommend/", AIRecommendView.as_view(), name="ai_recommend"),
    path("api/upload/", ImageUploadView.as_view(), name="image_upload"),
    path("api/export/", ExportDataView.as_view(), name="export"),
    path("api/import/", ImportDataView.as_view(), name="import"),
    # 衣
    path("api/wardrobe/", include("wardrobe.urls")),
    # 食
    path("api/food/", include("food.urls")),
    # 住
    path("api/home/", include("home.urls")),
    # 行
    path("api/travel/", include("travel.urls")),
    # 前端入口
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
]

# 开发环境：Django 内置静态文件和媒体文件服务
# 生产环境：WhiteNoise 处理 static，django.views.static 处理 media
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # 生产环境：显式服务 media 文件（当使用 Render disk 或本地存储时）
    from django.views.static import serve

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
