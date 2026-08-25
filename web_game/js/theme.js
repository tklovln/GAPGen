// theme.js — 美術換皮：預設載 godot_demo/resources/sprites/，
// ?theme=<name> 時以 generated_art/<name>/sprites/ 覆蓋（缺圖 fallback 回預設）。
// 對齊 art_theme.gd 的「先載預設 → live 覆蓋」策略。

const DEFAULT_BASE = '../godot_demo/resources/sprites/';
const GENERATED_BASE = '../generated_art/';

// 對齊 godot_demo/web/live_sprites/manifest.json 的 sprite 清單
export const MANIFEST = [
  'Barrel', 'BeverageChiller_body', 'BeverageChiller_bottle_blue', 'BeverageChiller_bottle_green',
  'BeverageChiller_bottle_red', 'BeverageChiller_bottle_yellow', 'BeverageChiller_closed',
  'BeverageChiller_door', 'BeverageChiller_lv1', 'BeverageChiller_lv2', 'BeverageChiller_lv3',
  'BeverageChiller_lv4', 'BeverageChiller_lv5', 'Blu', 'Crt1', 'Crt2', 'Crt3', 'Crt4', 'Grn',
  'LtBl', 'Mud', 'Pool_lv1', 'Pool_lv2', 'Pool_lv3', 'Pool_lv4', 'Pool_lv5', 'Postmark_01',
  'Postmark_02', 'Postmark_bundle', 'Postmark_card', 'Postmark_goal', 'Puddle_lv1', 'Puddle_lv2',
  'Pur', 'Red', 'Rope_lv1', 'Rope_lv2', 'SalmonCan', 'SalmonCan_body', 'SalmonCan_top1',
  'SalmonCan_top2', 'Soda0d', 'Soda90', 'Stamp', 'TNT', 'TrPr', 'TrafficCone_lv1',
  'TrafficCone_lv2', 'WaterChiller_closed', 'WaterChiller_door', 'WaterChiller_lv1',
  'WaterChiller_lv10', 'WaterChiller_lv11', 'WaterChiller_lv2', 'WaterChiller_lv3',
  'WaterChiller_lv4', 'WaterChiller_lv5', 'WaterChiller_lv6', 'WaterChiller_lv7',
  'WaterChiller_lv8', 'WaterChiller_lv9', 'Yel', 'board_bg',
];

class ArtThemeClass {
  constructor() {
    this.textures = new Map();   // stem → PIXI.Texture
    this.urls = new Map();       // stem → 實際使用的 URL（HUD <img> 用）
    this.currentTheme = '';
    this._listeners = [];
  }

  onThemeReady(fn) { this._listeners.push(fn); }
  _emitReady() { for (const fn of this._listeners) fn(); }

  has(name) { return this.textures.has(name); }
  get(name) { return this.textures.get(name) || null; }
  url(name) { return this.urls.get(name) || DEFAULT_BASE + name + '.png'; }

  themeBase(themeName) { return GENERATED_BASE + themeName + '/sprites/'; }

  // 旋轉動畫幀（scripts/gen_rotation_gif.py 產出，10 幀 turntable）
  // ponytail: 目前只有 deo_cat_ip 的 Soda90 生成過幀；其他主題/素材回 null，
  // candy 端會 fallback 成直接旋轉貼圖。要擴充就對該 sprite 跑一次生成腳本即可。
  // SPIN_FRAMES_VERSION: 幀重新生成/後處理時 +1，避免瀏覽器用舊快取（例如白底版）
  static SPIN_FRAMES_VERSION = 2;

  async loadSpinFrames(stem) {
    this._spinFrames ??= new Map();
    const key = this.currentTheme + '/' + stem;
    if (this._spinFrames.has(key)) return this._spinFrames.get(key);
    let out = null;
    if (this.currentTheme === 'deo_cat_ip') {
      try {
        const frames = [];
        for (let i = 0; i < 10; i++) {
          const src = `${GENERATED_BASE}rotation_test/${stem}/frame_${String(i).padStart(2, '0')}.png`
            + `?v=${ArtThemeClass.SPIN_FRAMES_VERSION}`;
          frames.push(await PIXI.Assets.load({ src, loadParser: 'loadTextures' }));
        }
        out = frames;
      } catch (_e) { out = null; }
    }
    this._spinFrames.set(key, out);
    return out;
  }

  // 批次載入（12 張一批，對齊 art_theme.gd BATCH=12）；缺圖回 null
  async _loadBatch(base, names, onProgress) {
    const out = new Map();
    const BATCH = 12;
    let done = 0;
    for (let i = 0; i < names.length; i += BATCH) {
      const batch = names.slice(i, i + BATCH);
      await Promise.all(batch.map(async (nm) => {
        const url = base + nm + '.png';
        try {
          const tex = await PIXI.Assets.load({ src: url, loadParser: 'loadTextures' });
          out.set(nm, { tex, url });
        } catch (_e) {
          out.set(nm, null);
        }
        done++;
        if (onProgress) onProgress(done, names.length);
      }));
    }
    return out;
  }

  async load(themeName = '', onProgress = null) {
    this.currentTheme = themeName;
    // 1) packed 預設
    if (this.textures.size === 0) {
      const defaults = await this._loadBatch(DEFAULT_BASE, MANIFEST, onProgress);
      for (const [nm, entry] of defaults) {
        if (entry) { this.textures.set(nm, entry.tex); this.urls.set(nm, entry.url); }
      }
      this._defaultUrls = new Map(this.urls);
      this._defaultTextures = new Map(this.textures);
    } else {
      // 重載回預設
      this.textures = new Map(this._defaultTextures);
      this.urls = new Map(this._defaultUrls);
    }
    // 2) 主題覆蓋（缺圖保留預設）
    if (themeName !== '') {
      const overrides = await this._loadBatch(this.themeBase(themeName), MANIFEST, onProgress);
      for (const [nm, entry] of overrides) {
        if (entry) { this.textures.set(nm, entry.tex); this.urls.set(nm, entry.url); }
      }
    }
    this._emitReady();
  }

  // 從 python http.server 的目錄列表撈 generated_art/ 下的變體名單；失敗回空陣列
  async listThemes() {
    try {
      const res = await fetch(GENERATED_BASE);
      if (!res.ok) return [];
      const html = await res.text();
      const names = [...html.matchAll(/href="([^"/]+)\/"/g)].map((m) => decodeURIComponent(m[1]));
      // 只留有 sprites/ 子資料夾的（用 HEAD 探測 Red.png，併發）
      const checks = await Promise.all(names.map(async (nm) => {
        try {
          const r = await fetch(this.themeBase(nm) + 'Red.png', { method: 'HEAD' });
          return r.ok ? nm : null;
        } catch (_e) { return null; }
      }));
      return checks.filter(Boolean);
    } catch (_e) {
      return [];
    }
  }
}

export const ArtTheme = new ArtThemeClass();
