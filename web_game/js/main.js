// main.js — 入口：對齊 demo_main.gd + hud.gd（DOM HUD 版）
import { ArtTheme } from './theme.js';
import { parseLevelDict, buildObstacleMap } from './level_loader.js';
import { GameManager, GameState } from './game_manager.js';
import { GameBoard } from './board.js';
import * as Audio from './audio.js';
import { tileFamily, OBJECTIVE_ICON_STEMS, COLOR_MAP } from './tiles.js';
import { AvatarBT } from './avatar.js';
import { K } from './util.js';

const LEVELS_BASE = '../godot_demo/levels/';
const LEVEL_COUNT = 100;
const levelFile = (n) => LEVELS_BASE + 'Level_' + String(n).padStart(3, '0') + '.json';

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);

let app = null;
let board = null;
let currentLevelNum = 1;
let bgSprite = null;

// ============ 全螢幕背景 — 對齊 bg_theme.gd（board_bg 紋理，KEEP_ASPECT_COVERED）============

function layoutBg() {
  if (!bgSprite || !bgSprite.texture) return;
  const tex = bgSprite.texture;
  const sw = app.screen.width, sh = app.screen.height;
  const scale = Math.max(sw / tex.width, sh / tex.height);
  bgSprite.scale.set(scale);
  bgSprite.position.set((sw - tex.width * scale) / 2, (sh - tex.height * scale) / 2);
}

function applyBg() {
  const tex = ArtTheme.get('board_bg');
  if (!tex) return;
  if (!bgSprite) {
    bgSprite = new PIXI.Sprite(tex);
    app.stage.addChildAt(bgSprite, 0);
  } else {
    bgSprite.texture = tex;
  }
  layoutBg();
}

// ============ PIXI app ============

async function initApp() {
  app = new PIXI.Application();
  await app.init({
    resizeTo: window,
    background: 0x1a1229,
    antialias: true,
    resolution: Math.min(window.devicePixelRatio || 1, 2),
    autoDensity: true,
  });
  $('game').appendChild(app.canvas);
  ArtTheme.onThemeReady(applyBg);
  window.addEventListener('resize', () => {
    layoutBg();
    if (board) board.relayout(app.screen.width, app.screen.height);
  });
}

// ============ HUD ============

const hud = {
  objEls: new Map(), // objKey → {root, countEl}

  show() { $('hud').classList.remove('hidden'); },
  hide() { $('hud').classList.add('hidden'); },

  objKey(obj) {
    if (obj.type === 'collect') return 'collect:' + obj.color;
    return obj.type + ':' + tileFamily(String(obj.tile_id || ''));
  },

  // 頭像：DEM02 動畫頭像（behavior tree：idle 眨眼 / 消除時看右下+微笑）
  applyAvatar() {
    if (!this._avatar) {
      this._avatar = new AvatarBT($('avatarCanvas'), '../DEO_emotion/');
    }
  },

  build() {
    this.applyAvatar();
    const wrap = $('objectives');
    wrap.innerHTML = '';
    this.objEls.clear();
    for (const obj of GameManager.levelObjectives) {
      const el = document.createElement('div');
      el.className = 'obj';
      if (obj.type === 'collect') {
        const names = ['Red', 'Grn', 'Blu', 'Yel', 'Pur', 'Brn'];
        const stem = names[obj.color];
        if (ArtTheme.has(stem)) {
          el.innerHTML = `<img src="${ArtTheme.url(stem)}" alt="${stem}">`;
        } else {
          const cssColor = '#' + (COLOR_MAP[obj.color] ?? 0xffffff).toString(16).padStart(6, '0');
          el.innerHTML = `<div class="swatch" style="background:${cssColor}"></div>`;
        }
      } else if (obj.type === 'score') {
        el.innerHTML = `<span class="star">★</span>`;
      } else {
        const fam = tileFamily(String(obj.tile_id || ''));
        const stem = OBJECTIVE_ICON_STEMS[fam] || fam;
        el.innerHTML = `<img src="${ArtTheme.url(stem)}" alt="${fam}">`;
      }
      const count = document.createElement('span');
      count.className = 'count';
      el.appendChild(count);
      wrap.appendChild(el);
      this.objEls.set(this.objKey(obj), { root: el, countEl: count });
    }
    this.refreshObjectives();
    $('scoreVal').textContent = GameManager.currentScore;
    this.setMoves(GameManager.movesRemaining);
  },

  setMoves(m) {
    $('movesVal').textContent = m;
    $('movesPanel').classList.toggle('low', m <= 5);
  },

  refreshObjectives() {
    for (const obj of GameManager.levelObjectives) {
      const entry = this.objEls.get(this.objKey(obj));
      if (!entry) continue;
      if (obj.type === 'score') {
        const done = GameManager.currentScore >= obj.target;
        entry.countEl.textContent = done ? '✓' : String(obj.target);
        entry.root.classList.toggle('done', done);
      } else {
        const remain = Math.max(obj.target - (obj.current || 0), 0);
        entry.countEl.textContent = remain > 0 ? String(remain) : '✓';
        entry.root.classList.toggle('done', remain <= 0);
      }
    }
  },

  // 目標 icon 在畫面上的座標（goal fly 目的地）
  objScreenPos(family) {
    for (const obj of GameManager.levelObjectives) {
      const fam = obj.type === 'collect' ? '' : tileFamily(String(obj.tile_id || ''));
      if (fam !== family) continue;
      const entry = this.objEls.get(this.objKey(obj));
      if (!entry) continue;
      const r = entry.root.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }
    const r = $('goalsPanel').getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  },
};

