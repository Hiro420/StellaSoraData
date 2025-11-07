# -*- coding: utf-8 -*-
"""
目的：
 全Gemパラメータ（34種類）について
 ----------- 出力内容 -----------
 1列目：パラメータ名 (AttrType)
 2列目：Position1で取得可能なら "○"
 3列目：Position2で取得可能なら "○"
 4列目：Position3で取得可能なら "○"
 5列目：レアリティ4で取りうる値（複数あればカンマ区切り）
 6列目：レアリティ3で取りうる値（複数あればカンマ区切り）
 7列目：レアリティ2で取りうる値
 8列目：レアリティ1で取りうる値
--------------------------------
読み込むファイル（相対パス）：
  JP\bin\CharGemAttrType.json
  JP\bin\CharGemAttrGroup.json
  JP\bin\CharGemAttrValue.json
  JP\bin\CharGemSlotControl.json
出力：
  gem_parameter_table.csv
"""

import os
import json
import csv

# ----------------------------------------------
# JSON を読み込む関数
# ----------------------------------------------


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------
# 相対パス指定（ユーザー指定通り）
# ----------------------------------------------
PATH_TYPE = os.path.join("JP", "bin", "CharGemAttrType.json")
PATH_GROUP = os.path.join("JP", "bin", "CharGemAttrGroup.json")
PATH_VALUE = os.path.join("JP", "bin", "CharGemAttrValue.json")
PATH_SLOT = os.path.join("JP", "bin", "CharGemSlotControl.json")

# JSON読み込み
attr_types = load_json(PATH_TYPE)
attr_groups = load_json(PATH_GROUP)
attr_values = load_json(PATH_VALUE)
slotctrl = load_json(PATH_SLOT)

# ----------------------------------------------
# SlotControl (Position1,2,3) → グループ一覧を取得
# ----------------------------------------------
position_to_groups = {}  # {Position番号: [GroupId,...]}

for slot in slotctrl.values():
    pos = slot.get("Position", 1)   # Positionが無いものは1とみなす（初期スロット）
    groups = slot.get("AttrGroupId", [])
    position_to_groups.setdefault(pos, [])
    position_to_groups[pos].extend(groups)

# ----------------------------------------------
# グループID → AttrTypeId一覧に変換
# ----------------------------------------------
group_to_attrtypes = {}  # {GroupId: [AttrTypeId,...]}

for group in attr_groups.values():
    gid = group["GroupId"]
    attrs = group.get("AttrType", [])  # グループ内のパラメータID
    group_to_attrtypes[gid] = attrs

# ----------------------------------------------
# パラメータごとの "○" 判定を作成する
# ----------------------------------------------
param_position_flag = {}  # {AttrTypeId: {pos1: bool, pos2: bool, pos3: bool}}

for pos in [1, 2, 3]:
    groups = position_to_groups.get(pos, [])
    for grp in groups:
        for aid in group_to_attrtypes.get(grp, []):
            param_position_flag.setdefault(aid, {1: False, 2: False, 3: False})
            param_position_flag[aid][pos] = True

# ----------------------------------------------
# レアリティごとの値を収集する
# ----------------------------------------------
param_values = {}  # {AttrTypeId: {rarity: [values,...]}}

for rec in attr_values.values():
    aid = int(rec["AttrType"])
    val = rec["Value"]
    rar = int(rec["Rarity"])

    param_values.setdefault(aid, {})
    param_values[aid].setdefault(rar, [])

    # 値が文字列ならそのまま、数値文字列なら変換
    try:
        val = float(val) if "." in val else int(val)
    except:
        pass

    param_values[aid][rar].append(val)

# ----------------------------------------------
# テーブル出力用CSV生成
# ----------------------------------------------
OUTPUT_CSV = "gem_parameter_table.csv"

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Parameter", "Pos1", "Pos2", "Pos3",
                     "Rarity4", "Rarity3", "Rarity2", "Rarity1"])

    # AttrTypeId昇順で処理
    for aid in sorted(attr_types.keys(), key=lambda x: int(x)):
        rec = attr_types[str(aid)]
        pname = rec["AttrType"]  # JSONの値そのまま使用

        posflag = param_position_flag.get(
            int(aid), {1: False, 2: False, 3: False})

        def val_to_str(rarity):
            vals = param_values.get(int(aid), {}).get(rarity, [])
            return ",".join(str(v) for v in vals)

        writer.writerow([
            pname,
            "○" if posflag.get(1) else "",
            "○" if posflag.get(2) else "",
            "○" if posflag.get(3) else "",
            val_to_str(4),
            val_to_str(3),
            val_to_str(2),
            val_to_str(1)
        ])

print("\n✅ 出力完了： gem_parameter_table.csv を生成しました。")
