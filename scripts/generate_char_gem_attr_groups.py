# このブロックでは必要な標準ライブラリを読み込みます。
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any


# このブロックでは入力ファイルと出力フォルダの基本となるパスを定義いたします。
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "JP"
OUTPUT_DIR = BASE_DIR / "output" / "char_gem_attr_groups"


# このブロックでは素質タグの末尾2桁に応じた名称置換の対応表を準備いたします。
TRAIT_NAME_MAP: Dict[str, str] = {
    "05": "主力金素質1",
    "06": "主力金素質2",
    "07": "主力虹素質1",
    "08": "主力金素質3",
    "09": "主力金素質4",
    "10": "主力虹素質2",
    "11": "主力金素質5",
    "12": "主力金素質6",
    "13": "主力虹素質3",
    "25": "支援金素質1",
    "26": "支援金素質2",
    "27": "支援虹素質1",
    "28": "支援金素質3",
    "29": "支援金素質4",
    "30": "支援虹素質2",
    "31": "支援金素質5",
    "32": "支援金素質6",
    "33": "支援虹素質3",
    "41": "汎用金素質1",
    "42": "汎用金素質2",
    "43": "汎用金素質3",
}


# このブロックでは素質タグを検索するための正規表現を準備いたします。
TRAIT_PATTERN = re.compile(r"##素質#(\d{4})#レベル")


def load_json(path: Path) -> Dict[str, Any]:
    """指定されたパスからJSONデータを読み込みます。"""
    # このブロックではJSONファイルを開き、辞書型として読み込んで返却いたします。
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def format_value(value_str: str) -> str:
    """値を表示用に整形します。"""
    # このブロックでは文字列を浮動小数点に変換し、条件に応じて整形いたします。
    try:
        numeric_value = float(value_str)
    except ValueError:
        return value_str

    if numeric_value < 1:
        percentage = numeric_value * 100
        return f"{percentage:g}%"

    if numeric_value.is_integer():
        return str(int(numeric_value))

    return str(numeric_value)


def build_effect_key(attr_value: Dict[str, Any]) -> str:
    """EffectDesc検索用のキーを生成します。"""
    # このブロックではAttrTypeおよびサブタイプの情報を組み合わせてキーを作成いたします。
    attr_type = str(attr_value.get("AttrType"))
    first = attr_value.get("AttrTypeFirstSubtype")
    second = attr_value.get("AttrTypeSecondSubtype")

    suffix_parts: List[str] = []
    if first is not None:
        suffix_parts.append(str(first))
    if second is not None:
        suffix_parts.append(str(second))

    if not suffix_parts:
        return ""

    suffix = "".join(suffix_parts).zfill(4)
    return f"EffectDesc.{attr_type}{suffix}.1"


def resolve_name(raw_name: str) -> str:
    """タグ付き名称を最終的な名称に変換します。"""
    # このブロックでは素質タグの有無を確認し、必要であれば置換を実施いたします。
    match = TRAIT_PATTERN.search(raw_name)
    if not match:
        return raw_name

    tail_digits = match.group(1)[-2:]
    return TRAIT_NAME_MAP.get(tail_digits, raw_name)


def aggregate_group_data() -> Dict[int, Dict[str, Any]]:
    """全グループのデータを集約して返します。"""
    # このブロックでは元データを読み込み、グループごとの情報を集約いたします。
    type_data = load_json(DATA_DIR / "bin" / "CharGemAttrType.json")
    group_data = load_json(DATA_DIR / "bin" / "CharGemAttrGroup.json")
    value_data = load_json(DATA_DIR / "bin" / "CharGemAttrValue.json")
    effect_descs = load_json(DATA_DIR / "language" / "ja_JP" / "EffectDesc.json")

    group_weights: Dict[int, int] = {}
    for item in group_data.values():
        group_id = int(item.get("GroupId"))
        if group_id not in group_weights and "Weight" in item:
            group_weights[group_id] = item["Weight"]

    values_by_type: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for item in value_data.values():
        type_id = int(item.get("TypeId"))
        values_by_type[type_id].append(item)

    grouped_results: Dict[int, Dict[str, Any]] = {}

    for item in type_data.values():
        type_id = int(item.get("Id"))
        group_id = int(item.get("GroupId"))

        group_entry = grouped_results.setdefault(
            group_id,
            {
                "GroupId": group_id,
                "Weight": group_weights.get(group_id),
                "Names": defaultdict(list),
            },
        )

        for value in values_by_type.get(type_id, []):
            effect_key = build_effect_key(value)
            if not effect_key:
                continue

            effect_name = effect_descs.get(effect_key)
            if not effect_name:
                continue

            resolved_name = resolve_name(effect_name)
            formatted_value = format_value(value.get("Value", ""))
            rarity = value.get("Rarity")

            group_entry["Names"][resolved_name].append(
                {
                    "TypeId": type_id,
                    "Rarity": rarity,
                    "Value": formatted_value,
                }
            )

    for group_entry in grouped_results.values():
        names_dict = group_entry["Names"]
        sorted_names = {}
        for name in sorted(names_dict):
            rarity_list = names_dict[name]
            rarity_list.sort(key=lambda item: item["Rarity"])
            sorted_names[name] = rarity_list
        group_entry["Names"] = sorted_names

    return grouped_results


def write_group_files(grouped_results: Dict[int, Dict[str, Any]]) -> None:
    """個別およびまとめファイルを作成します。"""
    # このブロックでは出力ディレクトリを準備し、個別のグループファイルを書き出します。
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for group_id, data in sorted(grouped_results.items()):
        output_path = OUTPUT_DIR / f"group_{group_id}.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    # このブロックでは指定されたグループをまとめたファイルを作成いたします。
    group_sets = {
        "group_1_2_3_4.json": [1, 2, 3, 4],
        "group_5_6_7_8.json": [5, 6, 7, 8],
        "group_9_10.json": [9, 10],
    }

    for filename, group_ids in group_sets.items():
        combined = {
            "GroupIds": group_ids,
            "Groups": {
                str(gid): grouped_results.get(gid)
                for gid in group_ids
                if gid in grouped_results
            },
        }
        output_path = OUTPUT_DIR / filename
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(combined, handle, ensure_ascii=False, indent=2)


def main() -> None:
    """スクリプトのエントリーポイントです。"""
    # このブロックでは全体の処理フローを実行いたします。
    grouped_results = aggregate_group_data()
    write_group_files(grouped_results)


# このブロックではスクリプトが直接実行された場合のみmain関数を呼び出します。
if __name__ == "__main__":
    main()