// ============ 覆蓋層 ============

function showOverlay(id) {
  for (const oid of ['loading', 'menu', 'result']) $(oid).classList.toggle('hidden', oid !== id);
  if (id === null) for (const oid of ['loading', 'menu', 'result']) $(oid).classList.add('hidden');
}

function showResult(won, stars, score) {
  $('resultTitle').textContent = won ? '過關！' : '步數用完';
  $('resultStars').textContent = won ? '★'.repeat(Math.max(stars, 1)) + '☆'.repeat(3 - Math.max(stars, 1)) : '';
  $('resultScore').textContent = '分數 ' + score;
  $('nextBtn').classList.toggle('hidden', !won || currentLevelNum >= LEVEL_COUNT);
  showOverlay('result');
}

// ============ 選單 ============

async function buildMenu() {
  const grid = $('levelGrid');
  grid.innerHTML = '';
  for (let n = 1; n <= LEVEL_COUNT; n++) {
    const btn = document.createElement('button');
    btn.textContent = n;
    btn.addEventListener('click', () => { Audio.playButtonSound(); startLevel(n); });
    grid.appendChild(btn);
  }
  const sel = $('themeSelect');
  const themes = await ArtTheme.listThemes();
  for (const t of themes) {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  }
  sel.value = ArtTheme.currentTheme;
  sel.addEventListener('change', async () => {
    showOverlay('loading');
    $('loadingSub').textContent = '載入主題 ' + (sel.value || '預設');
    await ArtTheme.load(sel.value);
    const url = new URL(location.href);
    if (sel.value) url.searchParams.set('theme', sel.value);
    else url.searchParams.delete('theme');
    history.replaceState(null, '', url);
    showOverlay('menu');
  });
}

// ============ 關卡流程 ============

