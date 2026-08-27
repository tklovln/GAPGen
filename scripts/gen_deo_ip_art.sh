#!/usr/bin/env bash
# DEO 黑白貓 IP → 一套 match3 遊戲美術
#
# 參考圖：DEO_emotion/(12 張情緒系列) — 手繪粗墨線、白底黑塊貓、奶油黃、粉頰
# 產出  ：generated_art/$RUN/sprites/  (5 基本元素 + 5 道具 + 棋盤背景)
#         generated_art/$RUN/generated_sprites.png  (整組聯絡表，一眼檢查一致性)
#
# 用法：
#   bash scripts/gen_deo_ip_art.sh --dry-run     # 只看 prompt / 目標，不呼叫 API
#   bash scripts/gen_deo_ip_art.sh               # 正式生成（預設墨線貼紙風）
#   STYLE_PRESET=3d bash scripts/gen_deo_ip_art.sh   # 主流手遊 soft-3D 風（皮克斯質感）
#   bash scripts/gen_deo_ip_art.sh --force       # 連已 pass 的也重生
#   RUN=deo_v2 MAX_ITERS=5 bash scripts/gen_deo_ip_art.sh
#
# 生成後套進遊戲：
#   .venv/bin/python scripts/ai_art_gen.py apply --run deo_cat_ip

set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
STYLE_PRESET="${STYLE_PRESET:-ink}"   # ink=手繪墨線貼紙 | 3d=主流手遊 soft-3D
RUN="${RUN:-$([ "$STYLE_PRESET" = 3d ] && echo deo_cat_3d || echo deo_cat_ip)}"
REF="${REF:-DEO_emotion/DEM01.png}"
MAX_ITERS="${MAX_ITERS:-4}"

[[ -x "$PY" ]] || { echo "找不到 python: $PY (先建 .venv 或用 PY=python3)" >&2; exit 1; }
[[ -f "$REF" ]] || { echo "找不到參考圖: $REF" >&2; exit 1; }

# ---- 風格一 ink：手繪墨線貼紙（原始 DEO IP 風）----
# 這個 IP 的靈魂就是手繪墨線；色票取自 DEO_emotion 的實際像素統計。
# 刻意不放薄荷綠(#A8DCC0)：色相 ~140° 落在綠幕 chromakey 區間，會被去背吃掉。
STYLE_INK="Hand-drawn 2D sticker illustration in the DEO black-and-white cat IP style. \
Use a BOLD hand-inked black outline (#131313) around every shape — brush-pen quality with \
slightly wobbly, uneven, varying line weight, never a uniform vector stroke. \
Use completely FLAT fills with no gradients, no ambient occlusion and no rendered 3D shading; \
depth comes only from black shape blocking and the ink line. \
Lock the palette to paper white (#FFFFFF), solid ink black (#131313), warm cream yellow (#FFDB96) \
and soft blush pink (#FFCDC8), plus one saturated accent hue per asset where gameplay demands it. \
Keep shapes chunky, rounded and simple with very little interior detail; the only texture allowed is \
short black tick marks or thin hatching lines. Keep it cute, calm and stamp-like, as if drawn by the \
same artist as the reference cat brand. \
Do NOT add a white sticker border, paper die-cut frame, halo or drop shadow around the subject — \
the black ink line IS the edge."

# ---- 風格二 3d：主流三消手遊 soft-3D（Royal Match / Candy Crush 世代，皮克斯質感）----
# 保留 DEO 的色彩構成：白 + 墨黑做主體識別，奶油黃 / 粉頰做品牌暖色。
STYLE_3D="Polished soft-3D mobile puzzle-game asset in the style of top-grossing match-3 games, \
with Pixar-like toy appeal. Chunky, rounded, squashy proportions — every form looks inflated and \
huggable, like vinyl toys or soft candy. Smooth high-quality 3D render: bright studio key light \
from upper-left, gentle ambient bounce fill, ONE crisp glossy specular highlight per surface, and \
soft subtle self-shadow at the base of forms; NO harsh blacks in shading and NO outlines — the \
silhouette is defined by lighting and color contrast alone. Colors are vivid, saturated and \
candy-like with clean smooth gradients. Preserve the DEO cat brand color DNA: porcelain white \
(#FFFFFF) and deep ink black (#131313) as the primary body pairing, with warm cream yellow \
(#FFDB96) and soft blush pink (#FFCDC8) as the signature accent tones, plus one saturated hero hue \
per asset where gameplay demands it. Keep interior detail minimal so each asset reads instantly \
at small board scale; big simple shapes, cute and friendly, never realistic or gritty. \
Do NOT add text, sparkle particles, sticker borders or drop shadows around the subject."

if [[ "$STYLE_PRESET" = 3d ]]; then
  STYLE="$STYLE_3D"
else
  STYLE="$STYLE_INK"
  # 墨線風才放行 pipeline 的「禁止外框線」硬規則
  # (生圖 prompt / chromakey / critic 評審 / 畫風精煉四處同時放行)
  export ART_ALLOW_OUTLINE=1
fi

# 主題：不畫貓臉(pipeline 全域禁止五官)，改用同一隻貓世界觀的道具，用畫風承載 IP 識別度
THEME="DEO 黑白貓 IP 的貓咪日常小物世界觀 — 例如貓爪印、小魚乾、毛線球、貓罐頭、鈴鐺、貓抓板、\
牛奶盒、魚骨、貓窩紙箱。每個物件都要看起來像同一個貓咪品牌出品的同一組遊戲素材，簡單、可愛、\
一眼看得懂，不要出現貓的臉或五官。"

ASSETS="Red,Grn,Blu,Yel,Pur,Soda0d,Soda90,TNT,LtBl,TrPr,board_bg"

echo "== DEO IP match3 art =="
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
