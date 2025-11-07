# -*- coding: utf-8 -*-
"""
目的：
- JP\bin\CharGemAttrType.json と JP\bin\CharGemAttrValue.json を読み、
  ① パラメータ種類（全34想定）の一覧テーブル
  ② 各パラメータの「取りうる値」と「対応レアリティ（最大4段階）」のテーブル
  を作成・保存する。

入力（相対パス）：
  JP\bin\CharGemAttrType.json
  JP\bin\CharGemAttrValue.json

出力（カレントディレクトリに保存）：
  gem_param_types_list.csv          … パラメータ種類の一覧
  gem_param_values_rarity.csv       … 値×レアリティ（＋サブタイプ）一覧
  gem_param_values_rarity_by_param/ … パラメータごとにCSVを分割保存（任意でON/OFF可）
"""

import os
import json
import csv

# ------------------------------------------------------------
# 1) 入力ファイルのパス設定（相対パスのまま）
#    ※ スクリプトを実行するカレントディレクトリからの相対です。
# ------------------------------------------------------------
PATH_ATTR_TYPE = os.path.join("JP", "bin", "CharGemAttrType.json")
PATH_ATTR_VALUE = os.path.join("JP", "bin", "CharGemAttrValue.json")

# ------------------------------------------------------------
# 2) JSONを読み込む関数（エラー時はメッセージを出して終了）
# ------------------------------------------------------------


def load_json(path: str):
    # ファイルを開いてJSONとして読み込みます
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


try:
    attr_type = load_json(PATH_ATTR_TYPE)   # パラメータ種類マスタ
    attr_value = load_json(PATH_ATTR_VALUE)  # 値×レアリティ一覧
except FileNotFoundError as e:
    raise SystemExit(
        f"入力ファイルが見つかりません: {e.filename}\n相対パスの位置と作業ディレクトリを確認してください。")
except json.JSONDecodeError as e:
    raise SystemExit(f"JSONの読み込みに失敗しました: {e}")

# ------------------------------------------------------------
# 3) 数値っぽい文字列を数値に直す小さな関数
#    （例: "105" → 105, "0.04" → 0.04、失敗したら元の文字列のまま）
# ------------------------------------------------------------


def parse_numeric(v):
    # すでに数値ならそのまま返す
    if isinstance(v, (int, float)):
        return v
    # 文字列であれば、整数/小数の順に変換を試みる
    if isinstance(v, str):
        s = v.strip()
        # 整数（先頭が-の負数も考慮）
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            try:
                return int(s)
            except Exception:
                pass
        # 小数（0.04 など）
        try:
            return float(s)
        except Exception:
            return v
    # それ以外の型はそのまま
    return v


# ------------------------------------------------------------
# 4) ① パラメータ種類の一覧を作る
#    - AttrTypeId / GroupId / AttrType名（原文）をテーブル化
#    - 想定上 34 種類だが、実データ数はこの段階で検証可能
# ------------------------------------------------------------
param_types_rows = []         # CSVへ書き出す行のリスト
attr_id_to_name = {}         # 後段で名前参照するための辞書
for rec in attr_type.values():
    aid = int(rec.get("Id"))
    g = rec.get("GroupId")
    nm = str(rec.get("AttrType"))
    param_types_rows.append({
        "AttrTypeId": aid,
        "GroupId": g,
        "AttrTypeName_raw": nm,  # 原文（おそらく中国語ベース）
    })
    attr_id_to_name[aid] = nm

# AttrTypeId 昇順で並べる（見やすさのため）
param_types_rows.sort(key=lambda r: r["AttrTypeId"])

# ------------------------------------------------------------
# 5) ② 値×レアリティの表を作る
#    - 各レコードは AttrTypeId に属する 1 つの候補値（Value）とその Rarity
#    - Subtype（First/Second）も残しておくと分析に有用
# ------------------------------------------------------------
values_rarity_rows = []
for rec in attr_value.values():
    aid = int(rec.get("AttrType"))
    val = parse_numeric(rec.get("Value"))
    rar = rec.get("Rarity")  # 1～4想定
    sub1 = rec.get("AttrTypeFirstSubtype")
    sub2 = rec.get("AttrTypeSecondSubtype")
    values_rarity_rows.append({
        "AttrTypeId": aid,
        "AttrTypeName_raw": attr_id_to_name.get(aid, f"(Unknown:{aid})"),
        "Value": val,
        "Rarity": rar,
        "Subtype1": sub1,
        "Subtype2": sub2,
    })

# 並び順： AttrTypeId → Rarity → Value（文字列/数値混在でも安定するように文字列化キーも併用）


def sort_key(row):
    v = row["Value"]
    # 型の違いがあっても安定するよう、(型優先, 文字列表現) のタプルに
    if isinstance(v, (int, float)):
        vkey = (0, str(v))
    else:
        vkey = (1, str(v))
    return (row["AttrTypeId"], row.get("Rarity", 0) or 0, vkey)


values_rarity_rows.sort(key=sort_key)

# ------------------------------------------------------------
# 6) CSVに保存（UTF-8 / BOMなし）
# ------------------------------------------------------------
OUT_TYPES_CSV = "gem_param_types_list.csv"
OUT_VALUES_CSV = "gem_param_values_rarity.csv"

with open(OUT_TYPES_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=["AttrTypeId", "GroupId", "AttrTypeName_raw"])
    writer.writeheader()
    writer.writerows(param_types_rows)

with open(OUT_VALUES_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
                            "AttrTypeId", "AttrTypeName_raw", "Value", "Rarity", "Subtype1", "Subtype2"])
    writer.writeheader()
    writer.writerows(values_rarity_rows)

# ------------------------------------------------------------
# 7) （任意）パラメータごとにファイルを分けて保存したい場合の処理
#    - True にすると、gem_param_values_rarity_by_param/ 配下に AttrTypeIdごとCSVを出力
#    - 後から見返すときに便利です
# ------------------------------------------------------------
SPLIT_BY_PARAM = True
if SPLIT_BY_PARAM:
    out_dir = "gem_param_values_rarity_by_param"
    os.makedirs(out_dir, exist_ok=True)
    # AttrTypeIdごとに抽出して保存
    current_id = None
    bucket = []

    def flush_bucket(aid, rows):
        if not rows:
            return
        path = os.path.join(out_dir, f"attr_{aid:03d}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                                    "AttrTypeId", "AttrTypeName_raw", "Value", "Rarity", "Subtype1", "Subtype2"])
            writer.writeheader()
            writer.writerows(rows)

    for row in values_rarity_rows:
        aid = row["AttrTypeId"]
        if current_id is None:
            current_id = aid
            bucket = [row]
        elif aid == current_id:
            bucket.append(row)
        else:
            flush_bucket(current_id, bucket)
            current_id = aid
            bucket = [row]
    # 最後のひとかたまりを出力
    flush_bucket(current_id, bucket)

# ------------------------------------------------------------
# 8) コンソールに簡易サマリを出す（件数確認など）
# ------------------------------------------------------------
unique_param_count = len({r["AttrTypeId"] for r in param_types_rows})
print("✅ 出力が完了しました。")
print(f"- パラメータ種類の推定件数: {unique_param_count} 種類（想定: 34）")
print(f"- 一覧CSV: {os.path.abspath(OUT_TYPES_CSV)}")
print(f"- 値×レアリティCSV: {os.path.abspath(OUT_VALUES_CSV)}")
print(f"- 分割CSVディレクトリ: {os.path.abspath('gem_param_values_rarity_by_param')}")