async function startLevel(n) {
  currentLevelNum = n;
  showOverlay('loading');
  $('loadingSub').textContent = 'Level ' + n;

  let raw;
  try {
    const res = await fetch(levelFile(n));
    if (!res.ok) throw new Error('HTTP ' + res.status);
    raw = await res.json();
  } catch (e) {
    $('loadingSub').textContent = '關卡載入失敗：' + e.message;
    setTimeout(() => showOverlay('menu'), 1200);
    return;
  }
  const level = parseLevelDict(raw);
  level.levelId = n;

  if (board) { board.destroy(); board = null; }
  GameManager.clearListeners();
  GameManager.startLevel(level);

  const root = new PIXI.Container();
  app.stage.addChild(root);
  board = new GameBoard(app, root);
  board.setObstacleMap(buildObstacleMap(level.obstacleData, level.gridWidth, level.gridHeight));
  board.setBottomObstacleMap(buildObstacleMap(level.bottomObstacleData, level.gridWidth, level.gridHeight));
  board.initBoard(level, app.screen.width, app.screen.height);

  // GameManager → HUD
  GameManager.on('score_changed', (s) => {
    $('scoreVal').textContent = s;
    hud.refreshObjectives();
    if (hud._avatar) hud._avatar.onMatch();
  });
  GameManager.on('moves_changed', (m) => {
    hud.setMoves(m);
    if (hud._avatar) hud._avatar.setMoves(m);
  });
  GameManager.on('explosion', () => { if (hud._avatar) hud._avatar.onExplosion(); });
  GameManager.on('bad_swap', () => { if (hud._avatar) hud._avatar.onBadSwap(); });
  GameManager.on('objective_updated', () => hud.refreshObjectives());
  GameManager.on('level_completed', (_id, score, stars) => {
    if (hud._avatar) hud._avatar.setMood('win');
    Audio.playLevelCompleteSound();
    setTimeout(() => showResult(true, stars, score), 900);
  });
  GameManager.on('level_failed', () => {
    if (hud._avatar) hud._avatar.setMood('lose');
    Audio.playLevelFailedSound();
    setTimeout(() => showResult(false, 0, GameManager.currentScore), 700);
  });

  // 目標飛行回饋：飛向 HUD 對應目標 icon
  board.onGoalFly = (worldPos, family, tileId) => {
    const screenTo = hud.objScreenPos(family);
    const canvasRect = app.canvas.getBoundingClientRect();
    const to = { x: screenTo.x - canvasRect.left, y: screenTo.y - canvasRect.top };
    const stem = OBJECTIVE_ICON_STEMS[family] || tileId;
    board.effects.spawnGoalFly(worldPos, to, stem);
  };

  hud.build();
  hud.show();
  if (hud._avatar) {
    // startLevel 的 moves_changed 發生在監聽器註冊前，這裡補同步一次
    hud._avatar.setMood('');
    hud._avatar.setMoves(GameManager.movesRemaining);
  }
  showOverlay(null);
  window.__game = { board, GameManager, level, hud };   // 測試/自動驗證用
}

// ============ 按鈕 ============

function bindButtons() {
  $('muteBtn').addEventListener('click', () => {
    const m = Audio.toggleMuted();
    $('muteBtn').textContent = m ? '🔇' : '🔊';
  });
  $('menuBtn').addEventListener('click', () => {
    Audio.playButtonSound();
    if (board) { board.destroy(); board = null; }
    GameManager.currentState = GameState.MENU;
    hud.hide();
    showOverlay('menu');
  });
  $('retryBtn').addEventListener('click', () => { Audio.playButtonSound(); startLevel(currentLevelNum); });
  $('nextBtn').addEventListener('click', () => { Audio.playButtonSound(); startLevel(currentLevelNum + 1); });
  $('backBtn').addEventListener('click', () => {
    Audio.playButtonSound();
    if (board) { board.destroy(); board = null; }
    hud.hide();
    showOverlay('menu');
  });
  // 第一次點擊解鎖 WebAudio
  window.addEventListener('pointerdown', () => Audio.unlockAudio(), { once: true });
}

// ============ 啟動 ============

(async function boot() {
  showOverlay('loading');
  $('loadingSub').textContent = '初始化…';
  await initApp();
  bindButtons();

  const theme = params.get('theme') || '';
  $('loadingSub').textContent = '載入美術素材…';
  await ArtTheme.load(theme, (done, total) => {
    $('loadingSub').textContent = `載入美術素材… ${done}/${total}`;
  });

  await buildMenu();

  const startAt = parseInt(params.get('level') || '0', 10);
  if (startAt >= 1 && startAt <= LEVEL_COUNT) startLevel(startAt);
  else showOverlay('menu');
})();
