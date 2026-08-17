"""生成一周每日餐食计划（从菜谱库挑选）

策略:
- 早餐: 主食/汤品 (粥面馒头类)
- 午餐: 家常菜(荤) + 家常菜(素) + 汤品
- 晚餐: 家常菜 + 凉菜 + 主食
- 宵夜: 甜品/小吃

用法: python seed_weekly_meals.py [用户名] [起始日期]
"""
import os
import random
import sys
from datetime import date, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lifehub.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django

django.setup()

from django.contrib.auth.models import User
from food.models import Recipe, MealLog


def pick(qs, n):
    """随机挑 n 道不重复"""
    ids = list(qs.values_list("id", flat=True))
    random.shuffle(ids)
    return [Recipe.objects.get(id=i) for i in ids[:n]]


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "demo"
    start = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    user = User.objects.get(username=username)

    MealLog.objects.filter(user=user).delete()  # 先清空旧的

    # 分类候选池
    breakfast_pool = Recipe.objects.filter(
        user=user, category__in=["主食", "汤品"], is_public=True
    ).distinct()
    if breakfast_pool.count() < 10:
        breakfast_pool = Recipe.objects.filter(category__in=["主食", "汤品"], is_public=True)
    lunch_main = Recipe.objects.filter(category="家常菜", is_public=True)
    lunch_soup = Recipe.objects.filter(category="汤品", is_public=True)
    dinner_main = Recipe.objects.filter(category="家常菜", is_public=True)
    dinner_cold = Recipe.objects.filter(category="凉菜", is_public=True)
    dinner_staple = Recipe.objects.filter(category="主食", is_public=True)
    snack_pool = Recipe.objects.filter(category__in=["甜品", "小吃"], is_public=True)

    created = 0
    for i in range(7):
        d = start + timedelta(days=i)
        # 早餐: 1-2 道
        bf = pick(breakfast_pool, 2)
        for r in bf:
            MealLog.objects.create(user=user, date=d, meal_type="breakfast", recipe=r)
            created += 1
        # 午餐: 主荤 + 素 + 汤
        lm = pick(lunch_main, 2)
        ls = pick(lunch_soup, 1)
        for r in lm + ls:
            MealLog.objects.create(user=user, date=d, meal_type="lunch", recipe=r)
            created += 1
        # 晚餐: 主 + 凉 + 主食
        dm = pick(dinner_main, 1)
        dc = pick(dinner_cold, 1)
        ds = pick(dinner_staple, 1)
        for r in dm + dc + ds:
            MealLog.objects.create(user=user, date=d, meal_type="dinner", recipe=r)
            created += 1
        # 宵夜: 甜品/小吃
        sn = pick(snack_pool, 1)
        for r in sn:
            MealLog.objects.create(user=user, date=d, meal_type="snack", recipe=r)
            created += 1
        print(f"  {d} ({'一二三四五六日'[d.weekday()]}) 早{len(bf)} 午{len(lm)+len(ls)} 晚{len(dm)+len(dc)+len(ds)} 加{len(sn)}")

    print(f"\n✅ 一周餐食计划生成完成: 共 {created} 条记录 ({start} ~ {start + timedelta(days=6)})")


if __name__ == "__main__":
    main()
