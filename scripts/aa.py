# -*- coding: utf-8 -*-
"""
Param設定スキャナ（テスト用）
------------------------------------
目的：
- JP/bin の主要データ（Skill / Word / Potential / Talent）から Param1..Param15 を走査し、
  "BuffValue,NoLevel,4021,Time,10K" のような「設定文」を一覧抽出する。

出力：
- 標準出力：抽出行の一覧（必要に応じて要約）
- --export-csv: CSVに保存
- --unique: 設定文の重複排除（同一文言は1行に）

便利オプション：
- --filter-table BuffValue  などで、先頭トークン（テーブル名）による絞り込み
- --print-sample 20         最初のN件だけ表示（CSVはフル）
- --summary                  コンソール末尾に集計を出す（Container × Table）

注意：
- 既存リポジトリ構造（このファイルの親の親がリポジトリルート）を想定。
- 解析対象の「Param〇」は「カンマ区切りの文字列」だけを抽出対象にします（= 設定文の体裁）。
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# =========================
# 基本設定・ユーティリティ
# =========================

# リポジトリのルート推定（scripts/ から見て上へ2つ）
BASE_DIR = Path(__file__).resolve().parents[1]

# JSONキャッシュ（同じファイルを何度も読まない）
_JSON_CACHE: Dict[Path, Any] = {}


def load_json(path: Path) -> Any:
    """JSONを読み込む。失敗時は例外のまま上げる。"""
    if path not in _JSON_CACHE:
        with path.open(encoding="utf-8") as f:
            _JSON_CACHE[path] = json.load(f)
    return _JSON_CACHE[path]


def is_param_setting_text(value: Any) -> bool:
    """
    「Param設定っぽい」文字列かを判定する簡易ルール。
    - 文字列である
    - カンマを含む（"BuffValue,NoLevel,4021,Time,10K" 等）
    """
    return isinstance(value, str) and ("," in value)

# =========================
# 対象データのロード
# =========================


def load_sources() -> Dict[str, Dict[str, Any]]:
    """必要な bin JSON を辞書で返す。"""
    return {
        "Skill": load_json(BASE_DIR / "JP" / "bin" / "Skill.json"),
        "Word": load_json(BASE_DIR / "JP" / "bin" / "Word.json"),
        "Potential": load_json(BASE_DIR / "JP" / "bin" / "Potential.json"),
        "Talent": load_json(BASE_DIR / "JP" / "bin" / "Talent.json"),
        # 必要になればここに他のbinを追加（Character/TalentGroup/… は通常 Param を持たない）
    }

# =========================
# 抽出ロジック
# =========================


PARAM_KEYS = [f"Param{i}" for i in range(1, 16)]  # Param1..Param15


def extract_params_from_container(
    container_name: str,
    data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    1つのコンテナ（Skill/Word/Potential/Talent）から Param設定を抽出する。
    返す各行の形：
    {
      "Container": "Skill",
      "OwnerId": "14410000",
      "OwnerName": "<可能ならName/Titleなど>",
      "ParamKey": "Param1",
      "ParamText": "BuffValue,NoLevel,4021,Time,10K",
      "Table": "BuffValue",
      "Mode": "NoLevel",
      "Identifier": "4021",
      "Extras": "Time,10K"
    }
    """
    rows: List[Dict[str, Any]] = []

    # data は { "id文字列": { ... }, ... } 形式を想定
    for owner_id_str, entry in data.items():
        # 所有者の表示名を拾えそうなら拾う（Word: Title, Skill: Title等）
        owner_name = None
        # binの中身は多言語キーではないため、ここでは Name/Title があれば使用
        for key in ("Name", "Title"):
            if isinstance(entry.get(key), str):
                owner_name = entry.get(key)
                break

        for pkey in PARAM_KEYS:
            if pkey in entry and is_param_setting_text(entry[pkey]):
                param_text = entry[pkey]
                # カンマで分割して Table/Mode/Identifier/Extras を粗く分解
                parts = param_text.split(",")
                table = parts[0].strip() if len(parts) > 0 else ""
                mode = parts[1].strip() if len(parts) > 1 else ""
                identifier = parts[2].strip() if len(parts) > 2 else ""
                extras = ",".join(part.strip()
                                  for part in parts[3:]) if len(parts) > 3 else ""

                rows.append({
                    "Container": container_name,
                    "OwnerId": owner_id_str,
                    "OwnerName": owner_name or "",
                    "ParamKey": pkey,
                    "ParamText": param_text,
                    "Table": table,
                    "Mode": mode,
                    "Identifier": identifier,
                    "Extras": extras,
                })

    return rows


