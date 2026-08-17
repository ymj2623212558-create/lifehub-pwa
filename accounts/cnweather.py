"""中国天气网 (weather.com.cn) - 国家气象局官方天气数据（免费免注册）

主天气通道：国内服务器，无需 VPN，无需 API Key
- 城市搜索: toy1.weather.com.cn/search?cityname=XX
- 实时天气: d1.weather.com.cn/sk_2d/{citycode}.html
- 7天预报:  www.weather.com.cn/weather/{citycode}.shtml

注意: 这些是网页内部接口（非正式开放 API），可能随时调整；
若失败由 WeatherView 自动切换到 Open-Meteo 备用通道。
"""
import json
import re
import urllib.request
import urllib.parse

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "http://www.weather.com.cn/",
}

# 天气描述 -> emoji（与 Open-Meteo 风格统一）
WEATHER_EMOJI = {
    "晴": "☀️",
    "多云": "⛅",
    "少云": "🌤️",
    "阴": "☁️",
    "阴天": "☁️",
    "雾": "🌫️",
    "霾": "🌫️",
    "扬沙": "🌫️",
    "浮尘": "🌫️",
    "沙尘暴": "🌫️",
    "小雨": "🌧️",
    "中雨": "🌧️",
    "大雨": "🌧️",
    "暴雨": "⛈️",
    "大暴雨": "⛈️",
    "特大暴雨": "⛈️",
    "阵雨": "🌦️",
    "雷阵雨": "⛈️",
    "雷阵雨伴有冰雹": "⛈️",
    "雨夹雪": "🌧️",
    "冻雨": "🌧️",
    "毛毛雨": "🌦️",
    "小雪": "🌨️",
    "中雪": "🌨️",
    "大雪": "❄️",
    "暴雪": "❄️",
    "阵雪": "🌨️",
}


def _emoji(desc):
    # 优先匹配更具体的天气词（雷阵雨/暴雨优先于多云）
    for kw in ["雷阵雨伴有冰雹", "雷阵雨", "暴雨", "大雪", "暴雪", "小雪", "中雨", "大雨", "小雨",
               "阵雨", "雨夹雪", "冻雨", "毛毛雨", "中雪", "晴", "多云", "少云", "阴", "雾", "霾"]:
        if kw in desc:
            return WEATHER_EMOJI.get(kw, "🌡️")
    return "🌡️"


def _fetch(url):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.read().decode("utf-8", "ignore")


def geocode(city):
    """城市名 -> 城市编码 (如 北京 -> 101010100)；失败返回 None"""
    if not city:
        return None
    try:
        url = f"https://toy1.weather.com.cn/search?cityname={urllib.parse.quote(city)}"
        data = _fetch(url)
        # 返回格式: ([{"ref":"101010100~beijing~北京~Beijing~北京~Beijing~10~..."},...])
        m = re.search(r'\{?"?ref"?\s*[:=]\s*"(\d+)~', data)
        if m:
            return m.group(1)
        return None
    except Exception:
        return None


def search_city(q):
    """城市搜索 -> [{name, admin1, country}]；失败返回 None"""
    if not q:
        return None
    try:
        url = f"https://toy1.weather.com.cn/search?cityname={urllib.parse.quote(q)}"
        data = _fetch(url)
        # 提取所有 ref 条目: 编码~拼音~中文名~英文名~中文名~英文名~...~省份
        items = re.findall(r'"ref":"(\d+)~([^~]*)~([^~]*)~[^~]*~([^~]*)~[^~]*~[^~]*~[^~]*~[^~]*~([^"]*)"', data)
        results = []
        for code, pinyin, name, name2, admin1 in items:
            # 过滤景点类（编码含字母 A/B 等）
            if re.search(r"[A-Za-z]", code):
                continue
            results.append({
                "name": name or name2 or q,
                "code": code,
                "lat": 0,
                "lon": 0,
                "admin1": admin1 or "",
                "country": "中国",
            })
        return results if results else None
    except Exception:
        return None


def fetch_weather(city, with_hourly=False):
    """获取实时 + 未来7天天气；失败返回 None"""
    try:
        code = geocode(city)
        if not code:
            return None

        # 实时天气
        sk = _fetch(f"http://d1.weather.com.cn/sk_2d/{code}.html")
        m = re.search(r"var dataSK=(\{.*\})", sk, re.S)
        if not m:
            return None
        sk_data = json.loads(m.group(1))
        desc = sk_data.get("weather", "") or ""
        cur = {
            "temp": float(sk_data.get("temp", 0)) if sk_data.get("temp") else None,
            "feels_like": None,
            "humidity": int(re.sub(r"\D", "", sk_data.get("SD", "0") or "0")) if sk_data.get("SD") else None,
            "wind": sk_data.get("wse", ""),
            "desc": desc,
            "icon": _emoji(desc),
        }

        # 7天预报
        page = _fetch(f"http://www.weather.com.cn/weather/{code}.shtml")
        days = []
        m2 = re.search(r'<ul class="t clearfix">(.*?)</ul>', page, re.S)
        if m2:
            lis = re.findall(r"<li.*?</li>", m2.group(1), re.S)
            for li in lis:
                hm = re.search(r"<h1>([^<]+)</h1>", li)
                wm = re.search(r'class="wea">([^<]+)</p>', li)
                # 温度: 今天<li>只有 <i>23℃</i>(低温)，其他天有 <i>23℃</i>..<span>32℃</span> 或 <b>..</b><span>..</span>
                tems = re.findall(r"<i>([^<]+)</i>", li) + re.findall(r"<span>([^<]+)</span>", li)
                temps = [t.replace("℃", "").strip() for t in tems if "℃" in t]
                # 也尝试 <b>23℃</b><span>30℃</span> 结构
                if len(temps) < 2:
                    temps2 = re.findall(r"<b>([^<]+)</b>", li)
                    temps = [t.replace("℃", "").strip() for t in temps2 if "℃" in t] + temps
                if not hm:
                    continue
                wdesc = wm.group(1).strip() if wm else ""
                # 解析日期: 17日（今天）-> 用索引补全
                tmin = None
                tmax = None
                if len(temps) >= 2:
                    tmin, tmax = float(temps[0]), float(temps[1])
                elif len(temps) == 1:
                    tmin = float(temps[0])
                days.append(
                    {
                        "date": "",
                        "desc": wdesc,
                        "icon": _emoji(wdesc),
                        "tmax": tmax,
                        "tmin": tmin,
                        "rain_prob": None,
                    }
                )

        # 补全日期（今天 + 未来6天）
        from datetime import date, timedelta

        today = date.today()
        for i, d in enumerate(days):
            d["date"] = (today + timedelta(days=i)).isoformat()

        result = {
            "city": city,
            "current": cur,
            "daily": days,
        }
        if with_hourly:
            result["hourly"] = []  # 中国天气网逐小时接口不稳定，留空由前端降级
        return result
    except Exception:
        return None
