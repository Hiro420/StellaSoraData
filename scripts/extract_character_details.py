"""Character detail extraction script."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# 各ブロックに初学者でも理解できるような丁寧な説明コメントを挿入します。

# 入力ファイル群が配置されているリポジトリのルートパスを決定します。
BASE_DIR = Path(__file__).resolve().parents[1]

# 解析対象のキャラクターIDを指定します。初期値として依頼された144を設定しています。
TARGET_CHARACTER_ID = 144


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file as dictionary."""
    # ファイルからJSONを読み込み、Pythonの辞書として返却します。
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def extract_skill_details(skill_id: int,
                           skill_data: Dict[str, Any],
                           skill_lang: Dict[str, str]) -> Dict[str, Any]:
    """Collect skill data and localized text."""
    # スキルIDに対応するデータを抽出し、日本語テキストを付けて整理します。
    key = str(skill_id)
    data = skill_data.get(key, {})
    result: Dict[str, Any] = {
        "Id": skill_id,
        "RawData": data,
        "Texts": {
            "Title": skill_lang.get(f"Skill.{key}.1"),
            "BriefDesc": skill_lang.get(f"Skill.{key}.13"),
            "Desc": skill_lang.get(f"Skill.{key}.2"),
        },
    }
    return result


def extract_localized_text(text_key: Optional[str],
                           lang_data: Dict[str, str]) -> Optional[str]:
    """Fetch localized text by key if available."""
    # ローカライズ用のキーを受け取り、日本語テキストが存在する場合は返します。
    if not text_key:
        return None
    return lang_data.get(text_key)


