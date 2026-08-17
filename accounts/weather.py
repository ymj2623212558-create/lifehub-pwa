"""天气服务 - 基于 Open-Meteo 免费 API（无需 key）

- 城市 -> 经纬度: geocoding-api.open-meteo.com
- 实时天气 + 未来7天预报: api.open-meteo.com
"""
import urllib.request
import urllib.parse
import json

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO 天气代码 -> (中文描述, emoji)
WEATHER_CODES = {
    0: ("晴", "☀️"),
    1: ("多云", "⛅"),
    2: ("阴", "☁️"),
    3: ("阴天", "🌥️"),
    45: ("雾", "🌫️"),
    48: ("雾凇", "🌫️"),
    51: ("毛毛雨", "🌦️"),
    53: ("毛毛雨", "🌦️"),
    55: ("毛毛雨", "🌦️"),
    56: ("冻雨", "🌧️"),
    57: ("冻雨", "🌧️"),
    61: ("小雨", "🌧️"),
    63: ("中雨", "🌧️"),
    65: ("大雨", "🌧️"),
    66: ("冻雨", "🌧️"),
    67: ("冻雨", "🌧️"),
    71: ("小雪", "🌨️"),
    73: ("中雪", "🌨️"),
    75: ("大雪", "❄️"),
    77: ("雪粒", "❄️"),
    80: ("阵雨", "🌦️"),
    81: ("阵雨", "🌧️"),
    82: ("强阵雨", "⛈️"),
    85: ("阵雪", "🌨️"),
    86: ("强阵雪", "❄️"),
    95: ("雷雨", "⛈️"),
    96: ("雷雨伴冰雹", "⛈️"),
    99: ("雷雨伴冰雹", "⛈️"),
}


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "LifeHub/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def geocode(city):
    """城市名 -> (lat, lon)；失败返回 None"""
    if not city:
        return None
    try:
        url = f"{GEOCODE_URL}?name={urllib.parse.quote(city)}&count=1&language=zh"
        data = _fetch_json(url)
        results = data.get("results") or []
        if not results:
            return None
        return results[0]["latitude"], results[0]["longitude"]
    except Exception:
        return None


def fetch_weather(city, with_hourly=False):
    """获取城市实时天气 + 7 天预报（可选逐小时）"""
    loc = geocode(city)
    if not loc:
        return None
    lat, lon = loc
    try:
        url = (
            f"{FORECAST_URL}?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
            "weather_code,wind_speed_10m"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
            "sunrise,sunset,precipitation_probability_max"
            "&forecast_days=7&timezone=auto"
        )
        if with_hourly:
            url += "&hourly=temperature_2m,weather_code,precipitation_probability,relative_humidity_2m"
        data = _fetch_json(url)
        current = data.get("current", {})
        daily = data.get("daily", {})
        code = current.get("weather_code", 0)
        desc, icon = WEATHER_CODES.get(code, ("未知", "🌡️"))

        days = []
        dates = daily.get("time", [])
        for i, d in enumerate(dates):
            dcode = (daily.get("weather_code") or [0] * 7)[i]
            ddesc, dicon = WEATHER_CODES.get(dcode, ("未知", "🌡️"))
            days.append(
                {
                    "date": d,
                    "code": dcode,
                    "desc": ddesc,
                    "icon": dicon,
                    "tmax": (daily.get("temperature_2m_max") or [None] * 7)[i],
                    "tmin": (daily.get("temperature_2m_min") or [None] * 7)[i],
                    "rain_prob": (daily.get("precipitation_probability_max") or [None] * 7)[i],
                }
            )

        result = {
            "city": city,
            "current": {
                "temp": current.get("temperature_2m"),
                "feels_like": current.get("apparent_temperature"),
                "humidity": current.get("relative_humidity_2m"),
                "wind": current.get("wind_speed_10m"),
                "code": code,
                "desc": desc,
                "icon": icon,
            },
            "daily": days,
        }

        # 逐小时预报（未来 24 小时，每 3 小时一条）
        if with_hourly:
            h = data.get("hourly", {})
            htimes = h.get("time", [])
            htemps = h.get("temperature_2m", [])
            hcodes = h.get("weather_code", [])
            hrains = h.get("precipitation_probability", [])
            hhums = h.get("relative_humidity_2m", [])
            hourly = []
            for i, t in enumerate(htimes):
                if i % 3 != 0:
                    continue
                if len(hourly) >= 24:
                    break
                hcode = hcodes[i] if i < len(hcodes) else 0
                hdesc, hicon = WEATHER_CODES.get(hcode, ("未知", "🌡️"))
                hourly.append(
                    {
                        "time": t[11:16],  # "HH:MM"
                        "date": t[:10],
                        "temp": htemps[i] if i < len(htemps) else None,
                        "code": hcode,
                        "desc": hdesc,
                        "icon": hicon,
                        "rain_prob": hrains[i] if i < len(hrains) else None,
                        "humidity": hhums[i] if i < len(hhums) else None,
                    }
                )
            result["hourly"] = hourly

        return result
    except Exception:
        return None
