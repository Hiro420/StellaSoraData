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


def extract_upgrade_details(group_ids: Optional[List[int]],
                            upgrade_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect upgrade group entries."""
    # スキル強化に使用される素材情報をまとめて取得します。
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
            results.append(entry)
    return results


def main(character_id: int = TARGET_CHARACTER_ID) -> None:
    """Entry point for the extraction script."""
    # 目的のJSONファイルを読み込みます。
    character_data = load_json(BASE_DIR / "JP" / "bin" / "Character.json")
    character_lang = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Character.json")
    skill_data = load_json(BASE_DIR / "JP" / "bin" / "Skill.json")
    skill_lang = load_json(BASE_DIR / "JP" / "language" / "ja_JP" / "Skill.json")
    skill_upgrade_data = load_json(BASE_DIR / "JP" / "bin" / "CharacterSkillUpgrade.json")

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

    # 追加情報として、スキル強化素材の詳細を付加します。
    output["SkillUpgradeDetails"] = extract_upgrade_details(skills_upgrade_group, skill_upgrade_data)

    # 追加情報として、利用可能な関連IDの一覧も提示します。
    output["RelatedIds"] = {
        "ViewId": character_entry.get("ViewId"),
        "AdvanceGroup": character_entry.get("AdvanceGroup"),
        "FragmentsId": character_entry.get("FragmentsId"),
        "AttributeId": character_entry.get("AttributeId"),
        "AIId": character_entry.get("AIId"),
        "AssistAIId": character_entry.get("AssistAIId"),
    }

    # 整形されたJSON文字列として結果を出力します。
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # メイン関数を呼び出し、スクリプトを実行します。
    main()
