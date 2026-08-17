"""美食天下 (meishichina.com) 菜谱爬虫

抓取分类列表页 -> 菜谱详情页，提取: 菜名/分类/食材/步骤/难度/时间
输出 JSON 供 LifeHub 导入
用法: python crawl_meishichina.py [每类页数] [输出文件]
"""
import json
import re
import sys
import time
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE = "https://home.meishichina.com"

# 分类: (路径, 显示名, LifeHub分类)
CATEGORIES = [
    ("recipe/recai/", "热菜", "家常菜"),
    ("recipe/liangcai/", "凉菜", "凉菜"),
    ("recipe/zhushi/", "主食", "主食"),
    ("recipe/xiaochi/", "小吃", "小吃"),
    ("recipe/hongbei/", "烘焙", "甜品"),
    ("recipe/tanggeng/", "汤羹", "汤品"),
    ("recipe/kuaishoucai/", "快手菜", "家常菜"),
    ("recipe/zaocan/", "早餐", "家常菜"),
    ("recipe/xican/", "西餐", "家常菜"),
    ("recipe/dongji/", "冬季菜", "家常菜"),
    ("recipe/gaoyanzhi/", "高颜值", "家常菜"),
    ("recipe/jiangpaoyancai/", "酱泡腌菜", "凉菜"),
    ("recipe/zizhishicai/", "自制", "家常菜"),
]


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_ingredients(html):
    """解析主料/辅料 -> ['西葫芦', '胡萝卜']"""
    ings = []
    for m in re.finditer(
        r'<span class="category_s1">.*?<b>(.*?)</b>', html, re.S
    ):
        name = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if name and name not in ings:
            ings.append(name)
    # 兜底: 按行抓取 category_s1
    if not ings:
        for m in re.finditer(r'<b>([^<]{1,20})</b>', html):
            name = m.group(1).strip()
            if name and name not in ings and not any(
                k in name for k in ["做法", "菜谱", "美食"]
            ):
                ings.append(name)
            if len(ings) >= 20:
                break
    return ings


def parse_steps(html):
    """解析步骤: 优先 meta description（带编号），否则从页面提取"""
    # meta description 通常是 "1.xxx2.xxx..." 完整步骤
    md = re.search(r'<meta name="description" content="([^"]+)"', html)
    if md:
        desc = md.group(1)
        # 去掉开头菜名描述
        steps = re.findall(r"\d+\.([^0-9]+)", desc)
        steps = [s.strip() for s in steps if len(s.strip()) > 2]
        if len(steps) >= 2:
            return steps
    # 兜底: 页面 subtitle 区域
    steps = []
    for m in re.finditer(
        r'<div class="[^"]*subtitle[^"]*"[^>]*>(.*?)</div>', html, re.S
    ):
        s = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if s and len(s) > 2:
            steps.append(s)
    return steps


def parse_detail(url, category_label, lifehub_cat):
    html = fetch(url)
    title_m = re.search(r"<title>([^<]+?)的做法", html)
    title = title_m.group(1).strip() if title_m else None
    if not title:
        title_m = re.search(r"<title>([^<]+)</title>", html)
        if title_m:
            title = title_m.group(1).split("_")[0].strip()
    if not title:
        return None

    ings = parse_ingredients(html)
    steps = parse_steps(html)
    if not ings or not steps:
        return None

    # 难度/时间从关键词推断
    difficulty = 2
    if any(k in html for k in ["新手", "简单", "初级"]):
        difficulty = 1
    if any(k in html for k in ["高级", "困难", "大师"]):
        difficulty = 3
    cook_time = 20
    tm = re.search(r"约?(\d+)\s*(分钟|min)", html)
    if tm:
        cook_time = min(int(tm.group(1)), 240)

    return {
        "title": title,
        "category": lifehub_cat,
        "cuisine": "",
        "difficulty": difficulty,
        "cook_time": cook_time,
        "ingredients": "\n".join(ings),
        "steps": "\n".join(f"{i+1}.{s}" for i, s in enumerate(steps)),
        "source": f"美食天下 {category_label}",
        "is_public": True,
        "user": None,
    }


def crawl_category(path, label, lifehub_cat, pages):
    results = []
    for page in range(1, pages + 1):
        url = f"{BASE}/{path}" if page == 1 else f"{BASE}/{path}?page={page}"
        try:
            list_html = fetch(url)
        except Exception as e:
            print(f"  [跳过] 列表页{page}: {e}")
            continue
        links = re.findall(
            r'href="(https://home\.meishichina\.com/recipe-\d+\.html)"',
            list_html,
        )
        unique = list(dict.fromkeys(links))
        print(f"  {label} 第{page}页: {len(unique)} 个菜谱")
        for link in unique:
            try:
                rec = parse_detail(link, label, lifehub_cat)
                if rec:
                    results.append(rec)
                    print(f"    ✓ {rec['title']} ({len(rec['ingredients'].splitlines())}食材/{len(rec['steps'].splitlines())}步)")
                time.sleep(0.4)
            except Exception as e:
                print(f"    ✗ {link}: {str(e)[:50]}")
                time.sleep(1.0)
        time.sleep(0.8)
    return results


def main():
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    outfile = sys.argv[2] if len(sys.argv) > 2 else "meishichina_recipes.json"
    # 可选: 第3个参数 = 逗号分隔的分类路径子串过滤（如 "kuaishoucai,zaocan"）
    only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
    all_recs = []
    for path, label, cat in CATEGORIES:
        if only and not any(o in path for o in only):
            continue
        print(f"\n=== 分类: {label} ===")
        all_recs.extend(crawl_category(path, label, cat, pages))
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(all_recs, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 完成! 共 {len(all_recs)} 道菜谱 -> {outfile}")


if __name__ == "__main__":
    main()
