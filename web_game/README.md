# Match3 Web 版

Godot 版 Match-3 的 1:1 網頁移植（PixiJS，無 build step），支援即時換皮 `generated_art/` 的美術包。

## 快速開始

在專案根目錄（`Match3_sim/`）執行：

```bash
./serve_web.sh start    # 啟動本機伺服器(8787) + Cloudflare tunnel，印出網址
./serve_web.sh stop     # 全部關掉
./serve_web.sh status   # 看狀態 + 目前外網網址
./serve_web.sh url      # 只印外網網址
```

`start` 會印出兩個網址：

- 本機：`http://localhost:8787/web_game/index.html?theme=deo_cat_ip`
- 外網：`https://<隨機字串>.trycloudflare.com/web_game/index.html?theme=deo_cat_ip`

注意事項：

- 服務用 macOS `launchctl` 跑在背景，關掉終端機不受影響；程序掛掉會自動重啟
- 外網網址每次 `start` 都會換（quick tunnel 免帳號的代價）；要固定網址需要 Cloudflare 帳號建 named tunnel
- 電腦重開機後要再跑一次 `start`
- 伺服器公開的是整個專案根目錄（遊戲需要讀 `generated_art/`、`godot_demo/`、`DEO_emotion/`），分享網址前留意這點
- log 在 `/tmp/match3_serve/`（`http.log`、`tunnel.log`）

不需要外網時，也可以只開本機伺服器：

```bash
python3 -m http.server 8787 --directory .   # 在 Match3_sim/ 下執行
```

## 網址參數

| 參數 | 說明 | 範例 |
|---|---|---|
| `theme` | 美術主題，對應 `generated_art/<name>/sprites/`；不帶則用 Godot 預設素材 | `?theme=deo_cat_ip` |
| `level` | 直接進指定關卡 | `?level=16` |

參數可以並用：`index.html?theme=deo_cat_ip&level=16`。
主題也可以在遊戲選單的下拉選單切換，會自動同步到網址。

注意：Soda 道具的旋轉幀動畫目前只有 `deo_cat_ip` 主題生成過（`generated_art/rotation_test/`），其他主題會 fallback 成直接旋轉貼圖。要擴充就對該 sprite 跑一次 `scripts/gen_rotation_gif.py`。

## 操作

- 點選兩個相鄰糖果、或直接拖曳：交換
- 點擊特殊道具（條紋/包裝/彩球）：直接觸發
- 可拖曳障礙物（桶子等）：拖到相鄰空格
- 下排按鈕：分數 / 靜音 / 選單（換關卡、換主題）

## 開發

- 程式碼在 `web_game/js/`，ES modules，改完重新整理即可（建議硬重整 Cmd+Shift+R 避免舊快取）
- 純邏輯自檢：`node web_game/selfcheck.mjs`（match finder + 頭像 behavior tree）
- 頭像表情用 `DEO_emotion/` 的圖：勝負/爆炸/無效交換/低步數會換表情，idle 眨眼與微笑是 canvas 繪製
- 音效在 `web_game/sfx/`（MP3 取樣，缺檔會 fallback 回 WebAudio 合成）
