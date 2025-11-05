#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HitDamage.json の levelTypeData と LevelData の組み合わせを調べるテスト用スクリプト。

・どの値の組み合わせがあるか（有無も含む）を集計して一覧表示します
・SkillId の有無との掛け合わせの内訳も出します
・各組み合わせのサンプル ID（最大 N 件）を表示します
・必要なら CSV にエクスポートできます
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Iterable


# ------------------------------
# ユーティリティ：JSON ロード
# ------------------------------
def load_json(path: Path) -> Any:
    """JSON ファイルを読み込みます。エンコーディングは UTF-8 前提です。"""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------
# 安全にキーを取り出すヘルパ
# ------------------------------
def get_first_present(d: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    """
    複数の候補キーのうち、最初に存在したキーの値を返します。
    見つからなければ None。
    """
    for k in keys:
        if k in d:
            return d[k]
    return None


# ------------------------------
# メインの集計処理
# ------------------------------
def analyze_hitdamage(
    base_dir: Path,
    top_samples: int = 5,
) -> Dict[str, Any]:
    """
    JP/bin/HitDamage.json を読み込み、levelTypeData/LevelData/SkillId の組み合わせを集計します。
    戻り値は、画面表示と CSV 出力に使うための辞書です。
    """
    # 1) ファイルパスを決定します
    hitdamage_path = base_dir / "JP" / "bin" / "HitDamage.json"

    # 2) JSON を読み込みます
    data: Dict[str, Dict[str, Any]] = load_json(hitdamage_path)

    # 3) 集計用の辞書を用意します
    #    combo -> {"count": n, "ids": [...], "skillId_present_count": x, "skillId_absent_count": y}
    #    combo は (levelTypeData or None, LevelData or None) のタプルにします
    combo_stats: Dict[Tuple[Optional[int], Optional[int]], Dict[str, Any]] = {}

    # 4) 全件ループして集計します
    total = 0
    missing_ltd = 0  # levelTypeData が無い件数
    missing_ld = 0   # LevelData が無い件数
    for key, entry in data.items():
        total += 1

        # 大文字小文字や表記揺れに備えて複数候補を見ます
        level_type_val = get_first_present(
            entry, ("levelTypeData", "LevelTypeData", "LevelType"))
        # 数値以外が来る可能性に備えて int にできるならします
        try:
            level_type_val = int(
                level_type_val) if level_type_val is not None else None
        except Exception:
            # 変換できなかったらそのまま None 扱い
            level_type_val = None

        level_data_val = get_first_present(
            entry, ("LevelData", "LevelId", "LevelID"))
        try:
            level_data_val = int(
                level_data_val) if level_data_val is not None else None
        except Exception:
            level_data_val = None

        skill_id_val = get_first_present(
            entry, ("SkillId", "skillId", "skillID"))
        try:
            skill_id_val = int(
                skill_id_val) if skill_id_val is not None else None
        except Exception:
            skill_id_val = None

        if level_type_val is None:
            missing_ltd += 1
        if level_data_val is None:
            missing_ld += 1

        combo = (level_type_val, level_data_val)
        stat = combo_stats.setdefault(
            combo,
            {
                "count": 0,
                "ids": [],  # サンプルIDを格納（最大 top_samples 件）
                "skillId_present": 0,
                "skillId_absent": 0,
                # 参考情報（最初に見つかった例の一部を覚えておく）
                "first_hit": {
                    "Id": entry.get("Id", key),
                    "HitdamageInfo": entry.get("HitdamageInfo"),
                    "SkillSlotType": entry.get("SkillSlotType"),
                },
            },
        )
        stat["count"] += 1
        if skill_id_val is not None:
            stat["skillId_present"] += 1
        else:
            stat["skillId_absent"] += 1

        # サンプルIDの保存（多すぎると重くなるので先頭 N 件まで）
        if len(stat["ids"]) < top_samples:
            stat["ids"].append(int(entry.get("Id", key)))

    # 5) 結果のまとめを返します
    return {
        "total": total,
        "missing_levelTypeData": missing_ltd,
        "missing_LevelData": missing_ld,
        "top_samples": top_samples,
        "combo_stats": combo_stats,  # 後で表示・CSV用に使います
    }


# ------------------------------
# 画面表示（人間向け）
# ------------------------------
def print_report(report: Dict[str, Any]) -> None:
    """コンソールに読みやすい形で結果を表示します。"""
    total = report["total"]
    missing_ltd = report["missing_levelTypeData"]
    missing_ld = report["missing_LevelData"]
    top_samples = report["top_samples"]
    combo_stats: Dict[Tuple[Optional[int], Optional[int]],
                      Dict[str, Any]] = report["combo_stats"]

    # ヘッダ
    print("=== HitDamage: levelTypeData × LevelData 組み合わせレポート ===")
    print(f"総件数: {total}")
    print(f"levelTypeData 欠落: {missing_ltd} 件")
    print(f"LevelData 欠落   : {missing_ld} 件")
    print()

    # コンボをソートして表示（levelTypeData 昇順、LevelData 昇順、None は後ろ）
    def sort_key(item):
        (ltd, ld), stat = item
        # None を大きく扱うための置換
        ltd_sort = (1, 10**9) if ltd is None else (0, ltd)
        ld_sort = (1, 10**9) if ld is None else (0, ld)
        return (ltd_sort, ld_sort)

    sorted_items = sorted(combo_stats.items(), key=sort_key)

    for (ltd, ld), stat in sorted_items:
        cnt = stat["count"]
        p = (cnt / total * 100.0) if total > 0 else 0.0
        skill_yes = stat["skillId_present"]
        skill_no = stat["skillId_absent"]
        first = stat["first_hit"]
        ids = ", ".join(str(x) for x in stat["ids"])

        print(f"- levelTypeData={ltd} / LevelData={ld} : {cnt} 件 ({p:.2f}%)")
        print(f"    SkillIdあり: {skill_yes} 件 / なし: {skill_no} 件")
        print(f"    例（最大 {top_samples} 件の Id）: {ids if ids else '(なし)'}")
        print(
            f"    代表例: Id={first.get('Id')} / Info={first.get('HitdamageInfo')} / SkillSlotType={first.get('SkillSlotType')}")
        print()

    # levelTypeData または LevelData が欠けている ID を見たい場合は、
    # ここで追加スキャンして表示することもできます（必要であれば追記してください）。


# ------------------------------
# CSV エクスポート
# ------------------------------
def export_csv(report: Dict[str, Any], csv_path: Path) -> None:
    """組み合わせの集計を CSV に書き出します。"""
    combo_stats: Dict[Tuple[Optional[int], Optional[int]],
                      Dict[str, Any]] = report["combo_stats"]
    total = report["total"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "levelTypeData",
            "LevelData",
            "count",
            "ratio_percent",
            "skillId_present",
            "skillId_absent",
            "sample_ids",
            "first_Id",
            "first_HitdamageInfo",
            "first_SkillSlotType",
        ])
        for (ltd, ld), stat in combo_stats.items():
            cnt = stat["count"]
            p = (cnt / total * 100.0) if total > 0 else 0.0
            writer.writerow([
                ltd,
                ld,
                cnt,
                f"{p:.2f}",
                stat["skillId_present"],
                stat["skillId_absent"],
                " ".join(str(x) for x in stat["ids"]),
                stat["first_hit"].get("Id"),
                stat["first_hit"].get("HitdamageInfo"),
                stat["first_hit"].get("SkillSlotType"),
            ])


# ------------------------------
# エントリポイント
# ------------------------------
def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解釈します。"""
    parser = argparse.ArgumentParser(
        description="HitDamage の levelTypeData × LevelData を調べるテスト")
    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="リポジトリのルートディレクトリ（JP/ が直下にある場所）。デフォルトは現在ディレクトリ。",
    )
    parser.add_argument(
        "--top-samples",
        type=int,
        default=5,
        help="各組み合わせで表示する Id のサンプル件数（多すぎると表示が長くなります）。",
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        default=None,
        help="CSV を書き出すパス。未指定なら書き出しません。",
    )
    return parser.parse_args()


def main() -> None:
    """メイン関数。集計→表示→（必要なら）CSV 出力を行います。"""
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()

    # 集計を実行
    report = analyze_hitdamage(base_dir=base_dir, top_samples=args.top_samples)

    # コンソールへレポート表示
    print_report(report)

    # CSV が指定されていれば出力
    if args.export_csv:
        csv_path = Path(args.export_csv).resolve()
        export_csv(report, csv_path)
        print(f"\nCSV を出力しました: {csv_path}")


if __name__ == "__main__":
    main()
