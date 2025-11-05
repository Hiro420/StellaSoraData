# -*- coding: utf-8 -*-
"""
キャラクターデータを詳細に収集するスクリプト（BriefDesc除外／Word参照はUI任せ）

要点:
- スキルの Texts は Title / Desc のみ（BriefDesc は取得しない）。
- スキル文中の「##ラベル#ID#」は置換せずそのまま残す。UI 側でクリック→モーダル表示。
- JSON の "WordRefs" に、スキル文で使われた Word の色と Param 置換済み本文（%は付けない）を収集。
- Param 解析（HitDamage全レベル、Effect/OnceAdd…のLevelUp等）は従来通り。
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Set

# -----------------------------------------
# 基本設定
# -----------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
TARGET_CHARACTER_ID = 144
_JSON_CACHE: Dict[Path, Any] = {}
HITDAMAGE_TO_SKILLS: Dict[str, Set[int]] = {}

# -----------------------------------------
# JSON ローダ（キャッシュ）
# -----------------------------------------


def load_json(path: Path) -> Any:
    if path not in _JSON_CACHE:
        with path.open(encoding="utf-8") as f:
            _JSON_CACHE[path] = json.load(f)
    return _JSON_CACHE[path]


# -----------------------------------------
# 各種データのロード
# -----------------------------------------
CHARACTER_DATA = load_json(BASE_DIR / "JP" / "bin" / "Character.json")
CHARACTER_LANG = load_json(
    BASE_DIR / "JP" / "language" / "ja_JP" / "Character.json")

SKILL_DATA = load_json(BASE_DIR / "JP" / "bin" / "Skill.json")
SKILL_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Skill.json")
SKILL_UPGRADE_DATA = load_json(
    BASE_DIR / "JP" / "bin" / "CharacterSkillUpgrade.json")

HIT_DAMAGE_DATA = load_json(BASE_DIR / "JP" / "bin" / "HitDamage.json")

BUFF_VALUE_DATA = load_json(BASE_DIR / "JP" / "bin" / "BuffValue.json")
EFFECT_VALUE_DATA = load_json(BASE_DIR / "JP" / "bin" / "EffectValue.json")
EFFECT_DATA = load_json(BASE_DIR / "JP" / "bin" / "Effect.json")

ATTRIBUTE_DATA = load_json(BASE_DIR / "JP" / "bin" / "Attribute.json")
UITEXT_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "UIText.json")

CHARACTER_TAG_DATA = load_json(BASE_DIR / "JP" / "bin" / "CharacterTag.json")
CHARACTER_TAG_LANG = load_json(
    BASE_DIR / "JP" / "language" / "ja_JP" / "CharacterTag.json")
CHAR_DES_DATA = load_json(BASE_DIR / "JP" / "bin" / "CharacterDes.json")

TALENT_GROUP_DATA = load_json(BASE_DIR / "JP" / "bin" / "TalentGroup.json")
TALENT_GROUP_LANG = load_json(
    BASE_DIR / "JP" / "language" / "ja_JP" / "TalentGroup.json")
TALENT_DATA = load_json(BASE_DIR / "JP" / "bin" / "Talent.json")
TALENT_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Talent.json")

CHAR_POTENTIAL_DATA = load_json(BASE_DIR / "JP" / "bin" / "CharPotential.json")
POTENTIAL_DATA = load_json(BASE_DIR / "JP" / "bin" / "Potential.json")
POTENTIAL_LANG = load_json(
    BASE_DIR / "JP" / "language" / "ja_JP" / "Potential.json")

ONCE_ADD_ATTR_VALUE_DATA = load_json(
    BASE_DIR / "JP" / "bin" / "OnceAdditionalAttributeValue.json")
ONCE_ADD_ATTR_DATA = load_json(
    BASE_DIR / "JP" / "bin" / "OnceAdditionalAttribute.json")

ENUM_DESC_DATA = load_json(BASE_DIR / "JP" / "bin" / "EnumDesc.json")

ITEM_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Item.json")

WORD_DATA = load_json(BASE_DIR / "JP" / "bin" / "Word.json")
WORD_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Word.json")

# -----------------------------------------
# Enum -> 日本語
# -----------------------------------------


def resolve_enum_text(enum_name: str, raw_value: Any) -> Optional[str]:
    try:
        value_int = int(raw_value)
    except (TypeError, ValueError):
        return None
    for entry in ENUM_DESC_DATA.values():
        if entry.get("EnumName") == enum_name and entry.get("Value") == value_int:
            key = entry.get("Key")
            if key:
                return UITEXT_LANG.get(f"UIText.{key}.1")
    return None

# -----------------------------------------
# LevelUp の行を末尾規則で集める
# -----------------------------------------


def build_level_entries(base_id: Any, dataset: Dict[str, Any], max_level: Optional[int] = None) -> List[Tuple[int, Dict[str, Any]]]:
    s = str(base_id)
    if len(s) < 3:
        return []
    prefix, suffix = s[:-2], s[-1]
    out: List[Tuple[int, Dict[str, Any]]] = []
    level = 1
    while True:
        level_id = f"{prefix}{level}{suffix}"
        row = dataset.get(level_id)
        if row is None:
            break
        out.append((level, row))
        level += 1
        if max_level is not None and level > max_level:
            break
    return out

# -----------------------------------------
# 数値変換（UIで%付与判断するため生値も保持）
# -----------------------------------------


def apply_numeric_transform(raw_value: Any, transform: Optional[str]) -> Dict[str, Any]:
    converted: Optional[float] = None
    try:
        if transform == "10K":
            converted = float(raw_value) / 10000
        elif transform == "HdPct":
            converted = float(raw_value) * 100
        elif transform == "10KHdPct":
            converted = float(raw_value) / 100
        elif transform in {"Fixed", None}:
            converted = float(raw_value)
    except (TypeError, ValueError):
        converted = None
    return {"Raw": raw_value, "Converted": converted, "Transform": transform}

# -----------------------------------------
# HitDamage 逆引き（LevelData が無い場合の推定に利用）
# -----------------------------------------


def _build_hitdamage_reverse_index() -> None:
    for sid_str, skill in SKILL_DATA.items():
        try:
            sid = int(sid_str)
        except Exception:
            continue
        for i in range(1, 16):
            v = skill.get(f"Param{i}")
            if isinstance(v, str) and v.startswith("HitDamage,DamageNum,"):
                parts = v.split(",")
                if len(parts) >= 3:
                    hd_id = parts[2]
                    HITDAMAGE_TO_SKILLS.setdefault(hd_id, set()).add(sid)


_build_hitdamage_reverse_index()


def _infer_bind_skill_for_hitdamage(identifier: str, values_count: int):
    candidates = sorted(HITDAMAGE_TO_SKILLS.get(identifier, set()))
    if not candidates:
        return (None, [], "NoLevelData_NoReverseRef")
    if len(candidates) == 1:
        return (candidates[0], candidates, "ReverseRef_Single")
    matched = [sid for sid in candidates if (
        SKILL_DATA.get(str(sid), {}).get("MaxLevel") == values_count)]
    if len(matched) == 1:
        return (matched[0], candidates, "ReverseRef_LengthMatch")
    return (candidates[0], candidates, "ReverseRef_Ambiguous_TakeFirst")

# -----------------------------------------
# Param 解析
# -----------------------------------------


def resolve_param(param_str: str, context_max_level: Optional[int] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "Source": param_str,
        "Table": None,
        "Mode": None,
        "Resolved": None,
        "FrameCount": None,
        "DurationSeconds": None,
        "RecastSeconds": None,
    }
    if not param_str:
        return result
    parts = param_str.split(",")
    if len(parts) < 3:
        return result
    table, mode, identifier = parts[0], parts[1], parts[2]
    result["Table"] = table
    result["Mode"] = mode

    # HitDamage（全レベル）
    if table == "HitDamage" and mode == "DamageNum":
        entry = HIT_DAMAGE_DATA.get(identifier)
        if entry:
            raw_list = entry.get("SkillPercentAmend", [])
            if isinstance(raw_list, list):
                values = []
                for idx, raw in enumerate(raw_list, start=1):
                    try:
                        conv = float(raw) / 10000
                    except (TypeError, ValueError):
                        conv = None
                    values.append(
                        {"Level": idx, "Raw": raw, "Converted": conv})

                level_type_val = entry.get("levelTypeData") or entry.get(
                    "LevelTypeData") or entry.get("LevelType")
                level_type_text = resolve_enum_text(
                    "ELT", level_type_val) if level_type_val is not None else None
                explicit_level_data = entry.get(
                    "LevelData") or entry.get("LevelId")
                bound_skill = None
                bound_skill_name = None
                method = "ExplicitLevelData" if explicit_level_data is not None else None
                candidates: List[int] = []

                if explicit_level_data is not None:
                    bd = SKILL_DATA.get(str(explicit_level_data))
                    if bd:
                        bound_skill = bd
                        bound_skill_name = SKILL_LANG.get(
                            f"Skill.{explicit_level_data}.1")
                    else:
                        sid, candidates, method = _infer_bind_skill_for_hitdamage(
                            identifier, len(raw_list))
                        if sid is not None:
                            bound_skill = SKILL_DATA.get(str(sid))
                            bound_skill_name = SKILL_LANG.get(f"Skill.{sid}.1")
                            explicit_level_data = sid
                            method = f"{method}_FallbackFromExplicitNonSkill"
                else:
                    sid, candidates, method = _infer_bind_skill_for_hitdamage(
                        identifier, len(raw_list))
                    if sid is not None:
                        bound_skill = SKILL_DATA.get(str(sid))
                        bound_skill_name = SKILL_LANG.get(f"Skill.{sid}.1")
                        explicit_level_data = sid

                result["Resolved"] = {
                    "Field": "SkillPercentAmend",
                    "Values": values,
                    "Bind": {
                        "LevelTypeRaw": level_type_val,
                        "LevelTypeText": level_type_text,
                        "LevelData": explicit_level_data,
                        "SkillName": bound_skill_name,
                        "SkillMaxLevel": bound_skill.get("MaxLevel") if bound_skill else None,
                        "Candidates": candidates,
                        "Method": method or "NoBindInfo",
                        "ValueCount": len(raw_list),
                    }
                }
        return result

    # BuffValue（NoLevel）
    if table == "BuffValue":
        entry = BUFF_VALUE_DATA.get(identifier)
        if entry:
            fields = []
            i = 3
            while i < len(parts):
                field = parts[i]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if i + 1 < len(parts):
                    nxt = parts[i + 1]
                    if nxt == "Enum":
                        transform_token = "Enum"
                        if i + 2 < len(parts):
                            transform_arg = parts[i + 2]
                        i += 3
                    else:
                        transform_token = nxt
                        i += 2
                else:
                    i += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    fields.append(
                        {"Field": field, "EnumName": transform_arg, "Raw": value, "Text": text})
                else:
                    fields.append(
                        {"Field": field, "Value": apply_numeric_transform(value, transform_token)})
            result["Resolved"] = {"Entry": entry, "Fields": fields}
        return result

    # EffectValue（NoLevel）
    if table == "EffectValue":
        entry = EFFECT_VALUE_DATA.get(identifier)
        if entry:
            fields = []
            i = 3
            while i < len(parts):
                field = parts[i]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if i + 1 < len(parts):
                    nxt = parts[i + 1]
                    if nxt == "Enum":
                        transform_token = "Enum"
                        if i + 2 < len(parts):
                            transform_arg = parts[i + 2]
                        i += 3
                    else:
                        transform_token = nxt
                        i += 2
                else:
                    i += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    fields.append(
                        {"Field": field, "EnumName": transform_arg, "Raw": value, "Text": text})
                else:
                    fields.append(
                        {"Field": field, "Value": apply_numeric_transform(value, transform_token)})
            result["Resolved"] = {"Entry": entry, "Fields": fields}
        return result

    # Effect（LevelUp）
    if table == "Effect" and mode == "LevelUp":
        entries = build_level_entries(
            identifier, EFFECT_VALUE_DATA, context_max_level)
        levels_out = []
        for level, entry in entries:
            fields = []
            i = 3
            while i < len(parts):
                field = parts[i]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if i + 1 < len(parts):
                    nxt = parts[i + 1]
                    if nxt == "Enum":
                        transform_token = "Enum"
                        if i + 2 < len(parts):
                            transform_arg = parts[i + 2]
                        i += 3
                    else:
                        transform_token = nxt
                        i += 2
                else:
                    i += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    fields.append(
                        {"Field": field, "EnumName": transform_arg, "Raw": value, "Text": text})
                else:
                    fields.append(
                        {"Field": field, "Value": apply_numeric_transform(value, transform_token)})
            levels_out.append({"Level": level, "Fields": fields})
        effect_entry = EFFECT_DATA.get(identifier)
        result["Resolved"] = {"Effect": effect_entry, "Levels": levels_out}
        return result

    # OnceAdditionalAttributeValue（NoLevel）
    if table == "OnceAdditionalAttributeValue" and mode == "NoLevel":
        entry = ONCE_ADD_ATTR_VALUE_DATA.get(identifier)
        if entry:
            fields = []
            i = 3
            while i < len(parts):
                field = parts[i]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if i + 1 < len(parts):
                    nxt = parts[i + 1]
                    if nxt == "Enum":
                        transform_token = "Enum"
                        if i + 2 < len(parts):
                            transform_arg = parts[i + 2]
                        i += 3
                    else:
                        transform_token = nxt
                        i += 2
                else:
                    i += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    fields.append(
                        {"Field": field, "EnumName": transform_arg, "Raw": value, "Text": text})
                else:
                    fields.append(
                        {"Field": field, "Value": apply_numeric_transform(value, transform_token)})
            result["Resolved"] = {"Entry": entry, "Fields": fields}
        return result

    # OnceAdditionalAttribute（LevelUp）
    if table == "OnceAdditionalAttribute" and mode == "LevelUp":
        entries = build_level_entries(
            identifier, ONCE_ADD_ATTR_VALUE_DATA, context_max_level)
        levels_out = []
        for level, entry in entries:
            fields = []
            i = 3
            while i < len(parts):
                field = parts[i]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if i + 1 < len(parts):
                    nxt = parts[i + 1]
                    if nxt == "Enum":
                        transform_token = "Enum"
                        if i + 2 < len(parts):
                            transform_arg = parts[i + 2]
                        i += 3
                    else:
                        transform_token = nxt
                        i += 2
                else:
                    i += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    fields.append(
                        {"Field": field, "EnumName": transform_arg, "Raw": value, "Text": text})
                else:
                    fields.append(
                        {"Field": field, "Value": apply_numeric_transform(value, transform_token)})
            levels_out.append({"Level": level, "Fields": fields})
        result["Resolved"] = {"Levels": levels_out}
        return result

    return result


# -----------------------------------------
# Word トークン（##）は UI 側で処理するため素通し
# -----------------------------------------
_WORD_TOKEN_RE = re.compile(r"##([^#]+)#(\d+)#")


def replace_word_tokens(text: Optional[str]) -> Optional[str]:
    return text


def _find_word_tokens_in_text(text: str) -> List[Tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in _WORD_TOKEN_RE.finditer(text or "")]


def _resolve_word_desc_with_params_for_id(word_id: str) -> str:
    template = WORD_LANG.get(f"Word.{word_id}.2") or ""
    wdef = WORD_DATA.get(str(word_id), {})
    param_values: Dict[str, str] = {}
    for i in range(1, 16):
        k = f"Param{i}"
        p = wdef.get(k)
        if not p:
            continue
        res_all = resolve_param(p, context_max_level=None)
        res = res_all.get("Resolved")
        rep = ""
        if not res:
            rep = ""
        elif "Fields" in res:
            fields = res.get("Fields", [])
            if fields:
                f0 = fields[0]
                if "Value" in f0 and isinstance(f0["Value"], dict):
                    v = f0["Value"]
                    rep = str(v.get("Converted") if v.get("Converted")
                              is not None else (v.get("Raw") or ""))
                elif "Text" in f0:
                    rep = str(f0["Text"])
                elif "Raw" in f0:
                    rep = str(f0["Raw"])
        elif "Values" in res:
            v0 = res["Values"][0] if res["Values"] else None
            if isinstance(v0, dict):
                rep = str(v0.get("Converted") if v0.get("Converted")
                          is not None else (v0.get("Raw") or ""))
        param_values[k] = rep
    return re.sub(r"&Param(\d+)&", lambda m: param_values.get(f"Param{m.group(1)}", ""), template)


def _collect_word_refs_for_character(char_skills: Dict[str, Any]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []

    def push(label: str, wid: str):
        key = (label, wid)
        if key in seen:
            return
        seen.add(key)
        color_hex = None
        wdef = WORD_DATA.get(str(wid), {})
        c = wdef.get("Color")
        if isinstance(c, str) and c:
            color_hex = f"#{c}"
        body = _resolve_word_desc_with_params_for_id(wid)
        out.append({"Id": int(wid), "Label": label,
                   "Color": color_hex, "Body": body})

    for sk in (char_skills or {}).values():
        txts = sk.get("Texts") if sk else None
        if not txts:
            continue
        # Title / Desc のみを対象（BriefDesc は取得していない）
        for field in ("Title", "Desc"):
            t = txts.get(field) or ""
            for label, wid in _find_word_tokens_in_text(t):
                push(label, wid)
    return out

# -----------------------------------------
# スキル詳細（Title/Descのみ）
# -----------------------------------------


def extract_skill_details(skill_id: int) -> Optional[Dict[str, Any]]:
    entry = SKILL_DATA.get(str(skill_id))
    if entry is None:
        return None
    max_level = entry.get("MaxLevel")
    title = replace_word_tokens(SKILL_LANG.get(f"Skill.{skill_id}.1"))
    desc = replace_word_tokens(SKILL_LANG.get(f"Skill.{skill_id}.2"))
    texts = {"Title": title, "Desc": desc}
    params: Dict[str, Any] = {}
    for i in range(1, 16):
        k = f"Param{i}"
        if k in entry and entry[k]:
            params[k] = resolve_param(entry[k], context_max_level=max_level)
    return {"Id": skill_id, "RawData": entry, "Texts": texts, "Params": params}

# -----------------------------------------
# スキル集合
# -----------------------------------------


def gather_skills(character_entry: Dict[str, Any]) -> Dict[str, Any]:
    fields = {
        "NormalAtk": character_entry.get("NormalAtkId"),
        "Skill": character_entry.get("SkillId"),
        "AssistSkill": character_entry.get("AssistSkillId"),
        "Ultimate": character_entry.get("UltimateId"),
        "AssistNormalAtk": character_entry.get("AssistNormalAtkId"),
        "AssistSpecialSkill": character_entry.get("AssistSpecialSkillId"),
        "AssistUltimate": character_entry.get("AssistUltimateId"),
        "TalentSkill": character_entry.get("TalentSkillId"),
    }
    out: Dict[str, Any] = {}
    for name, sid in fields.items():
        out[name] = extract_skill_details(
            sid) if isinstance(sid, int) else None
    return out

# -----------------------------------------
# 強化素材
# -----------------------------------------


def gather_skill_upgrade_details(group_ids: Optional[Iterable[int]]) -> List[Dict[str, Any]]:
    if not group_ids:
        return []
    res: List[Dict[str, Any]] = []
    seen: Set[int] = set()
    for gid in group_ids:
        if not isinstance(gid, int) or gid in seen:
            continue
        seen.add(gid)
        e = SKILL_UPGRADE_DATA.get(str(gid))
        if e:
            res.append(e)
    return res

# -----------------------------------------
# 能力値テーブル
# -----------------------------------------


def gather_attribute_tables(attribute_group_id: Any) -> List[Dict[str, Any]]:
    group_entries: Dict[int, Dict[str, Any]] = {}
    tgt = str(attribute_group_id) if attribute_group_id is not None else None
    for e in ATTRIBUTE_DATA.values():
        if tgt is not None and str(e.get("GroupId")) != tgt:
            continue
        lv = int(e.get("lvl", 0))
        existed = group_entries.get(lv)
        if existed is None or int(e.get("Id")) < int(existed.get("Id", "99999999")):
            group_entries[lv] = e
    if not group_entries:
        return []
    mx = max(group_entries.keys())
    targets = {1, mx}
    targets.update(l for l in group_entries.keys() if l % 10 == 0)
    results: List[Dict[str, Any]] = []
    for lv in sorted(targets):
        e = group_entries.get(lv)
        if not e:
            continue
        stats: List[Dict[str, Any]] = []
        for k, v in e.items():
            if k in {"Id", "GroupId", "lvl"}:
                continue
            jp = UITEXT_LANG.get(f"UIText.Attr_{k}.1")
            stats.append({"Key": k, "JapaneseName": jp, "Value": v})
        results.append({"Level": lv, "Stats": stats})
    return results

# -----------------------------------------
# タレント
# -----------------------------------------


def gather_talents(character_id: int) -> List[Dict[str, Any]]:
    groups = []
    for gid, g in TALENT_GROUP_DATA.items():
        if g.get("CharId") == character_id:
            groups.append((int(gid), g))
    groups.sort(key=lambda x: x[0])
    results: List[Dict[str, Any]] = []
    for gid, g in groups:
        gname = TALENT_GROUP_LANG.get(f"TalentGroup.{gid}.1")
        nodes_src = [n for n in TALENT_DATA.values()
                     if n.get("GroupId") == gid]
        nodes_src.sort(key=lambda it: (it.get("Index", 0),
                       it.get("Sort", 0), it.get("Id")))
        nodes: List[Dict[str, Any]] = []
        for n in nodes_src:
            nid = n.get("Id")
            texts = {"Title": TALENT_LANG.get(
                f"Talent.{nid}.1"), "Desc": TALENT_LANG.get(f"Talent.{nid}.2")}
            params: Dict[str, Any] = {}
            for i in range(1, 10):
                k = f"Param{i}"
                if k in n and n[k]:
                    params[k] = resolve_param(n[k])
            effects_details = []
            for eff_id in n.get("EffectId", []):
                ev = EFFECT_VALUE_DATA.get(str(eff_id))
                eff = EFFECT_DATA.get(str(eff_id))
                summary = None
                if ev:
                    vinfo = ev.get("EffectTypeParam1")
                    conv = apply_numeric_transform(
                        vinfo, "Fixed") if vinfo is not None else None
                    subtype = resolve_enum_text(
                        "EAT", ev.get("EffectTypeFirstSubtype"))
                    summary = {"EffectValue": conv, "SubtypeText": subtype}
                effects_details.append(
                    {"EffectId": eff_id, "Effect": eff, "EffectValue": ev, "Summary": summary})
            nodes.append({"Id": nid, "Index": n.get("Index"), "Type": n.get(
                "Type"), "Texts": texts, "Params": params, "Effects": effects_details})
        results.append({"GroupId": gid, "GroupName": gname,
                       "NodeLimit": g.get("NodeLimit"), "Nodes": nodes})
    return results

# -----------------------------------------
# タグ
# -----------------------------------------


def gather_tags(character_id: int) -> List[Dict[str, Any]]:
    des = CHAR_DES_DATA.get(str(character_id), {})
    tag_ids = des.get("Tag", []) or []
    out: List[Dict[str, Any]] = []
    for tid in tag_ids:
        out.append({"Id": tid, "Name": CHARACTER_TAG_LANG.get(
            f"CharacterTag.{tid}.1"), "Raw": CHARACTER_TAG_DATA.get(str(tid))})
    return out

# -----------------------------------------
# ポテンシャル（Item名優先）
# -----------------------------------------


def gather_potentials(character_id: int) -> Dict[str, List[Dict[str, Any]]]:
    ch = CHAR_POTENTIAL_DATA.get(str(character_id))
    if not ch:
        return {}
    categories: Dict[str, List[Dict[str, Any]]] = {}
    for cname, idlist in ch.items():
        if not isinstance(idlist, list):
            continue
        arr: List[Dict[str, Any]] = []
        for pid in idlist:
            entry = POTENTIAL_DATA.get(str(pid))
            if not entry:
                continue
            name_from_item = ITEM_LANG.get(f"Item.{pid}.1")
            texts = {"Name": name_from_item or POTENTIAL_LANG.get(
                f"Potential.{pid}.1"), "Desc": POTENTIAL_LANG.get(f"Potential.{pid}.2")}
            params: Dict[str, Any] = {}
            max_level = entry.get("MaxLevel")
            for i in range(1, 10):
                k = f"Param{i}"
                if k in entry and entry[k]:
                    params[k] = resolve_param(
                        entry[k], context_max_level=max_level)
            arr.append({"Id": pid, "Raw": entry, "Texts": texts,
                       "Params": params, "MaxLevel": max_level})
        categories[cname] = arr
    return categories

# -----------------------------------------
# 出力構築
# -----------------------------------------


def build_output(character_id: int) -> Dict[str, Any]:
    ce = CHARACTER_DATA.get(str(character_id))
    if ce is None:
        raise ValueError(f"キャラクターID {character_id} のデータが存在しません。")
    jname = CHARACTER_LANG.get(f"Character.{character_id}.1")
    skills_upgrade_group = ce.get("SkillsUpgradeGroup")
    skills = gather_skills(ce)

    return {
        "Character": {
            "Id": ce.get("Id"),
            "InternalName": ce.get("Name"),
            "JapaneseName": jname,
            "Tags": gather_tags(character_id),
        },
        "CombatParameters": {
            "AtkSpd": ce.get("AtkSpd"),
            "SwitchCD": ce.get("SwitchCD"),
            "EnergyConvRatio": ce.get("EnergyConvRatio"),
            "EnergyEfficiency": ce.get("EnergyEfficiency"),
            "GemSlots": ce.get("GemSlots"),
        },
        "Skills": skills,
        "SkillUpgradeDetails": gather_skill_upgrade_details(skills_upgrade_group),
        "RelatedIds": {
            "ViewId": ce.get("ViewId"),
            "AdvanceGroup": ce.get("AdvanceGroup"),
            "FragmentsId": ce.get("FragmentsId"),
            "AttributeId": ce.get("AttributeId"),
            "AIId": ce.get("AIId"),
            "AssistAIId": ce.get("AssistAIId"),
        },
        "AttributeTables": gather_attribute_tables(ce.get("AttributeId")),
        "Talents": gather_talents(character_id),
        "Potentials": gather_potentials(character_id),
        # スキル文（Title/Descのみ）に出現する Word を収集
        "WordRefs": _collect_word_refs_for_character(skills),
    }

# -----------------------------------------
# 保存＆CLI
# -----------------------------------------


def write_output(data: Dict[str, Any], character_id: int) -> None:
    out = BASE_DIR / f"character_{character_id}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="キャラクター詳細を抽出するツール")
    p.add_argument("character_id", type=int, nargs="?",
                   default=TARGET_CHARACTER_ID)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data = build_output(args.character_id)
    write_output(data, args.character_id)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
