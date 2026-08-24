// tiles.js — 對齊 tile_defs.py + game_board._ELIM_RULES + json_level_loader.gd 的資料表

export const CandyType = {
  NORMAL: 0, STRIPED_H: 1, STRIPED_V: 2, WRAPPED: 3, COLOR_BOMB: 4, SPIRAL: 5,
};

export const ELEMENT_TO_COLOR_INDEX = { Red: 0, Grn: 1, Blu: 2, Yel: 3, Pur: 4, Brn: 5 };
export const CANDY_IDX_TO_COLOR_NAME = ['Red', 'Grn', 'Blu', 'Yel'];
export const ELEMENT_NAMES = { 0: 'Red', 1: 'Grn', 2: 'Blu', 3: 'Yel', 4: 'Pur' };

// 消除規則 — 對齊 game_board._ELIM_RULES（源自 tile_defs.py）
export const ELIM_RULES = {
  Crt: { adj: true, inplace: false },
  Puddle: { adj: false, inplace: true },   // bottom layer
  Barrel: { adj: true, inplace: false },
  TrafficCone: { adj: true, inplace: false },
  SalmonCan: { adj: false, inplace: false }, // 只能道具消除
  WaterChiller: { adj: true, inplace: false },
  BeverageChiller: { adj: true, inplace: false },
  Rope: { adj: false, inplace: true },     // upper layer
  Mud: { adj: true, inplace: false },      // upper layer
  Pool: { adj: true, inplace: false },
  Stamp: { adj: true, inplace: false },
  Roadblock: { adj: true, inplace: false },
};

export function elimRule(tileId, kind) {
  for (const prefix of Object.keys(ELIM_RULES)) {
    if (tileId.startsWith(prefix)) return ELIM_RULES[prefix][kind] || false;
  }
  return false;
}

// 紙飛機權重表 — 對齊 game_board._PLANE_WEIGHT_BY_PREFIX
export const PLANE_WEIGHT_BY_PREFIX = {
  Crt: 10, Rope: 10, Barrel: 10, TrafficCone: 10, SalmonCan: 10,
  WaterChiller: 10, BeverageChiller: 10, Mud: 10, Pool: 10, Stamp: 10,
  Roadblock: 10, Puddle: 10,
};

export const isMovableObstacle = (tileId) =>
  tileId.startsWith('Barrel') || tileId.startsWith('TrafficCone');

// tile_id family（Crt1 → Crt、Puddle_lv2 → Puddle、WaterChiller_closed → WaterChiller）
export function tileFamily(tileId) {
  let s = tileId.split('#')[0];
  const lvIdx = s.indexOf('_lv');
  if (lvIdx >= 0) return s.substring(0, lvIdx);
  for (const suffix of ['_closed', '_open']) {
    if (s.endsWith(suffix)) { s = s.substring(0, s.length - suffix.length); break; }
  }
  let i = s.length;
  while (i > 0 && s[i - 1] >= '0' && s[i - 1] <= '9') i--;
  return i > 0 ? s.substring(0, i) : s;
}

// hits 模式（每扣血 GOAL+1）— 對齊 game_board._is_hits_mode_obstacle
export const isHitsModeObstacle = (tileId) =>
  tileId.startsWith('WaterChiller') || tileId.startsWith('BeverageChiller');

// tile_id + HP → sprite key，對齊 board_bg._resolve_sprite_key
export function resolveSpriteKey(tileId, hp) {
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  if (tileId.startsWith('Crt')) return 'Crt' + clamp(hp, 1, 4);
  if (tileId.startsWith('WaterChiller')) {
    const lv = clamp(hp, 1, 11);
    return lv === 11 ? 'WaterChiller_closed' : 'WaterChiller_lv' + lv;
  }
  if (tileId.startsWith('BeverageChiller')) {
    const lv = clamp(hp, 1, 5);
    return lv === 5 ? 'BeverageChiller_closed' : 'BeverageChiller_lv' + lv;
  }
  if (tileId.startsWith('Pool')) return 'Pool_lv' + clamp(hp, 1, 5);
  if (tileId.includes('_lv')) {
    const base = tileId.split('_lv')[0];
    const maxLv = { Puddle: 2, TrafficCone: 2, Rope: 2 }[base] || 1;
    return base + '_lv' + clamp(hp, 1, maxLv);
  }
  return tileId;
}

// 元素 fallback 顏色（無 sprite 時 / 粒子特效用）— 對齊 candy_renderer.COLOR_MAP
export const COLOR_MAP = {
  0: 0xf23333, 1: 0x33d94d, 2: 0x3373f2, 3: 0xffe626, 4: 0xb340e6, 5: 0xff8c1a,
};

export const BEVERAGE_BOTTLE_TEXTURE_KEY = {
  Red: 'BeverageChiller_bottle_red',
  Blu: 'BeverageChiller_bottle_blue',
  Grn: 'BeverageChiller_bottle_green',
  Yel: 'BeverageChiller_bottle_yellow',
};

