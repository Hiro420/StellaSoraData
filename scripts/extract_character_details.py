"""キャラクターデータを詳細に収集するスクリプト。"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# 各ブロックごとに初学者でも理解できるよう丁寧なコメントを記載します。

# リポジトリのルートパスを決定し、後続のファイル読み込みに利用します。
BASE_DIR = Path(__file__).resolve().parents[1]

# デフォルトで解析するキャラクターIDを指定します。依頼内容に合わせて144を採用します。
TARGET_CHARACTER_ID = 144

# JSONファイルを読み込んだ結果をキャッシュするための辞書を用意します。
_JSON_CACHE: Dict[Path, Any] = {}


def load_json(path: Path) -> Any:
    """JSONファイルを読み込み、Pythonオブジェクトとして返却します。"""
    # 同じファイルを繰り返し読み込む無駄を省くため、キャッシュを利用します。
    if path not in _JSON_CACHE:
        with path.open(encoding="utf-8") as handle:
            _JSON_CACHE[path] = json.load(handle)
    return _JSON_CACHE[path]


# 後続の処理で参照するデータ群を事前に読み込みます。
CHARACTER_DATA = load_json(BASE_DIR / "JP" / "bin" / "Character.json")
CHARACTER_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Character.json")
SKILL_DATA = load_json(BASE_DIR / "JP" / "bin" / "Skill.json")
SKILL_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Skill.json")
SKILL_UPGRADE_DATA = load_json(BASE_DIR / "JP" / "bin" / "CharacterSkillUpgrade.json")
HIT_DAMAGE_DATA = load_json(BASE_DIR / "JP" / "bin" / "HitDamage.json")
BUFF_VALUE_DATA = load_json(BASE_DIR / "JP" / "bin" / "BuffValue.json")
EFFECT_VALUE_DATA = load_json(BASE_DIR / "JP" / "bin" / "EffectValue.json")
EFFECT_DATA = load_json(BASE_DIR / "JP" / "bin" / "Effect.json")
ATTRIBUTE_DATA = load_json(BASE_DIR / "JP" / "bin" / "Attribute.json")
UITEXT_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "UIText.json")
CHARACTER_TAG_DATA = load_json(BASE_DIR / "JP" / "bin" / "CharacterTag.json")
CHARACTER_TAG_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "CharacterTag.json")
CHAR_DES_DATA = load_json(BASE_DIR / "JP" / "bin" / "CharacterDes.json")
TALENT_GROUP_DATA = load_json(BASE_DIR / "JP" / "bin" / "TalentGroup.json")
TALENT_GROUP_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "TalentGroup.json")
TALENT_DATA = load_json(BASE_DIR / "JP" / "bin" / "Talent.json")
TALENT_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Talent.json")
CHAR_POTENTIAL_DATA = load_json(BASE_DIR / "JP" / "bin" / "CharPotential.json")
POTENTIAL_DATA = load_json(BASE_DIR / "JP" / "bin" / "Potential.json")
POTENTIAL_LANG = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Potential.json")
ONCE_ADD_ATTR_DATA = load_json(BASE_DIR / "JP" / "bin" / "OnceAdditionalAttribute.json")
ONCE_ADD_ATTR_VALUE_DATA = load_json(BASE_DIR / "JP" / "bin" / "OnceAdditionalAttributeValue.json")
ENUM_DESC_DATA = load_json(BASE_DIR / "JP" / "bin" / "EnumDesc.json")


def resolve_enum_text(enum_name: str, raw_value: Any) -> Optional[str]:
    """列挙体の数値を日本語テキストへ変換します。"""
    # 列挙体を示すJSONでは値と文字列キーが対応付けられているため、ループで一致するものを探します。
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


def build_level_entries(base_id: Any, dataset: Dict[str, Any], max_level: Optional[int] = None) -> List[Tuple[int, Dict[str, Any]]]:
    """基底IDからレベル別エントリを順番に取得します。"""
    # IDは文字列に統一した上で、末尾2桁を利用したパターンで展開されることが多いためその規則に従います。
    base_str = str(base_id)
    if len(base_str) < 3:
        return []
    prefix = base_str[:-2]
    suffix = base_str[-1]
    entries: List[Tuple[int, Dict[str, Any]]] = []
    level = 1
    while True:
        level_id = f"{prefix}{level}{suffix}"
        candidate = dataset.get(level_id)
        if candidate is None:
            break
        entries.append((level, candidate))
        level += 1
        if max_level is not None and level > max_level:
            break
    return entries


def apply_numeric_transform(raw_value: Any, transform: Optional[str]) -> Dict[str, Any]:
    """数値変換を行い、元の値と併せて返却します。"""
    # 変換の種類ごとに分岐し、単純な除算で表現可能なものは浮動小数点に変換します。
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
    return {
        "Raw": raw_value,
        "Converted": converted,
        "Transform": transform,
    }


def resolve_param(param_str: str, context_max_level: Optional[int] = None) -> Dict[str, Any]:
    """Param文字列を解析して実際の値に変換します。"""
    # 解析結果をまとめる辞書を初期化し、後で共通のプレースホルダを追加します。
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

    # HitDamageのダメージ倍率を処理します。
    if table == "HitDamage" and mode == "DamageNum":
        entry = HIT_DAMAGE_DATA.get(identifier)
        if entry:
            raw_list = entry.get("SkillPercentAmend", [])
            if isinstance(raw_list, list):
                # スキルレベル分だけ値を抜き出し、10000で除算した値を併記します。
                per_level = []
                max_count = context_max_level or len(raw_list)
                for index, raw_value in enumerate(raw_list[:max_count], start=1):
                    converted = None
                    try:
                        converted = float(raw_value) / 10000
                    except (TypeError, ValueError):
                        converted = None
                    per_level.append({
                        "Level": index,
                        "Raw": raw_value,
                        "Converted": converted,
                    })
                result["Resolved"] = {
                    "Field": "SkillPercentAmend",
                    "Values": per_level,
                }
        return result

    # BuffValueに格納された数値を処理します。
    if table == "BuffValue":
        entry = BUFF_VALUE_DATA.get(identifier)
        if entry:
            resolved_fields = []
            index = 3
            while index < len(parts):
                field = parts[index]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if index + 1 < len(parts):
                    next_token = parts[index + 1]
                    if next_token == "Enum":
                        transform_token = "Enum"
                        if index + 2 < len(parts):
                            transform_arg = parts[index + 2]
                        index += 3
                    else:
                        transform_token = next_token
                        index += 2
                else:
                    index += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    resolved_fields.append({
                        "Field": field,
                        "EnumName": transform_arg,
                        "Raw": value,
                        "Text": text,
                    })
                else:
                    resolved_fields.append({
                        "Field": field,
                        "Value": apply_numeric_transform(value, transform_token),
                    })
            result["Resolved"] = {
                "Entry": entry,
                "Fields": resolved_fields,
            }
        return result

    # EffectValueの単体値を処理します。
    if table == "EffectValue":
        entry = EFFECT_VALUE_DATA.get(identifier)
        if entry:
            resolved_fields = []
            index = 3
            while index < len(parts):
                field = parts[index]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if index + 1 < len(parts):
                    next_token = parts[index + 1]
                    if next_token == "Enum":
                        transform_token = "Enum"
                        if index + 2 < len(parts):
                            transform_arg = parts[index + 2]
                        index += 3
                    else:
                        transform_token = next_token
                        index += 2
                else:
                    index += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    resolved_fields.append({
                        "Field": field,
                        "EnumName": transform_arg,
                        "Raw": value,
                        "Text": text,
                    })
                else:
                    resolved_fields.append({
                        "Field": field,
                        "Value": apply_numeric_transform(value, transform_token),
                    })
            result["Resolved"] = {
                "Entry": entry,
                "Fields": resolved_fields,
            }
        return result

    # Effectのレベル別データを処理します。
    if table == "Effect" and mode == "LevelUp":
        entries = build_level_entries(identifier, EFFECT_VALUE_DATA, context_max_level)
        resolved_levels = []
        for level, entry in entries:
            resolved_fields = []
            index = 3
            while index < len(parts):
                field = parts[index]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if index + 1 < len(parts):
                    next_token = parts[index + 1]
                    if next_token == "Enum":
                        transform_token = "Enum"
                        if index + 2 < len(parts):
                            transform_arg = parts[index + 2]
                        index += 3
                    else:
                        transform_token = next_token
                        index += 2
                else:
                    index += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    resolved_fields.append({
                        "Field": field,
                        "EnumName": transform_arg,
                        "Raw": value,
                        "Text": text,
                    })
                else:
                    resolved_fields.append({
                        "Field": field,
                        "Value": apply_numeric_transform(value, transform_token),
                    })
            resolved_levels.append({
                "Level": level,
                "Fields": resolved_fields,
            })
        effect_entry = EFFECT_DATA.get(identifier)
        result["Resolved"] = {
            "Effect": effect_entry,
            "Levels": resolved_levels,
        }
        return result

    # OnceAdditionalAttributeValueの固定値を処理します。
    if table == "OnceAdditionalAttributeValue" and mode == "NoLevel":
        entry = ONCE_ADD_ATTR_VALUE_DATA.get(identifier)
        if entry:
            resolved_fields = []
            index = 3
            while index < len(parts):
                field = parts[index]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if index + 1 < len(parts):
                    next_token = parts[index + 1]
                    if next_token == "Enum":
                        transform_token = "Enum"
                        if index + 2 < len(parts):
                            transform_arg = parts[index + 2]
                        index += 3
                    else:
                        transform_token = next_token
                        index += 2
                else:
                    index += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    resolved_fields.append({
                        "Field": field,
                        "EnumName": transform_arg,
                        "Raw": value,
                        "Text": text,
                    })
                else:
                    resolved_fields.append({
                        "Field": field,
                        "Value": apply_numeric_transform(value, transform_token),
                    })
            result["Resolved"] = {
                "Entry": entry,
                "Fields": resolved_fields,
            }
        return result

    # OnceAdditionalAttributeのレベル別データを処理します。
    if table == "OnceAdditionalAttribute" and mode == "LevelUp":
        entries = build_level_entries(identifier, ONCE_ADD_ATTR_VALUE_DATA, context_max_level)
        resolved_levels = []
        for level, entry in entries:
            resolved_fields = []
            index = 3
            while index < len(parts):
                field = parts[index]
                transform_token: Optional[str] = None
                transform_arg: Optional[str] = None
                if index + 1 < len(parts):
                    next_token = parts[index + 1]
                    if next_token == "Enum":
                        transform_token = "Enum"
                        if index + 2 < len(parts):
                            transform_arg = parts[index + 2]
                        index += 3
                    else:
                        transform_token = next_token
                        index += 2
                else:
                    index += 1
                value = entry.get(field)
                if transform_token == "Enum" and transform_arg:
                    text = resolve_enum_text(transform_arg, value)
                    resolved_fields.append({
                        "Field": field,
                        "EnumName": transform_arg,
                        "Raw": value,
                        "Text": text,
                    })
                else:
                    resolved_fields.append({
                        "Field": field,
                        "Value": apply_numeric_transform(value, transform_token),
                    })
            resolved_levels.append({
                "Level": level,
                "Fields": resolved_fields,
            })
        result["Resolved"] = {
            "Levels": resolved_levels,
        }
        return result

    # ModeやTableが想定外の場合はソース情報のみ返します。
    return result


def extract_skill_details(skill_id: int) -> Optional[Dict[str, Any]]:
    """スキル情報を抽出し、日本語テキストとParam解析結果を付与します。"""
    # 該当スキルIDが存在しない場合はNoneを返して呼び出し側で扱います。
    skill_entry = SKILL_DATA.get(str(skill_id))
    if skill_entry is None:
        return None
    max_level = skill_entry.get("MaxLevel")
    texts = {
        "Title": SKILL_LANG.get(f"Skill.{skill_id}.1"),
        "BriefDesc": SKILL_LANG.get(f"Skill.{skill_id}.13"),
        "Desc": SKILL_LANG.get(f"Skill.{skill_id}.2"),
    }
    params: Dict[str, Any] = {}
    for index in range(1, 10):
        key = f"Param{index}"
        if key in skill_entry and skill_entry[key]:
            params[key] = resolve_param(skill_entry[key], context_max_level=max_level)
    return {
        "Id": skill_id,
        "RawData": skill_entry,
        "Texts": texts,
        "Params": params,
    }


def gather_skills(character_entry: Dict[str, Any]) -> Dict[str, Any]:
    """キャラクターが参照する各スキルの詳細をまとめます。"""
    # キャラクターJSONに記載されているスキルIDを一覧化し、種類ごとに整理します。
    skill_fields = {
        "NormalAtk": character_entry.get("NormalAtkId"),
        "Skill": character_entry.get("SkillId"),
        "SpecialSkill": character_entry.get("SpecialSkillId"),
        "Ultimate": character_entry.get("UltimateId"),
        "AssistNormalAtk": character_entry.get("AssistNormalAtkId"),
        "AssistSkill": character_entry.get("AssistSkillId"),
        "AssistSpecialSkill": character_entry.get("AssistSpecialSkillId"),
        "AssistUltimate": character_entry.get("AssistUltimateId"),
        "TalentSkill": character_entry.get("TalentSkillId"),
    }
    gathered: Dict[str, Any] = {}
    for field_name, skill_id in skill_fields.items():
        if isinstance(skill_id, int):
            gathered[field_name] = extract_skill_details(skill_id)
        else:
            gathered[field_name] = None
    return gathered


def gather_skill_upgrade_details(group_ids: Optional[Iterable[int]]) -> List[Dict[str, Any]]:
    """スキル強化素材テーブルをまとめて取得します。"""
    # グループIDが重複する場合に備えて集合で重複排除しながら収集します。
    if not group_ids:
        return []
    results: List[Dict[str, Any]] = []
    seen: set[int] = set()
    for group_id in group_ids:
        if not isinstance(group_id, int) or group_id in seen:
            continue
        seen.add(group_id)
        entry = SKILL_UPGRADE_DATA.get(str(group_id))
        if entry:
            results.append(entry)
    return results


def gather_attribute_tables(attribute_group_id: Any) -> List[Dict[str, Any]]:
    """10レベル毎に能力値表を抽出し、日本語名とともに返します。"""
    # 同一レベルで複数行がある場合はIDの昇順で最初のものを採用します。
    group_entries: Dict[int, Dict[str, Any]] = {}
    target_group = str(attribute_group_id) if attribute_group_id is not None else None
    for entry in ATTRIBUTE_DATA.values():
        if target_group is not None and str(entry.get("GroupId")) != target_group:
            continue
        level = int(entry.get("lvl", 0))
        existing = group_entries.get(level)
        if existing is None or int(entry.get("Id")) < int(existing.get("Id", "99999999")):
            group_entries[level] = entry
    if not group_entries:
        return []
    max_level = max(group_entries.keys())
    target_levels = {1, max_level}
    target_levels.update(level for level in group_entries.keys() if level % 10 == 0)
    selected_levels = sorted(target_levels)
    results: List[Dict[str, Any]] = []
    for level in selected_levels:
        entry = group_entries.get(level)
        if not entry:
            continue
        stats: List[Dict[str, Any]] = []
        for key, value in entry.items():
            if key in {"Id", "GroupId", "lvl"}:
                continue
            translation = UITEXT_LANG.get(f"UIText.Attr_{key}.1")
            stats.append({
                "Key": key,
                "JapaneseName": translation,
                "Value": value,
            })
        results.append({
            "Level": level,
            "Stats": stats,
        })
    return results


def gather_talents(character_id: int) -> List[Dict[str, Any]]:
    """心相ツリーの情報を段階ごとに整理します。"""
    # キャラクターIDでフィルタされたグループを抽出し、ID順で処理します。
    groups = []
    for group_id, group_entry in TALENT_GROUP_DATA.items():
        if group_entry.get("CharId") == character_id:
            groups.append((int(group_id), group_entry))
    groups.sort(key=lambda item: item[0])
    results: List[Dict[str, Any]] = []
    for group_id, group_entry in groups:
        group_name = TALENT_GROUP_LANG.get(f"TalentGroup.{group_id}.1")
        nodes: List[Dict[str, Any]] = []
        for node in sorted(
            (node for node in TALENT_DATA.values() if node.get("GroupId") == group_id),
            key=lambda item: (item.get("Index", 0), item.get("Sort", 0), item.get("Id"))
        ):
            node_id = node.get("Id")
            texts = {
                "Title": TALENT_LANG.get(f"Talent.{node_id}.1"),
                "Desc": TALENT_LANG.get(f"Talent.{node_id}.2"),
            }
            params: Dict[str, Any] = {}
            for index in range(1, 10):
                key = f"Param{index}"
                if key in node and node[key]:
                    params[key] = resolve_param(node[key])
            effects_details = []
            for effect_id in node.get("EffectId", []):
                effect_entry = EFFECT_DATA.get(str(effect_id))
                effect_value_entry = EFFECT_VALUE_DATA.get(str(effect_id))
                effect_text = None
                if effect_value_entry:
                    # 効果量を固定値として簡易的にまとめます。変換はFixedとして扱い、生の値を重視します。
                    value_info = effect_value_entry.get("EffectTypeParam1")
                    converted = apply_numeric_transform(value_info, "Fixed") if value_info is not None else None
                    subtype_text = resolve_enum_text("EAT", effect_value_entry.get("EffectTypeFirstSubtype"))
                    effect_text = {
                        "EffectValue": converted,
                        "SubtypeText": subtype_text,
                    }
                effects_details.append({
                    "EffectId": effect_id,
                    "Effect": effect_entry,
                    "EffectValue": effect_value_entry,
                    "Summary": effect_text,
                })
            nodes.append({
                "Id": node_id,
                "Index": node.get("Index"),
                "Type": node.get("Type"),
                "Texts": texts,
                "Params": params,
                "Effects": effects_details,
            })
        results.append({
            "GroupId": group_id,
            "GroupName": group_name,
            "NodeLimit": group_entry.get("NodeLimit"),
            "Nodes": nodes,
        })
    return results


def gather_tags(character_id: int) -> List[Dict[str, Any]]:
    """キャラクタータグIDと日本語名称を取得します。"""
    # CharacterDes.jsonに含まれるTag配列からIDを取得し、タグ辞書を参照します。
    char_des_entry = CHAR_DES_DATA.get(str(character_id), {})
    tag_ids = char_des_entry.get("Tag", []) or []
    tags: List[Dict[str, Any]] = []
    for tag_id in tag_ids:
        tag_entry = CHARACTER_TAG_DATA.get(str(tag_id))
        tag_name = CHARACTER_TAG_LANG.get(f"CharacterTag.{tag_id}.1")
        tags.append({
            "Id": tag_id,
            "Name": tag_name,
            "Raw": tag_entry,
        })
    return tags


def gather_potentials(character_id: int) -> Dict[str, List[Dict[str, Any]]]:
    """ポテンシャル情報をカテゴリごとに集約します。"""
    char_potential_entry = CHAR_POTENTIAL_DATA.get(str(character_id))
    if not char_potential_entry:
        return {}
    categories: Dict[str, List[Dict[str, Any]]] = {}
    for category_name, id_list in char_potential_entry.items():
        if not isinstance(id_list, list):
            continue
        potentials: List[Dict[str, Any]] = []
        for potential_id in id_list:
            entry = POTENTIAL_DATA.get(str(potential_id))
            if not entry:
                continue
            texts = {
                "Name": POTENTIAL_LANG.get(f"Potential.{potential_id}.1"),
                "Desc": POTENTIAL_LANG.get(f"Potential.{potential_id}.2"),
            }
            params: Dict[str, Any] = {}
            max_level = entry.get("MaxLevel")
            for index in range(1, 10):
                key = f"Param{index}"
                if key in entry and entry[key]:
                    params[key] = resolve_param(entry[key], context_max_level=max_level)
            potentials.append({
                "Id": potential_id,
                "Raw": entry,
                "Texts": texts,
                "Params": params,
                "MaxLevel": max_level,
            })
        categories[category_name] = potentials
    return categories


def build_output(character_id: int) -> Dict[str, Any]:
    """最終的な出力構造を組み立てます。"""
    character_entry = CHARACTER_DATA.get(str(character_id))
    if character_entry is None:
        raise ValueError(f"キャラクターID {character_id} のデータが存在しません。")
    japanese_name = CHARACTER_LANG.get(f"Character.{character_id}.1")
    skills_upgrade_group = character_entry.get("SkillsUpgradeGroup")

    return {
        "Character": {
            "Id": character_entry.get("Id"),
            "InternalName": character_entry.get("Name"),
            "JapaneseName": japanese_name,
            "Tags": gather_tags(character_id),
        },
        "CombatParameters": {
            "AtkSpd": character_entry.get("AtkSpd"),
            "SwitchCD": character_entry.get("SwitchCD"),
            "EnergyConvRatio": character_entry.get("EnergyConvRatio"),
            "EnergyEfficiency": character_entry.get("EnergyEfficiency"),
            "GemSlots": character_entry.get("GemSlots"),
        },
        "Skills": gather_skills(character_entry),
        "SkillUpgradeDetails": gather_skill_upgrade_details(skills_upgrade_group),
        "RelatedIds": {
            "ViewId": character_entry.get("ViewId"),
            "AdvanceGroup": character_entry.get("AdvanceGroup"),
            "FragmentsId": character_entry.get("FragmentsId"),
            "AttributeId": character_entry.get("AttributeId"),
            "AIId": character_entry.get("AIId"),
            "AssistAIId": character_entry.get("AssistAIId"),
        },
        "AttributeTables": gather_attribute_tables(character_entry.get("AttributeId")),
        "Talents": gather_talents(character_id),
        "Potentials": gather_potentials(character_id),
    }


def write_output(data: Dict[str, Any], character_id: int) -> None:
    """結果をルート直下のJSONファイルへ書き出します。"""
    output_path = BASE_DIR / f"character_{character_id}.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解釈します。"""
    parser = argparse.ArgumentParser(description="キャラクター詳細を抽出するツール")
    parser.add_argument(
        "character_id",
        type=int,
        nargs="?",
        default=TARGET_CHARACTER_ID,
        help="解析対象のキャラクターIDを指定します。省略時は144を使用します。",
    )
    return parser.parse_args()


def main() -> None:
    """スクリプトのエントリーポイントです。"""
    args = parse_args()
    data = build_output(args.character_id)
    write_output(data, args.character_id)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # メイン関数を呼び出して処理を開始します。
    main()
