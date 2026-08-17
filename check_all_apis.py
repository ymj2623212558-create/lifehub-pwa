"""批量验证 LifeHub 前端所有功能对应的 API 端点"""
import json
import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:8002"


def post(url, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url, data=json.dumps(data).encode() if data is not None else None, headers=headers
    )
    return urllib.request.urlopen(req)


def get(url, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req)


# 登录
tok = json.loads(post(f"{BASE}/api/auth/login/", {"username": "demo", "password": "demo123456"}).read())["access"]
results = []


def test(name, fn):
    try:
        resp = fn()
        results.append((name, resp.status, "OK"))
    except Exception as e:
        results.append((name, getattr(e, "code", "ERR"), str(e)[:80]))


# 衣
test("衣-衣物列表", lambda: get(f"{BASE}/api/wardrobe/clothes/", tok))
test("衣-穿搭日记", lambda: get(f"{BASE}/api/wardrobe/outfits/", tok))
test("衣-穿搭推荐", lambda: get(f"{BASE}/api/wardrobe/suggest/", tok))
test("衣-创建衣物", lambda: post(f"{BASE}/api/wardrobe/clothes/", {"name": "测试衬衫", "category": "top", "color": "白", "season": "spring"}, tok))
test("衣-创建穿搭", lambda: post(f"{BASE}/api/wardrobe/outfits/", {"date": "2026-08-17", "clothes_ids": [], "occasion": "work", "note": "测试"}, tok))

# 食
test("食-菜谱库", lambda: get(f"{BASE}/api/food/recipes/", tok))
test("食-菜谱搜索(红烧肉)", lambda: get(f"{BASE}/api/food/recipes/?search=" + urllib.parse.quote("红烧肉"), tok))
test("食-菜谱分类筛选", lambda: get(f"{BASE}/api/food/recipes/?category=" + urllib.parse.quote("汤品"), tok))
test("食-用时筛选", lambda: get(f"{BASE}/api/food/recipes/?max_time=30", tok))
test("食-每日餐食", lambda: get(f"{BASE}/api/food/meals/", tok))
test("食-购物清单", lambda: get(f"{BASE}/api/food/shopping/", tok))
test("食-推荐", lambda: get(f"{BASE}/api/food/suggest/", tok))
test("食-创建菜谱", lambda: post(f"{BASE}/api/food/recipes/", {"title": "测试菜", "category": "家常菜", "difficulty": 1, "cook_time": 10, "ingredients": "测试", "steps": "1.测试"}, tok))
test("食-记录餐食", lambda: post(f"{BASE}/api/food/meals/", {"date": "2026-08-17", "meal_type": "lunch"}, tok))
test("食-添加购物项", lambda: post(f"{BASE}/api/food/shopping/", {"name": "测试物品", "quantity": 1}, tok))

# 住
test("住-记账", lambda: get(f"{BASE}/api/home/expenses/", tok))
test("住-记账统计", lambda: get(f"{BASE}/api/home/expenses/summary/", tok))
test("住-家务待办", lambda: get(f"{BASE}/api/home/tasks/", tok))
test("住-库存", lambda: get(f"{BASE}/api/home/inventory/", tok))
test("住-创建记账", lambda: post(f"{BASE}/api/home/expenses/", {"title": "测试支出", "amount": 10, "category": "food", "date": "2026-08-17"}, tok))
test("住-创建待办", lambda: post(f"{BASE}/api/home/tasks/", {"title": "测试待办", "due_date": "2026-08-20"}, tok))
test("住-创建库存", lambda: post(f"{BASE}/api/home/inventory/", {"name": "测试库存", "category": "清洁", "quantity": 5}, tok))

# 行
test("行-行程列表", lambda: get(f"{BASE}/api/travel/trips/", tok))
test("行-通勤记录", lambda: get(f"{BASE}/api/travel/commute/", tok))
test("行-通勤统计", lambda: get(f"{BASE}/api/travel/commute/summary/", tok))
test("行-创建行程", lambda: post(f"{BASE}/api/travel/trips/", {"title": "测试行程", "destination": "广州", "start_date": "2026-09-01", "end_date": "2026-09-03", "status": "planned"}, tok))
test("行-创建通勤", lambda: post(f"{BASE}/api/travel/commute/", {"date": "2026-08-17", "mode": "subway", "cost": 5}, tok))

# 其他
test("首页-Dashboard", lambda: get(f"{BASE}/api/dashboard/", tok))
test("天气-实时", lambda: get(f"{BASE}/api/weather/?city=" + urllib.parse.quote("北京"), tok))
test("天气-城市搜索", lambda: get(f"{BASE}/api/weather/search/?q=" + urllib.parse.quote("苏州"), tok))
test("天气-城市列表", lambda: get(f"{BASE}/api/weather/cities/", tok))
test("我的-档案", lambda: get(f"{BASE}/api/profile/", tok))
test("我的-导出JSON", lambda: get(f"{BASE}/api/export/?filetype=json", tok))
test("我的-导出PDF", lambda: get(f"{BASE}/api/export/?filetype=pdf", tok))
test("我的-导出Word", lambda: get(f"{BASE}/api/export/?filetype=docx", tok))
test("我的-导出JPG", lambda: get(f"{BASE}/api/export/?filetype=jpg", tok))
test("我的-改密", lambda: post(f"{BASE}/api/auth/password/", {"new_password": "demo123456"}, tok))

# 汇总
print(f"{'端点':<28}{'状态':<6}{'结果'}")
print("-" * 70)
fails = []
for name, status, note in results:
    mark = "✅" if status == 200 or status == 201 else "❌"
    print(f"{mark} {name:<26}{status:<6}{note}")
    if status not in (200, 201):
        fails.append(name)
print("-" * 70)
print(f"通过 {len(results) - len(fails)}/{len(results)}")
if fails:
    print("失败项:", fails)