def extract_all(
    sources: Dict[str, Dict[str, Any]],
    filter_table: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """すべての対象コンテナから Param設定を集めて、一つのリストにまとめる。"""
    all_rows: List[Dict[str, Any]] = []
    for name, data in sources.items():
        rows = extract_params_from_container(name, data)
        if filter_table:
            rows = [r for r in rows if r.get("Table") == filter_table]
        all_rows.extend(rows)
    return all_rows

# =========================
# 出力（CSV / プリント / 集計）
# =========================


CSV_FIELDS = [
    "Container", "OwnerId", "OwnerName",
    "ParamKey", "ParamText",
    "Table", "Mode", "Identifier", "Extras",
]


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    """抽出結果をCSVに保存。"""
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})


def print_rows(rows: List[Dict[str, Any]], limit: Optional[int] = None) -> None:
    """抽出行を見やすくプリント（limit指定で先頭N件だけ）。"""
    count = 0
    for r in rows:
        if limit is not None and count >= limit:
            break
        count += 1
        print(
            f"[{r['Container']}] "
            f"{r['OwnerId']:<10} {r['OwnerName'] or '-':<20} "
            f"{r['ParamKey']}: {r['ParamText']}"
        )
    print(f"\n表示件数: {min(count, len(rows))} / 総件数: {len(rows)}")


def summarize(rows: List[Dict[str, Any]]) -> None:
    """Container × Table で件数サマリを表示。"""
    from collections import defaultdict
    agg: Dict[Tuple[str, str], int] = defaultdict(int)
    for r in rows:
        agg[(r.get("Container", ""), r.get("Table", ""))] += 1

    print("\n=== Summary: Container × Table ===")
    for (container, table), cnt in sorted(agg.items()):
        print(f"{container:<10}  {table or '-':<15}  {cnt:>5}")

# =========================
# メイン（引数処理）
# =========================


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を定義する。"""
    p = argparse.ArgumentParser(description="Param設定の抽出テストツール")
    p.add_argument("--export-csv", type=str, default="",
                   help="CSV出力パス（例: ./param_settings.csv）")
    p.add_argument("--unique", action="store_true",
                   help="ParamText（設定文）の重複を排除して出力する")
    p.add_argument("--filter-table", type=str, default="",
                   help="先頭トークン（Table名）でフィルタ（例: BuffValue / EffectValue / HitDamage など）")
    p.add_argument("--print-sample", type=int, default=50,
                   help="コンソールに表示する最大行数（CSVはフル）")
    p.add_argument("--summary", action="store_true",
                   help="末尾に Container×Table の件数サマリを表示する")
    return p.parse_args()


def main() -> None:
    """エントリーポイント：抽出→表示/CSV→要約の流れ。"""
    args = parse_args()

    # データ読み込み
    sources = load_sources()

    # 抽出
    rows = extract_all(sources, filter_table=(args.filter_table or None))

    # 重複排除（ParamText基準）
    if args.unique:
        seen = set()
        uniq_rows: List[Dict[str, Any]] = []
        for r in rows:
            key = r["ParamText"]
            if key in seen:
                continue
            seen.add(key)
            uniq_rows.append(r)
        rows = uniq_rows

    # 表示
    print_rows(rows, limit=args.print_sample)

    # CSV保存（指定があれば）
    if args.export_csv:
        out_path = Path(args.export_csv)
        write_csv(out_path, rows)
        print(f"\nCSVを書き出しました: {out_path.resolve()}")

    # サマリ（指定があれば）
    if args.summary:
        summarize(rows)


if __name__ == "__main__":
    main()
