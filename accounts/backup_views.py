"""数据备份 - 导出/导入全部用户数据 (JSON)

导出: GET  /api/export/   -> 下载 JSON 文件
导入: POST /api/import/  -> body 为 JSON (Content-Type: application/json), 覆盖当前数据
"""
import json
from datetime import datetime, date, time
from decimal import Decimal

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from wardrobe.models import Clothing, OutfitLog
from food.models import Recipe, MealLog, ShoppingItem
from home.models import Expense, HouseTask, HomeInventory
from travel.models import Trip, TripEvent, CommuteLog, PackingItem
from .export_formats import FORMAT_MAP


def _model_data(model, user, via=None):
    """序列化模型实例为可恢复的 dict 列表（含关联字段名）

    via: 关联用户的字段路径，如 "trip__user"（用于 TripEvent/PackingItem）
    """
    rows = []
    if via:
        qs = model.objects.filter(**{via: user})
    else:
        qs = model.objects.filter(user=user)
    for obj in qs:
        d = {}
        for f in obj._meta.fields:
            name = f.name
            if name == "user":
                continue
            # 外键：存 id（如 trip -> trip_id），避免序列化成 __str__ 显示名
            if f.is_relation and f.many_to_one:
                val = getattr(obj, name + "_id")
            else:
                val = getattr(obj, name)
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            d[name] = val
        rows.append(d)
    return rows


def _collect(user, modules=None):
    """收集用户全部数据（modules: 指定模块列表，None=全部）"""
    all_data = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "username": user.username,
        "profile": _model_data(__import__("accounts.models", fromlist=["UserProfile"]).UserProfile, user),
        "clothes": _model_data(Clothing, user),
        "outfits": _model_data(OutfitLog, user),
        "recipes": _model_data(Recipe, user),
        "meals": _model_data(MealLog, user),
        "shopping": _model_data(ShoppingItem, user),
        "expenses": _model_data(Expense, user),
        "tasks": _model_data(HouseTask, user),
        "inventory": _model_data(HomeInventory, user),
        "trips": _model_data(Trip, user),
        "trip_events": _model_data(TripEvent, user, via="trip__user"),
        "commute": _model_data(CommuteLog, user),
        "packing": _model_data(PackingItem, user, via="trip__user"),
    }
    if modules is None:
        return all_data
    # 只保留勾选的模块（profile/version 始终保留）
    filtered = {"version": all_data["version"], "exported_at": all_data["exported_at"], "username": all_data["username"]}
    for m in modules:
        if m in all_data:
            filtered[m] = all_data[m]
    # 行程相关：选了 trips 才带 trip_events/packing
    if "trips" in modules:
        filtered["trip_events"] = all_data["trip_events"]
        filtered["packing"] = all_data["packing"]
    return filtered


class ExportDataView(APIView):
    """导出数据（支持 ?modules=a,b 选择模块 & ?filetype=json|csv|pdf|docx|jpg 选择格式）

    注意: 不能用 format 参数名（DRF 保留字，会被内容协商拦截）
    """

    def get(self, request):
        modules = request.query_params.get("modules")
        mod_list = modules.split(",") if modules else None
        fmt = request.query_params.get("filetype", "json").lower()
        if fmt not in FORMAT_MAP:
            return Response({"error": f"不支持的格式: {fmt}（支持: {', '.join(FORMAT_MAP.keys())}）"}, status=400)
        data = _collect(request.user, mod_list)
        content_type, ext, generator = FORMAT_MAP[fmt]
        payload = generator(data)
        filename = f"lifehub-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{ext}"
        resp = HttpResponse(payload, content_type=content_type)
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp


def _json_default(o):
    """JSON 序列化兜底：Decimal / date / time"""
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (date, time, datetime)):
        return o.isoformat()
    return str(o)


class ImportDataView(APIView):
    """从 JSON 恢复数据（覆盖当前用户的同名数据）"""

    def post(self, request):
        data = request.data
        if not isinstance(data, dict) or "version" not in data:
            return Response({"error": "无效的备份文件"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        # 先清空现有数据，再导入（覆盖语义）
        for model, uf in [
            (Clothing, "user"), (OutfitLog, "user"),
            (Recipe, "user"), (MealLog, "user"), (ShoppingItem, "user"),
            (Expense, "user"), (HouseTask, "user"), (HomeInventory, "user"),
            (Trip, "user"), (CommuteLog, "user"),
            (TripEvent, "trip__user"), (PackingItem, "trip__user"),
        ]:
            if uf == "user":
                model.objects.filter(user=user).delete()
            else:
                model.objects.filter(**{uf: user}).delete()

        counts = {}
        # (备份键, 模型, 关联用户的字段名或路径)
        import_specs = [
            ("clothes", Clothing, "user"), ("outfits", OutfitLog, "user"),
            ("recipes", Recipe, "user"), ("meals", MealLog, "user"),
            ("shopping", ShoppingItem, "user"), ("expenses", Expense, "user"),
            ("tasks", HouseTask, "user"), ("inventory", HomeInventory, "user"),
            ("trips", Trip, "user"), ("commute", CommuteLog, "user"),
            ("trip_events", TripEvent, "trip__user"),
            ("packing", PackingItem, "trip__user"),
        ]
        for key, model, user_field in import_specs:
            rows = data.get(key) or []
            for row in rows:
                d = dict(row)
                obj_id = d.pop("id", None)
                # 通过关联路径判断是否属于该用户
                if user_field.endswith("__user"):
                    trip_id = d.get("trip")
                    if trip_id is None or not Trip.objects.filter(id=trip_id, user=user).exists():
                        continue
                    obj = model()
                else:
                    obj = model(user=user)
                # 保留原始主键，保证外键关联不失效
                if obj_id is not None:
                    obj.id = obj_id
                # 用模型字段名列表判断（hasattr 对未设置的 FK 会因 RelatedObjectDoesNotExist 返回 False）
                field_names = {f.name for f in model._meta.fields}
                for k, v in d.items():
                    if k not in field_names:
                        continue
                    # 外键：赋 <field>_id（如 trip -> trip_id），避免 "must be a Trip instance"
                    f = model._meta.get_field(k)
                    if f.is_relation and f.many_to_one:
                        setattr(obj, k + "_id", v)
                    else:
                        setattr(obj, k, v)
                try:
                    obj.save()
                    counts[key] = counts.get(key, 0) + 1
                except Exception:
                    pass

        # 档案恢复
        profile_rows = data.get("profile") or []
        if profile_rows:
            from accounts.models import UserProfile
            p = getattr(user, "profile", None) or UserProfile.objects.create(user=user)
            pfields = {f.name for f in p._meta.fields}
            for k, v in profile_rows[0].items():
                if k not in ("id", "user") and k in pfields:
                    setattr(p, k, v)
            p.save()

        return Response({"ok": True, "imported": counts})
