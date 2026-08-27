#!/usr/bin/env bash
# BHO 萬聖節黑貓 IP → 一套 match3 遊戲美術
#
# 參考圖：BHO_Halloween/bho045.png — 萬聖節賀圖：粗墨線 + 白色貼紙描邊、
#         深灰紫底、奶油黃星星、南瓜橘，spooky-cute
# 產出  ：generated_art/$RUN/sprites/  (5 基本元素 + 5 道具 + 棋盤背景)
#         generated_art/$RUN/generated_sprites.png  (整組聯絡表，一眼檢查一致性)
#
# 用法：
#   bash scripts/gen_bho_halloween_art.sh --dry-run   # 只看 prompt / 目標，不呼叫 API
#   bash scripts/gen_bho_halloween_art.sh             # 正式生成
#   bash scripts/gen_bho_halloween_art.sh --force     # 連已 pass 的也重生
#   RUN=bho_v2 MAX_ITERS=5 bash scripts/gen_bho_halloween_art.sh
#
# 生成後套進遊戲：
#   .venv/bin/python scripts/ai_art_gen.py apply --run bho_halloween
#   遊戲網址加 ?theme=bho_halloween（頭像會自動換成 bho008~012 的骷髏裝貓）

set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
RUN="${RUN:-bho_halloween}"
REF="${REF:-BHO_Halloween/bho045.png}"
MAX_ITERS="${MAX_ITERS:-4}"

# 這個 IP 一樣靠手繪墨線，放行 pipeline 的「禁止外框線」硬規則
export ART_ALLOW_OUTLINE=1

[[ -x "$PY" ]] || { echo "找不到 python: $PY (先建 .venv 或用 PY=python3)" >&2; exit 1; }
[[ -f "$REF" ]] || { echo "找不到參考圖: $REF" >&2; exit 1; }

# 畫風：鎖 bho045 的線條與色票（色票為目測近似值）。
# 參考圖的白色貼紙描邊被 pipeline 硬規則禁止（去背後白邊會浮在深色棋盤上也不好看），
# 改用粗墨線收邊；貼紙感由平塗色塊 + 色票承載。
# 刻意不用綠色系：色相 ~140° 落在綠幕 chromakey 區間，會被去背吃掉。
STYLE="Hand-drawn 2D Halloween sticker illustration in the BHO black-cat IP style. \
Use a BOLD hand-inked black outline (#131313) around every shape — brush-pen quality with \
slightly wobbly, uneven, varying line weight, never a uniform vector stroke. \
Use completely FLAT fills with no gradients and no rendered 3D shading; depth comes only from \
black shape blocking and the ink line. \
Lock the palette to spooky-cute Halloween tones taken from the reference: off-white (#F5F0E8), \
solid ink black (#131313), warm cream yellow (#F2D492), pumpkin orange (#E8833A) and muted \
brick red (#C94F3D), with dusty gray-purple (#575061) only as a shadow/secondary tone. \
Avoid green hues entirely. \
Keep shapes chunky, rounded and simple with very little interior detail; the only texture allowed \
is short black tick marks or thin hatching lines. Keep it playful-spooky and cute, never scary or \
gory, as if drawn by the same artist as the reference Halloween card. \
Do NOT add a white sticker border, paper die-cut frame, halo, glow or drop shadow around the \
subject — the black ink line IS the edge."

# 主題：不畫臉(pipeline 全域禁止五官)，用萬聖節小物承載氛圍
THEME="BHO 黑貓 IP 的萬聖節世界觀 — 例如南瓜燈(無臉純南瓜)、幽靈床單(無臉)、蝙蝠剪影、\
糖果、藥水瓶、骨頭、蜘蛛網、女巫帽、掃帚、大釜、星星。每個物件都要看起來像同一張萬聖節賀卡 \
裡的手繪貼紙，簡單、可愛、帶點搗蛋氣氛，一眼看得懂；不要出現任何臉或五官，不要血腥恐怖元素。"

ASSETS="Red,Grn,Blu,Yel,Pur,Soda0d,Soda90,TNT,LtBl,TrPr,board_bg"

echo "== BHO Halloween match3 art =="
echo "run       : $RUN"
echo "reference : $REF"
echo "assets    : $ASSETS"
echo

"$PY" scripts/ai_art_gen.py generate \
  --mode theme-swap \
  --style "$STYLE" \
  --theme "$THEME" \
  --style-image "$REF" \
  --run "$RUN" \
  --max-iters "$MAX_ITERS" \
  "$@"

echo
echo "產出: generated_art/$RUN/sprites/"
echo "檢查: open generated_art/$RUN/generated_sprites.png"
echo "套用: $PY scripts/ai_art_gen.py apply --run $RUN"
