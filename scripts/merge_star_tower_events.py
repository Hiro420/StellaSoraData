"""Star Tower event data merger."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


# この関数では、指定されたパスからJSONファイルを読み込み、辞書として返します。
def load_json(path: Path) -> Dict[str, object]:
    # 初学者向けに説明すると、with構文を使うとファイルを開いた後の後片付けを自動で行ってくれます。
    with path.open(encoding="utf-8") as file:
        # json.loadを使うことで、JSON形式の文字列をPythonのデータに変換します。
        return json.load(file)


# この関数では、選択肢の説明文から「（50％）」のような確率表示を抜き出します。
def extract_probabilities(option_text: Optional[str]) -> List[float]:
    # 正規表現を使って「（数字％）」の部分だけを取り出します。
    probability_pattern = re.compile(r"（([0-9]+)％）")
    # テキストが無い場合は空のリストを返しておきます。
    if not option_text:
        return []
    # 見つかった数値を順番に取り出し、float型へ変換して保存します。
    values: List[float] = []
    for match in probability_pattern.findall(option_text):
        try:
            values.append(float(match))
        except ValueError:
            # 変換できない場合は無視して次の値を確認します。
            continue
    # 取り出した確率一覧を返します。
    return values


# この関数では、ドロップテーブルの情報を参照してアイテム名を調べる辞書を用意します。
def build_item_name_lookup(item_data: Dict[str, object], item_lang: Dict[str, str]) -> Dict[int, str]:
    # 結果を格納する辞書を作成します。
    names: Dict[int, str] = {}
    # アイテムIDごとに、日本語名があれば辞書へ登録します。
    for item_id in item_data.keys():
        key = f"Item.{item_id}.1"
        if key in item_lang:
            names[int(item_id)] = item_lang[key]
    # 完成した辞書を返します。
    return names


# この関数では、DropPkg.jsonを読みやすい形にまとめ直します。
def build_drop_package_lookup(drop_pkg: Dict[str, Dict[str, object]]) -> Dict[int, List[int]]:
    # PkgIdごとに参照するアイテムIDをまとめる辞書を用意します。
    packages: Dict[int, List[int]] = {}
    for entry in drop_pkg.values():
        pkg_id = entry.get("PkgId")
        item_id = entry.get("ItemId")
        # 型チェックを行い、整数として扱える場合のみ登録します。
        if isinstance(pkg_id, int) and isinstance(item_id, int):
            packages.setdefault(pkg_id, []).append(item_id)
    # まとめ終わった辞書を返します。
    return packages


# この関数では、エフェクトコードごとの意味を簡単な辞書としてまとめます。
def describe_effect(
    effect_code: int,
    parameters: List[int],
    drop_data: Dict[str, Dict[str, object]],
    drop_packages: Dict[int, List[int]],
    item_names: Dict[int, str],
) -> Dict[str, object]:
    # まずはコードと生のパラメータを記録した基本情報を作ります。
    effect_info: Dict[str, object] = {
        "code": effect_code,
        "parameters": parameters,
    }
    # エフェクトごとに内容を追加説明します。
    if effect_code == 1:
        effect_info["type"] = "gain_coin"
        if parameters:
            effect_info["amount"] = parameters[0]
    elif effect_code == 5:
        effect_info["type"] = "spend_coin"
        if parameters:
            effect_info["amount"] = parameters[0]
    elif effect_code == 3:
        effect_info["type"] = "trigger_drop"
        items: List[Dict[str, object]] = []
        drop_id = parameters[0] if parameters else None
        variant = parameters[1] if len(parameters) > 1 else None
        keys_to_try: List[str] = []
        if drop_id is not None:
            if variant is not None:
                specific_key = f"{drop_id}{variant}"
                if specific_key in drop_data:
                    keys_to_try.append(specific_key)
                else:
                    keys_to_try.append(str(drop_id))
            else:
                keys_to_try.append(str(drop_id))
        seen_pkgs: set[int] = set()
        for key in keys_to_try:
            drop_entry = drop_data.get(key)
            if not drop_entry:
                continue
            pkg_id = drop_entry.get("PkgId")
            if isinstance(pkg_id, int) and pkg_id not in seen_pkgs:
                seen_pkgs.add(pkg_id)
                for item_id in drop_packages.get(pkg_id, []):
                    items.append({
                        "item_id": item_id,
                        "item_name": item_names.get(item_id),
                    })
        effect_info["drop_items"] = items
    elif effect_code == 6:
        effect_info["type"] = "modify_hp_or_resource"
        if parameters:
            effect_info["value"] = parameters[0]
    elif effect_code == 14:
        effect_info["type"] = "apply_event_effect"
        if parameters:
            effect_info["target_id"] = parameters[0]
    elif effect_code == 16:
        effect_info["type"] = "trigger_event_message"
        if parameters:
            effect_info["target_id"] = parameters[0]
    elif effect_code == 17:
        effect_info["type"] = "gain_notes_random"
        if parameters:
            effect_info["quantity"] = parameters[0]
        if len(parameters) > 1:
            effect_info["note_type"] = parameters[1]
    elif effect_code == 18:
        effect_info["type"] = "gain_specific_notes"
        if parameters:
            effect_info["note_id"] = parameters[0]
        if len(parameters) > 1:
            effect_info["quantity"] = parameters[1]
    elif effect_code == 19:
        effect_info["type"] = "spend_notes_random"
        if parameters:
            effect_info["quantity"] = parameters[0]
    else:
        effect_info["type"] = "unknown_effect"
    # 補足情報を加えたエフェクト内容を返します。
    return effect_info


# この関数では、指定された規則IDに属する選択肢IDの一覧を集めます。
def collect_option_ids(event_options: Dict[str, object], rule_id: int) -> List[int]:
    # 結果を格納するリストを用意します。
    option_ids: List[int] = []
    for raw_id in event_options.keys():
        try:
            option_id = int(raw_id)
        except ValueError:
            continue
        # 100で割った商が規則IDと一致するものだけを対象にします。
        if option_id // 100 == rule_id:
            option_ids.append(option_id)
    # 昇順に並べ替えて返します。
    return sorted(option_ids)


# この関数では、イベントごとのNPC発言を整理して取得します。
def gather_actions(action_data: Dict[str, str], event_id: int, npc_ids: List[int]) -> List[Dict[str, object]]:
    # 結果を入れる空のリストを用意して、後で順番通りに発言を追加します。
    npc_actions: List[Dict[str, object]] = []
    # それぞれのNPCについて、イベント内で話すセリフをまとめます。
    for npc_id in npc_ids:
        # 各NPCに対応する発言を集めるリストを用意します。
        lines: List[str] = []
        # セリフが複数行になる場合に備えて、連番を1から順に確認します。
        line_index = 1
        while True:
            # JSONのキーは「StarTowerEventAction.<イベントID><NPCID>.<行番号>」という形式なので、それに合わせて文字列を作ります。
            key = f"StarTowerEventAction.{event_id}{npc_id}.{line_index}"
            # 対応するキーがなければ、そのNPCの発言はこれ以上ないと判断します。
            if key not in action_data:
                break
            # セリフが見つかった場合はリストに追加し、次の行を確認します。
            lines.append(action_data[key])
            line_index += 1
        # 一つでもセリフが存在すれば、結果リストにNPC情報として登録します。
        if lines:
            npc_actions.append({
                "npc_id": npc_id,
                "lines": lines,
            })
    # NPC順にまとめた発言リストを返します。
    return npc_actions


# この関数では、イベント内の選択肢テキストを整理して取得します。
def gather_options(option_data: Dict[str, str], event_id: int, npc_ids: List[int]) -> List[Dict[str, object]]:
    # 選択肢ごとの情報を順番通りに保存するリストを準備します。
    collected_options: List[Dict[str, object]] = []
    # 選択肢は「01」「02」のように二桁で管理されているため、1から順に確認します。
    option_index = 1
    while True:
        # このフラグで、今回の選択肢番号に対応するテキストがあったかどうかを確認します。
        found_any = False
        # 各NPCごとにテキストが存在するかを調べ、あればまとめていきます。
        for npc_id in npc_ids:
            # 行単位のテキストを格納するリストを初期化します。
            lines: List[str] = []
            # 選択肢の文章も複数行になる可能性があるため、こちらも連番で確認します。
            line_index = 1
            while True:
                # キーの形式は「StarTowerEventOptionAction.<イベントID><選択肢番号(二桁)><NPCID>.<行番号>」です。
                key = f"StarTowerEventOptionAction.{event_id}{option_index:02d}{npc_id}.{line_index}"
                # テキストが存在しなければ、その組み合わせの行は終わりとみなします。
                if key not in option_data:
                    break
                # 見つかったテキストをリストに追加し、次の行を探します。
                lines.append(option_data[key])
                line_index += 1
            # 一つでもテキストがあれば、今回の選択肢番号として登録します。
            if lines:
                collected_options.append({
                    "option_index": option_index,
                    "npc_id": npc_id,
                    "lines": lines,
                })
                found_any = True
        # 今回の選択肢番号で何も見つからなければ、全ての選択肢を確認し終えたと判断して終了します。
        if not found_any:
            break
        option_index += 1
    # まとめ終わった選択肢リストを返します。
    return collected_options


# この関数では、テーマIDを日本語名称へ変換するための辞書を作成します。
def build_theme_lookup(star_tower_lang: Dict[str, str]) -> Dict[int, str]:
    # 結果を格納する空の辞書を用意し、あとでテーマIDと名称を対応付けます。
    theme_names: Dict[int, str] = {}
    # JSON内のキーは「StarTower.<ID>.<番号>」という形式なので、IDを取り出します。
    for key, value in star_tower_lang.items():
        # 末尾が「.1」のキーだけが名称（タイトル）に対応するため、それ以外は無視します。
        if not key.startswith("StarTower.") or not key.endswith(".1"):
            continue
        # キーをドットで分割し、中央の要素をテーマIDとして取得します。
        _, raw_id, _ = key.split(".")
        # 取得したIDを整数に変換し、名称文字列と紐付けて辞書へ保存します。
        theme_names[int(raw_id)] = value
    # 完成したテーマ名称辞書を呼び出し元へ返します。
    return theme_names


# この関数では、マップIDに対応するシーン情報とテーマ名称をまとめて取得します。
def lookup_map_details(
    map_data: Dict[str, Dict[str, object]],
    theme_names: Dict[int, str],
    map_id: Optional[int],
) -> Dict[str, Optional[str]]:
    # マップIDが未指定の場合は、空欄扱いで結果を返します。
    if map_id is None:
        return {
            "map_scene_resource": None,
            "map_theme_name": None,
        }

    # JSON上では文字列のキーになっているため、事前に文字列へ変換して参照します。
    map_entry = map_data.get(str(map_id))
    # マップ情報が存在しなければ、シーンリソースとテーマ名称の双方を未入力で返します。
    if not map_entry:
        return {
            "map_scene_resource": None,
            "map_theme_name": None,
        }

    # シーンリソースはStarTowerMap.jsonに直接記録されているので、そのまま取り出します。
    scene_res = map_entry.get("SceneRes")
    # テーマ名称はThemeフィールドと先ほどの辞書を使って取得します。
    theme_id = map_entry.get("Theme")
    theme_name = theme_names.get(int(theme_id)) if isinstance(theme_id, int) else None

    # 取得した情報を分かりやすい辞書にまとめて返します。
    return {
        "map_scene_resource": scene_res,
        "map_theme_name": theme_name,
    }


# プログラムのメイン処理をまとめた関数です。
def main() -> None:
    # スクリプトファイルの場所から見たときのリポジトリ直下のパスを求めます。
    repo_root = Path(__file__).resolve().parents[1]
    # 必要なJSONファイルのパスを丁寧に指定します。
    event_path = repo_root / "JP" / "bin" / "StarTowerEvent.json"
    action_path = repo_root / "JP" / "language" / "ja_JP" / "StarTowerEventAction.json"
    option_path = repo_root / "JP" / "language" / "ja_JP" / "StarTowerEventOptionAction.json"
    map_path = repo_root / "JP" / "bin" / "StarTowerMap.json"
    star_tower_lang_path = repo_root / "JP" / "language" / "ja_JP" / "StarTower.json"
    event_options_path = repo_root / "JP" / "bin" / "EventOptions.json"
    event_options_lang_path = repo_root / "JP" / "language" / "ja_JP" / "EventOptions.json"
    event_result_path = repo_root / "JP" / "bin" / "EventResult.json"
    drop_path = repo_root / "JP" / "bin" / "Drop.json"
    drop_pkg_path = repo_root / "JP" / "bin" / "DropPkg.json"
    item_path = repo_root / "JP" / "bin" / "Item.json"
    item_lang_path = repo_root / "JP" / "language" / "ja_JP" / "Item.json"
    # 出力先のファイルパスを指定し、後でJSONとして書き出します。
    output_path = repo_root / "JP" / "StarTowerEventsCombined.json"

    # 先ほど用意した関数を使って、各JSONファイルを読み込みます。
    event_data = load_json(event_path)
    action_data = load_json(action_path)
    option_data = load_json(option_path)
    map_data = load_json(map_path)
    star_tower_lang = load_json(star_tower_lang_path)
    event_options = load_json(event_options_path)
    event_options_lang = load_json(event_options_lang_path)
    event_results = load_json(event_result_path)
    drop_data = load_json(drop_path)
    drop_pkg_data = load_json(drop_pkg_path)
    item_data = load_json(item_path)
    item_lang = load_json(item_lang_path)

    # テーマ名称を取得するための辞書を作成します。
    theme_names = build_theme_lookup(star_tower_lang)
    # ドロップ用の辞書を作成して、後で報酬の詳細を補完できるようにします。
    drop_packages = build_drop_package_lookup(drop_pkg_data)
    item_names = build_item_name_lookup(item_data, item_lang)
    # 選択肢IDごとに結果IDをまとめておきます。
    results_by_option: Dict[int, List[int]] = {}
    for raw_id, result in event_results.items():
        try:
            result_id = int(raw_id)
        except ValueError:
            continue
        option_id = result_id // 100
        results_by_option.setdefault(option_id, []).append(result_id)
    for option_id in results_by_option:
        results_by_option[option_id].sort()

    # まとめた結果を格納するリストを用意します。
    merged_events: List[Dict[str, object]] = []

    # イベントはID順で並べると確認しやすいため、数値に変換した順番で処理します。
    for event_key in sorted(event_data.keys(), key=lambda value: int(value)):
        # 現在のイベント情報を取り出し、後の処理で使いやすいようにします。
        event = event_data[event_key]
        event_id = int(event["Id"])
        npc_ids = event.get("RelatedNPCs", [])

        # イベントに紐づくNPCの発言と選択肢をそれぞれ集めます。
        npc_actions = gather_actions(action_data, event_id, npc_ids)
        npc_options = gather_options(option_data, event_id, npc_ids)

        # マップIDから、シーンリソースとテーマ名称を取得します。
        map_details = lookup_map_details(map_data, theme_names, event.get("GuaranteedMapId"))

        # 一つのイベントに必要な情報を辞書としてまとめ、結果リストに追加します。
        option_details: List[Dict[str, object]] = []
        option_ids = collect_option_ids(event_options, event.get("OptionsRulesId", 0))
        for option_id in option_ids:
            option_text = event_options_lang.get(f"EventOptions.{option_id}.1")
            probabilities = extract_probabilities(option_text)
            results_for_option = results_by_option.get(option_id, [])
            option_entry: Dict[str, object] = {
                "option_id": option_id,
                "option_index": option_id % 100,
                "text": option_text,
                "results": [],
            }
            for index, result_id in enumerate(results_for_option):
                result_entry = event_results.get(str(result_id), {})
                result_details: Dict[str, object] = {
                    "result_id": result_id,
                    "probability_percent": probabilities[index] if index < len(probabilities) else None,
                    "effects": [],
                }
                # Effect1 から順番に存在するものを調べて、一覧へ追加します。
                for effect_index in range(1, 6):
                    effect_key = f"Effect{effect_index}"
                    param_key = f"Parameter{effect_index}"
                    if effect_key not in result_entry:
                        continue
                    effect_code = result_entry[effect_key]
                    params = result_entry.get(param_key, [])
                    if not isinstance(params, list):
                        params = []
                    described = describe_effect(
                        effect_code,
                        params,
                        drop_data,
                        drop_packages,
                        item_names,
                    )
                    result_details["effects"].append(described)
                option_entry["results"].append(result_details)
            option_details.append(option_entry)

        merged_events.append({
            "id": event_id,
            "description": event.get("Desc"),
            "event_type": event.get("EventType"),
            "guaranteed_map_id": event.get("GuaranteedMapId"),
            "guaranteed_map_scene_res": map_details["map_scene_resource"],
            "guaranteed_map_theme": map_details["map_theme_name"],
            "related_npcs": npc_ids,
            "actions": npc_actions,
            "options": npc_options,
            "option_outcomes": option_details,
        })

    # 書き出す際には読みやすいようにインデントを指定し、UTF-8で保存します。
    output_path.write_text(json.dumps(merged_events, ensure_ascii=False, indent=2), encoding="utf-8")


# この記述により、スクリプトを直接実行したときだけmain関数が動くようになります。
if __name__ == "__main__":
    # メインの処理を呼び出します。
    main()