def extract_item_details(item_id: Optional[int],
                         item_data: Dict[str, Any],
                         item_lang: Dict[str, str],
                         quantity: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Collect item data with localized texts."""
    # 素材IDを受け取り、アイテム情報と日本語テキストをまとめて返します。
    if not isinstance(item_id, int):
        return None
    raw = item_data.get(str(item_id), {})
    result: Dict[str, Any] = {
        "Id": item_id,
        "RawData": raw,
        "Texts": {
            "Title": extract_localized_text(raw.get("Title"), item_lang),
            "Desc": extract_localized_text(raw.get("Desc"), item_lang),
            "Literary": extract_localized_text(raw.get("Literary"), item_lang),
        },
    }
    if quantity is not None:
        result["Quantity"] = quantity
    return result


def extract_gem_details(gem_ids: Optional[List[int]],
                        gem_data: Dict[str, Any],
                        gem_lang: Dict[str, str]) -> List[Dict[str, Any]]:
    """Collect gem details for the provided slots."""
    # キャラクターが装備できる専用音動機の情報をまとめて取得します。
    if not gem_ids:
        return []
    results: List[Dict[str, Any]] = []
    for gem_id in gem_ids:
        raw = gem_data.get(str(gem_id), {})
        result = {
            "Id": gem_id,
            "RawData": raw,
            "Texts": {
                "Title": extract_localized_text(raw.get("Title"), gem_lang),
                "Desc": extract_localized_text(raw.get("Desc"), gem_lang),
            },
        }
        results.append(result)
    return results


def extract_upgrade_details(group_ids: Optional[List[int]],
                            upgrade_data: Dict[str, Any],
                            item_data: Optional[Dict[str, Any]] = None,
                            item_lang: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Collect upgrade group entries."""
    # スキル強化に使用される素材情報をまとめて取得し、必要に応じて詳細も付加します。
    results: List[Dict[str, Any]] = []
    if not group_ids:
        return results
    seen: set[int] = set()
    for group_id in group_ids:
        if group_id in seen:
            continue
        seen.add(group_id)
        entry = upgrade_data.get(str(group_id))
        if entry:
            entry_copy = dict(entry)
            if item_data is not None and item_lang is not None:
                materials: List[Dict[str, Any]] = []
                for idx in range(1, 4):
                    tid_key = f"Tid{idx}"
                    qty_key = f"Qty{idx}"
                    material = extract_item_details(entry.get(tid_key), item_data, item_lang, entry.get(qty_key))
                    if material:
                        materials.append(material)
                if materials:
                    entry_copy["Materials"] = materials
            results.append(entry_copy)
    return results


def extract_advance_details(group_id: Optional[int],
                            advance_data: Dict[str, Any],
                            item_data: Dict[str, Any],
                            item_lang: Dict[str, str]) -> List[Dict[str, Any]]:
    """Collect advance data for the character."""
    # 星級突破に必要な素材情報を抽出し、詳細情報を付けて整理します。
    if not isinstance(group_id, int):
        return []
    results: List[Dict[str, Any]] = []
    for entry in advance_data.values():
        if entry.get("Group") != group_id:
            continue
        entry_copy = dict(entry)
        materials: List[Dict[str, Any]] = []
        for idx in range(1, 4):
            tid_key = f"Tid{idx}"
            qty_key = f"Qty{idx}"
            material = extract_item_details(entry.get(tid_key), item_data, item_lang, entry.get(qty_key))
            if material:
                materials.append(material)
        if materials:
            entry_copy["Materials"] = materials
        results.append(entry_copy)
    results.sort(key=lambda value: value.get("AdvanceLvl", 0))
    return results


def extract_attribute_group(attribute_id: Optional[str],
                            attribute_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect attribute set that matches the provided group id."""
    # キャラクター成長パラメータ群を抽出して、レベル順に整理します。
    if attribute_id is None:
        return []
    try:
        target_group = int(attribute_id)
    except (TypeError, ValueError):
        return []
    results: List[Dict[str, Any]] = []
    for entry in attribute_data.values():
        if entry.get("GroupId") == target_group:
            results.append(entry)
    results.sort(key=lambda value: value.get("lvl", 0))
    return results


def extract_view_details(view_id: Optional[int],
                         view_data: Dict[str, Any],
                         view_lang: Dict[str, str],
                         tag_data: Dict[str, Any],
                         tag_lang: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Collect descriptive view information for the character."""
    # キャラクターの紹介文やタグを取得し、関連する日本語テキストを付けます。
    if not isinstance(view_id, int):
        return None
    raw = view_data.get(str(view_id))
    if raw is None:
        return None
    tag_details: List[Dict[str, Any]] = []
    for tag_id in raw.get("Tag", []):
        tag_raw = tag_data.get(str(tag_id), {})
        tag_details.append({
            "Id": tag_id,
            "RawData": tag_raw,
            "Texts": {
                "Title": extract_localized_text(tag_raw.get("Title"), tag_lang),
            },
        })
    texts = {
        "Alias": extract_localized_text(raw.get("Alias"), view_lang),
        "CnCv": extract_localized_text(raw.get("CnCv"), view_lang),
        "JpCv": extract_localized_text(raw.get("JpCv"), view_lang),
        "CharDes": extract_localized_text(raw.get("CharDes"), view_lang),
        "PotentialMain1": extract_localized_text(raw.get("PotentialMain1"), view_lang),
        "PotentialMain2": extract_localized_text(raw.get("PotentialMain2"), view_lang),
        "PotentialAssistant1": extract_localized_text(raw.get("PotentialAssistant1"), view_lang),
        "PotentialAssistant2": extract_localized_text(raw.get("PotentialAssistant2"), view_lang),
        "PotentialMainContent1": extract_localized_text(raw.get("PotentialMainContent1"), view_lang),
        "PotentialMainContent2": extract_localized_text(raw.get("PotentialMainContent2"), view_lang),
        "PotentialAssistantContent1": extract_localized_text(raw.get("PotentialAssistantContent1"), view_lang),
        "PotentialAssistantContent2": extract_localized_text(raw.get("PotentialAssistantContent2"), view_lang),
    }
    return {
        "RawData": raw,
        "Texts": texts,
        "TagDetails": tag_details,
        "PreferTags": raw.get("PreferTags"),
        "HateTags": raw.get("HateTags"),
    }


def extract_ai_details(ai_id: Optional[int], ai_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Collect AI configuration by identifier."""
    # キャラクターAIに関する設定値を取り出します。
    if not isinstance(ai_id, int):
        return None
    raw = ai_data.get(str(ai_id))
    if raw is None:
        return None
    return {"Id": ai_id, "RawData": raw}


def main(character_id: int = TARGET_CHARACTER_ID) -> None:
    """Entry point for the extraction script."""
    # 目的のJSONファイルを読み込みます。
    character_data = load_json(BASE_DIR / "JP" / "bin" / "Character.json")
    character_lang = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Character.json")
    skill_data = load_json(BASE_DIR / "JP" / "bin" / "Skill.json")
    skill_lang = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Skill.json")
    skill_upgrade_data = load_json(BASE_DIR / "JP" / "bin" / "CharacterSkillUpgrade.json")
    char_gem_data = load_json(BASE_DIR / "JP" / "bin" / "CharGem.json")
    char_gem_lang = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "CharGem.json")
    item_data = load_json(BASE_DIR / "JP" / "bin" / "Item.json")
    item_lang = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Item.json")
    view_data = load_json(BASE_DIR / "JP" / "bin" / "CharacterDes.json")
    view_lang = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "CharacterDes.json")
    tag_data = load_json(BASE_DIR / "JP" / "bin" / "CharacterTag.json")
    tag_lang = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "CharacterTag.json")
    advance_data = load_json(BASE_DIR / "JP" / "bin" / "CharacterAdvance.json")
    attribute_data = load_json(BASE_DIR / "JP" / "bin" / "Attribute.json")
    ai_data = load_json(BASE_DIR / "JP" / "bin" / "AI.json")

    # キャラクター情報を取得します。存在しない場合は適切に通知します。
    char_key = str(character_id)
    character_entry: Optional[Dict[str, Any]] = character_data.get(char_key)
    if character_entry is None:
        print(f"キャラクターID {character_id} の情報が見つかりませんでした。")
        return

    # 出力用の構造体を初期化します。
    skills_upgrade_group = character_entry.get("SkillsUpgradeGroup")
    output: Dict[str, Any] = {
        "Id": character_entry.get("Id"),
        "InternalName": character_entry.get("Name"),
        "JapaneseName": character_lang.get(f"Character.{char_key}.1"),
        "AtkSpd": character_entry.get("AtkSpd"),
        "SwitchCD": character_entry.get("SwitchCD"),
        "EnergyConvRatio": character_entry.get("EnergyConvRatio"),
        "EnergyEfficiency": character_entry.get("EnergyEfficiency"),
        "SkillsUpgradeGroup": skills_upgrade_group,
        "GemSlots": character_entry.get("GemSlots"),
    }

    # 参照されるスキル情報を丁寧に収集します。
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

    # スキル情報をまとめて取り出し、結果に追加します。
    output_skills: Dict[str, Any] = {}
    for field_name, skill_id in skill_fields.items():
        if isinstance(skill_id, int):
            output_skills[field_name] = extract_skill_details(skill_id, skill_data, skill_lang)
        else:
            output_skills[field_name] = None
    output["Skills"] = output_skills

    # 追加情報として、専用音動機の詳細を付け加えます。
    gem_slots = character_entry.get("GemSlots")
    output["GemSlotDetails"] = extract_gem_details(gem_slots, char_gem_data, char_gem_lang)

    # 追加情報として、スキル強化素材の詳細を付加します。
    output["SkillUpgradeDetails"] = extract_upgrade_details(
        skills_upgrade_group,
        skill_upgrade_data,
        item_data,
        item_lang,
    )

    # 追加情報として、利用可能な関連IDの一覧も提示します。
    view_id = character_entry.get("ViewId")
    advance_group = character_entry.get("AdvanceGroup")
    fragments_id = character_entry.get("FragmentsId")
    attribute_id = character_entry.get("AttributeId")
    ai_id = character_entry.get("AIId")
    assist_ai_id = character_entry.get("AssistAIId")

    output["RelatedIds"] = {
        "ViewId": view_id,
        "AdvanceGroup": advance_group,
        "FragmentsId": fragments_id,
        "AttributeId": attribute_id,
        "AIId": ai_id,
        "AssistAIId": assist_ai_id,
    }

    # 追加情報として、関連IDに対応する詳細データをひとまとめにします。
    fragment_detail = extract_item_details(fragments_id, item_data, item_lang)
    output["RelatedDetails"] = {
        "View": extract_view_details(view_id, view_data, view_lang, tag_data, tag_lang),
        "Advance": extract_advance_details(advance_group, advance_data, item_data, item_lang),
        "FragmentItem": fragment_detail,
        "Attributes": extract_attribute_group(attribute_id, attribute_data),
        "AI": extract_ai_details(ai_id, ai_data),
        "AssistAI": extract_ai_details(assist_ai_id, ai_data),
    }

    # 整形されたJSON文字列として結果を出力します。
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # メイン関数を呼び出し、スクリプトを実行します。
    main()