// HUD 目標 icon stem — 對齊 hud.OBJECTIVE_ICON_STEMS
export const OBJECTIVE_ICON_STEMS = {
  Crt: 'Crt1', Barrel: 'Barrel', TrafficCone: 'TrafficCone_lv1',
  SalmonCan: 'SalmonCan', Stamp: 'Postmark_goal',
  WaterChiller: 'WaterChiller_closed', BeverageChiller: 'BeverageChiller_closed',
  Pool: 'Pool_lv5', Puddle: 'Puddle_lv1', Rope: 'Rope_lv1', Mud: 'Mud',
};

// candy special type → sprite 名
export const SPECIAL_SPRITE = {
  [CandyType.STRIPED_H]: 'Soda0d',
  [CandyType.STRIPED_V]: 'Soda90',
  [CandyType.WRAPPED]: 'TNT',
  [CandyType.COLOR_BOMB]: 'LtBl',
  [CandyType.SPIRAL]: 'TrPr',
};

// ============ CandyFactory — 對齊 candy_factory.gd ============

export function determineSpecialType(matchData) {
  const cells = matchData.cells || [];
  const shape = matchData.shape || 'line';
  const directions = matchData.directions || [];
  if (cells.length >= 5 || shape === 'five') return CandyType.COLOR_BOMB;
  if (shape === 'special' || directions.length > 1) return CandyType.WRAPPED;
  if (cells.length === 4 || shape === 'four') {
    return directions.length > 0 && directions[0] === 'horizontal'
      ? CandyType.STRIPED_V : CandyType.STRIPED_H;
  }
  return -1;
}

export function getComboResult(typeA, typeB) {
  const CT = CandyType;
  const types = [typeA, typeB].sort((a, b) => a - b);
  if (types[0] === CT.COLOR_BOMB && types[1] === CT.COLOR_BOMB) return { effect: 'destroy_all' };
  if (types.includes(CT.COLOR_BOMB)) {
    const other = typeA === CT.COLOR_BOMB ? typeB : typeA;
    if (other === CT.WRAPPED) return { effect: 'color_bomb_wrapped' };
    if (other === CT.STRIPED_H || other === CT.STRIPED_V) return { effect: 'color_bomb_striped' };
    return { effect: 'color_bomb_normal' };
  }
  const isStripedA = typeA === CT.STRIPED_H || typeA === CT.STRIPED_V;
  const isStripedB = typeB === CT.STRIPED_H || typeB === CT.STRIPED_V;
  const isSpiralA = typeA === CT.SPIRAL;
  const isSpiralB = typeB === CT.SPIRAL;
  if (typeA === CT.WRAPPED && typeB === CT.WRAPPED) return { effect: 'double_wrapped' };
  if ((typeA === CT.WRAPPED && isStripedB) || (typeB === CT.WRAPPED && isStripedA))
    return { effect: 'wrapped_striped' };
  if (isStripedA && isStripedB) return { effect: 'double_striped' };
  if (isSpiralA && isSpiralB) return { effect: 'double_spiral' };
  if ((isSpiralA && typeB === CT.WRAPPED) || (isSpiralB && typeA === CT.WRAPPED))
    return { effect: 'spiral_wrapped' };
  if ((isSpiralA && isStripedB) || (isSpiralB && isStripedA)) return { effect: 'spiral_striped' };
  return { effect: 'none' };
}

// ============ SpecialCandy 目標範圍 — 對齊 special_candy.gd ============

export function getStripedHTargets(pos, gridWidth) {
  const out = [];
  for (let x = 0; x < gridWidth; x++) if (x !== pos.x) out.push({ x, y: pos.y });
  return out;
}

export function getStripedVTargets(pos, gridHeight) {
  const out = [];
  for (let y = 0; y < gridHeight; y++) if (y !== pos.y) out.push({ x: pos.x, y });
  return out;
}

export function getWrappedTargets(pos, w, h) {
  const out = [];
  for (let dx = -2; dx <= 2; dx++) for (let dy = -2; dy <= 2; dy++) {
    if (dx === 0 && dy === 0) continue;
    const tx = pos.x + dx, ty = pos.y + dy;
    if (tx >= 0 && tx < w && ty >= 0 && ty < h) out.push({ x: tx, y: ty });
  }
  return out;
}

export function getBigWrappedTargets(pos, w, h) {
  const out = [];
  for (let dx = -3; dx <= 3; dx++) for (let dy = -3; dy <= 3; dy++) {
    if (dx === 0 && dy === 0) continue;
    const tx = pos.x + dx, ty = pos.y + dy;
    if (tx >= 0 && tx < w && ty >= 0 && ty < h) out.push({ x: tx, y: ty });
  }
  return out;
}

export function getCrossTargets(pos, w, h) {
  const out = [];
  for (let x = 0; x < w; x++) if (x !== pos.x) out.push({ x, y: pos.y });
  for (let y = 0; y < h; y++) if (y !== pos.y) out.push({ x: pos.x, y });
  return out;
}
