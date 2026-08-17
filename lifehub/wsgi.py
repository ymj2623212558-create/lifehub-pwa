"""
WSGI config for lifehub project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lifehub.settings')

# 生产环境首次启动自初始化:
# 平台(PocketBay/Railway 等)不会自动执行 migrate/seed,
# 这里在 WSGI 加载时检测并完成: 建表 -> 建 demo 账号 -> 导入菜谱库
# 仅在数据缺失时执行, 之后启动直接跳过, 不阻塞正常请求。
_initialized = False


def _bootstrap():
    global _initialized
    if _initialized:
        return
    _initialized = True
    try:
        import django

        django.setup()

        from django.conf import settings

        if settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
            # 0. 确保数据库目录存在
            db_path = settings.DATABASES["default"]["NAME"]
            if db_path:
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
            # 1. 建表: migrate 幂等, 每次启动执行安全(已迁移自动跳过)
            from django.core.management import call_command

            call_command("migrate", "--noinput", verbosity=0)
            # 2. 建 demo 账号 + 示例数据 (不存在才建)
            from django.contrib.auth.models import User

            if not User.objects.filter(username="demo").exists():
                call_command("seed_data", verbosity=0)
            # 3. 导入菜谱库 (若存在且未导入完整库)
            import json

            recipes_file = os.path.join(settings.BASE_DIR, "data", "recipes.json")
            if os.path.exists(recipes_file):
                from food.models import Recipe

                if Recipe.objects.count() < 100:
                    with open(recipes_file, encoding="utf-8") as f:
                        recs = json.load(f)
                    for r in recs:
                        Recipe.objects.create(
                            user=None,
                            title=r.get("title", ""),
                            category=r.get("category", "家常菜"),
                            cuisine=r.get("cuisine", ""),
                            difficulty=r.get("difficulty", 1),
                            cook_time=r.get("cook_time", 30),
                            servings=r.get("servings", ""),
                            ingredients=r.get("ingredients", ""),
                            steps=r.get("steps", ""),
                            is_public=True,
                        )
    except Exception as e:
        # 初始化失败不阻塞启动, 应用仍可加载(登录会报错但可排查)
        sys.stderr.write(f"[lifehub bootstrap] WARN: {e}\n")


_bootstrap()

application = get_wsgi_application()
