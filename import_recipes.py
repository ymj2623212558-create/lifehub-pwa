"""导入爬取的菜谱到 LifeHub 数据库

用法: python import_recipes.py <json文件> [用户名]
菜谱设为公开，所有用户可见；同时关联到指定用户(可选)
"""
import json
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lifehub.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django

django.setup()

from django.contrib.auth.models import User
from food.models import Recipe


def main():
    infile = sys.argv[1] if len(sys.argv) > 1 else "data/recipes.json"
    username = sys.argv[2] if len(sys.argv) > 2 else None
    with open(infile, encoding="utf-8") as f:
        recs = json.load(f)

    user = User.objects.filter(username=username).first() if username else None
    existing = set(Recipe.objects.values_list("title", flat=True))

    added = 0
    skipped = 0
    for r in recs:
        title = r["title"]
        if title in existing:
            skipped += 1
            continue
        Recipe.objects.create(
            user=user,
            title=title,
            category=r.get("category", "家常菜"),
            cuisine=r.get("cuisine", ""),
            difficulty=r.get("difficulty", 2),
            cook_time=max(r.get("cook_time", 20) or 20, 10),  # 至少10分钟，避免异常小值
            ingredients=r.get("ingredients", ""),
            steps=r.get("steps", ""),
            is_public=True,
        )
        existing.add(title)
        added += 1

    print(f"✅ 导入完成: 新增 {added} 道, 跳过重复 {skipped} 道")
    print(f"   当前菜谱总数: {Recipe.objects.count()}")


if __name__ == "__main__":
    main()
