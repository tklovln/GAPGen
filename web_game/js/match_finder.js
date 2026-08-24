// match_finder.js — 1:1 移植 godot_demo/scripts/board/match_finder.gd
// grid[x][y] = Candy | null；blocked = Set of "x,y"
import { K, DIRS4 } from './util.js';
import { CandyType } from './tiles.js';

const inGrid = (x, y, w, h) => x >= 0 && x < w && y >= 0 && y < h;

function isNormalAt(grid, x, y, blocked) {
  if (blocked.has(K(x, y))) return null;
  const c = grid[x][y];
  if (!c || c.candyType !== CandyType.NORMAL) return null;
  return c;
}

export function findAllMatches(grid, width, height, blocked) {
  const rawLines = []; // {color, positions:[{x,y}], kind:'h'|'v'|'block'|'arm'}

  // 1. raw 水平連線
  for (let y = 0; y < height; y++) {
    let x = 0;
    while (x < width) {
      const c0 = isNormalAt(grid, x, y, blocked);
      if (!c0) { x++; continue; }
      const color = c0.candyColor;
      const run = [{ x, y }];
      let xx = x + 1;
      while (xx < width) {
        const c2 = isNormalAt(grid, xx, y, blocked);
        if (!c2 || c2.candyColor !== color) break;
        run.push({ x: xx, y });
        xx++;
      }
      if (run.length >= 3) rawLines.push({ color, positions: run, kind: 'h' });
      x = xx > x ? xx : x + 1;
    }
  }

  // 2. raw 垂直連線
  for (let x = 0; x < width; x++) {
    let y = 0;
    while (y < height) {
      const c0 = isNormalAt(grid, x, y, blocked);
      if (!c0) { y++; continue; }
      const color = c0.candyColor;
      const run = [{ x, y }];
      let yy = y + 1;
      while (yy < height) {
        const c2 = isNormalAt(grid, x, yy, blocked);
        if (!c2 || c2.candyColor !== color) break;
        run.push({ x, y: yy });
        yy++;
      }
      if (run.length >= 3) rawLines.push({ color, positions: run, kind: 'v' });
      y = yy > y ? yy : y + 1;
    }
  }

  // 3. raw 2x2 方塊
  for (let x = 0; x < width - 1; x++) {
    for (let y = 0; y < height - 1; y++) {
      const positions = check2x2At(grid, x, y, width, height, blocked);
      if (positions.length === 4) {
        rawLines.push({ color: grid[x][y].candyColor, positions, kind: 'block' });
      }
    }
  }

  // T/L 短臂
  rawLines.push(...collectTArmLines(grid, width, height, blocked, rawLines));

  if (rawLines.length === 0) return [];

  // 4. Union-Find 合併同色 + overlap
  const n = rawLines.length;
  const parent = Array.from({ length: n }, (_, i) => i);
  const findRoot = (i) => {
    while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; }
    return i;
  };
  const posSetOf = rawLines.map((rl) => new Set(rl.positions.map((p) => K(p.x, p.y))));
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (rawLines[i].color !== rawLines[j].color) continue;
      let overlap = false;
      for (const p of rawLines[i].positions) {
        if (posSetOf[j].has(K(p.x, p.y))) { overlap = true; break; }
      }
      if (overlap) {
        const ri = findRoot(i), rj = findRoot(j);
        if (ri !== rj) parent[ri] = rj;
      }
    }
  }

  // 5. 收集 group
  const groups = new Map();
  for (let i = 0; i < n; i++) {
    const root = findRoot(i);
    if (!groups.has(root)) {
      groups.set(root, { color: rawLines[i].color, positions: [], pset: new Set(), hasBlock: false });
    }
    const g = groups.get(root);
    for (const p of rawLines[i].positions) {
      const k = K(p.x, p.y);
      if (!g.pset.has(k)) { g.pset.add(k); g.positions.push(p); }
    }
    if (rawLines[i].kind === 'block') g.hasBlock = true;
  }

  // 6. classify shape per group
  const matches = [];
  for (const g of groups.values()) {
    const positions = g.positions;
    if (positions.length < 3) continue;
    const pset = g.pset;

    let maxH = 0, maxV = 0;
    let maxHRun = [], maxVRun = [];
    let ltPivot = positions[0];
    let hasCross = false;
    for (const p of positions) {
      let hRun = 1, hpStart = p.x, hpEnd = p.x;
      let px = p.x + 1;
      while (pset.has(K(px, p.y))) { hRun++; hpEnd = px; px++; }
      px = p.x - 1;
      while (pset.has(K(px, p.y))) { hRun++; hpStart = px; px--; }
      let vRun = 1, vpStart = p.y, vpEnd = p.y;
      let py = p.y + 1;
      while (pset.has(K(p.x, py))) { vRun++; vpEnd = py; py++; }
      py = p.y - 1;
      while (pset.has(K(p.x, py))) { vRun++; vpStart = py; py--; }
      if (hRun > maxH) {
        maxH = hRun;
        maxHRun = [];
        for (let cx = hpStart; cx <= hpEnd; cx++) maxHRun.push({ x: cx, y: p.y });
      }
      if (vRun > maxV) {
        maxV = vRun;
        maxVRun = [];
        for (let cy = vpStart; cy <= vpEnd; cy++) maxVRun.push({ x: p.x, y: cy });
      }
      if (hRun >= 3 && vRun >= 2 && !hasCross) { hasCross = true; ltPivot = p; }
    }

    let shape = 'line';
    let direction = 'horizontal';
    let specialPos = positions[0];

    if (Math.max(maxH, maxV) >= 5) {
      shape = 'five';
      specialPos = maxH >= maxV
        ? maxHRun[Math.floor(maxHRun.length / 2)]
        : maxVRun[Math.floor(maxVRun.length / 2)];
    } else if (hasCross && !g.hasBlock && positions.length >= 5) {
      shape = 'special';
      specialPos = ltPivot;
    } else if (Math.max(maxH, maxV) === 4) {
      shape = 'four';
      if (maxH >= maxV) { direction = 'horizontal'; specialPos = maxHRun[1]; }
      else { direction = 'vertical'; specialPos = maxVRun[1]; }
    } else if (g.hasBlock) {
      shape = 'block_2x2';
      specialPos = positions[0];
      for (const p of positions) {
        if (p.x <= specialPos.x && p.y <= specialPos.y) specialPos = p;
      }
    } else {
      shape = 'line';
      specialPos = maxH >= maxV
        ? maxHRun[Math.floor(maxHRun.length / 2)]
        : maxVRun[Math.floor(maxVRun.length / 2)];
    }

    matches.push({
      cells: positions, shape, direction, specialPos,
      color: g.color, directions: [direction],
    });
  }
  return matches;
}

function collectTArmLines(grid, width, height, blocked, rawLines) {
  const arms = [];
  for (const raw of rawLines) {
    if (raw.kind !== 'h' || raw.positions.length < 3) continue;
    const color = raw.color;
    const hset = new Set(raw.positions.map((p) => K(p.x, p.y)));
    for (const p of raw.positions) {
      for (const dr of [-1, 1]) {
        const np = { x: p.x, y: p.y + dr };
        if (np.y < 0 || np.y >= height || blocked.has(K(np.x, np.y)) || hset.has(K(np.x, np.y))) continue;
        const c = isNormalAt(grid, np.x, np.y, blocked);
        if (!c || c.candyColor !== color) continue;
        const arm = colRun(grid, np.x, np.y, width, height, color, blocked, hset);
        if (arm.length >= 2) arms.push({ color, positions: arm, kind: 'arm' });
      }
    }
  }
  for (const raw of rawLines) {
    if (raw.kind !== 'v' || raw.positions.length < 3) continue;
    const color = raw.color;
    const vset = new Set(raw.positions.map((p) => K(p.x, p.y)));
    for (const p of raw.positions) {
      for (const dc of [-1, 1]) {
        const np = { x: p.x + dc, y: p.y };
        if (np.x < 0 || np.x >= width || blocked.has(K(np.x, np.y)) || vset.has(K(np.x, np.y))) continue;
        const c = isNormalAt(grid, np.x, np.y, blocked);
        if (!c || c.candyColor !== color) continue;
        const arm = rowRun(grid, np.x, np.y, width, height, color, blocked, vset);
        if (arm.length >= 2) arms.push({ color, positions: arm, kind: 'arm' });
      }
    }
  }
  return arms;
}

function colRun(grid, x, y, width, height, color, blocked, exclude) {
  const run = [{ x, y }];
  let py = y + 1;
  while (py < height) {
    const k = K(x, py);
    if (blocked.has(k) || exclude.has(k)) break;
    const c = isNormalAt(grid, x, py, blocked);
    if (!c || c.candyColor !== color) break;
    run.push({ x, y: py });
    py++;
  }
  py = y - 1;
  while (py >= 0) {
    const k = K(x, py);
    if (blocked.has(k) || exclude.has(k)) break;
    const c = isNormalAt(grid, x, py, blocked);
    if (!c || c.candyColor !== color) break;
    run.unshift({ x, y: py });
    py--;
  }
  return run;
}

function rowRun(grid, x, y, width, height, color, blocked, exclude) {
  const run = [{ x, y }];
  let px = x + 1;
  while (px < width) {
    const k = K(px, y);
    if (blocked.has(k) || exclude.has(k)) break;
    const c = isNormalAt(grid, px, y, blocked);
    if (!c || c.candyColor !== color) break;
    run.push({ x: px, y });
    px++;
  }
  px = x - 1;
  while (px >= 0) {
    const k = K(px, y);
    if (blocked.has(k) || exclude.has(k)) break;
    const c = isNormalAt(grid, px, y, blocked);
    if (!c || c.candyColor !== color) break;
    run.unshift({ x: px, y });
    px--;
  }
  return run;
}

// 延伸消除 — 對齊 collect_extended_elimination
export function collectExtendedElimination(grid, width, height, cells, shape, pivot, color, blocked) {
  const pos = new Set(cells.map((p) => K(p.x, p.y)));
  const extra = [];
  if (shape === 'five') {
    for (const dr of [-1, 1]) {
      const np = { x: pivot.x, y: pivot.y + dr };
      if (np.y < 0 || np.y >= height || blocked.has(K(np.x, np.y)) || pos.has(K(np.x, np.y))) continue;
      const c = isNormalAt(grid, np.x, np.y, blocked);
      if (c && c.candyColor === color) extra.push(np);
    }
  } else if (shape === 'special') {
    for (const off of DIRS4) {
      const np = { x: pivot.x + off.x, y: pivot.y + off.y };
      if (!inGrid(np.x, np.y, width, height) || blocked.has(K(np.x, np.y)) || pos.has(K(np.x, np.y))) continue;
      const c = isNormalAt(grid, np.x, np.y, blocked);
      if (!c || c.candyColor !== color) continue;
      const trial = new Set(pos);
      trial.add(K(np.x, np.y));
      if (trialHasFourOr2x2(grid, width, height, trial, color, blocked)) extra.push(np);
    }
  } else if (shape === 'block_2x2') {
    for (const p of cells) {
      for (const off of DIRS4) {
        const np = { x: p.x + off.x, y: p.y + off.y };
        if (!inGrid(np.x, np.y, width, height) || blocked.has(K(np.x, np.y)) || pos.has(K(np.x, np.y))) continue;
        const c = isNormalAt(grid, np.x, np.y, blocked);
        if (!c || c.candyColor !== color) continue;
        if (formsThreeWithBlock(np, cells)) extra.push(np);
      }
    }
  }
  return extra;
}

function trialHasFourOr2x2(grid, width, height, trial, color, blocked) {
  const byRow = new Map(), byCol = new Map();
  for (const k of trial) {
    const [x, y] = k.split(',').map(Number);
    const c = grid[x][y];
    if (!c || c.candyColor !== color) continue;
    if (!byRow.has(y)) byRow.set(y, []);
    byRow.get(y).push(x);
    if (!byCol.has(x)) byCol.set(x, []);
    byCol.get(x).push(y);
  }
  for (const xs of byRow.values()) {
    xs.sort((a, b) => a - b);
    if (maxConsecutive(xs) >= 4) return true;
  }
  for (const ys of byCol.values()) {
    ys.sort((a, b) => a - b);
    if (maxConsecutive(ys) >= 4) return true;
  }
  for (const k of trial) {
    const [x, y] = k.split(',').map(Number);
    if (check2x2At(grid, x, y, width, height, blocked).length === 4) return true;
  }
  return false;
}

function maxConsecutive(sortedVals) {
  if (sortedVals.length === 0) return 0;
  let best = 1, cur = 1;
  for (let i = 1; i < sortedVals.length; i++) {
    if (sortedVals[i] === sortedVals[i - 1] + 1) { cur++; best = Math.max(best, cur); }
    else cur = 1;
  }
  return best;
}

function formsThreeWithBlock(arm, blockCells) {
  let shared = 0;
  for (const p of blockCells) {
    if (p.y === arm.y && Math.abs(p.x - arm.x) === 1) shared++;
    else if (p.x === arm.x && Math.abs(p.y - arm.y) === 1) shared++;
  }
  return shared >= 2;
}

function check2x2At(grid, x, y, width, height, blocked) {
  const positions = [];
  if (x + 1 >= width || y + 1 >= height) return positions;
  const c00 = isNormalAt(grid, x, y, blocked);
  if (!c00) return positions;
  const color = c00.candyColor;
  for (let dx = 0; dx < 2; dx++) {
    for (let dy = 0; dy < 2; dy++) {
      const px = x + dx, py = y + dy;
      const cc = isNormalAt(grid, px, py, blocked);
      if (!cc || cc.candyColor !== color) return [];
      positions.push({ x: px, y: py });
    }
  }
  return positions;
}

// ============ 相容介面 ============

export function hasPossibleMoves(grid, width, height, blocked) {
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (blocked.has(K(x, y))) continue;
      const c = grid[x][y];
      if (c && c.candyType !== CandyType.NORMAL) return true;
    }
  }
  return findHintMove(grid, width, height, blocked).length > 0;
}

export function findHintMove(grid, width, height, blocked) {
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (blocked.has(K(x, y)) || grid[x][y] === null) continue;
      for (const dir of [{ x: 1, y: 0 }, { x: 0, y: 1 }]) {
        const nx = x + dir.x, ny = y + dir.y;
        if (nx >= width || ny >= height) continue;
        if (blocked.has(K(nx, ny))) continue;
        const other = grid[nx][ny];
        if (other === null) {
          // 盤內空格：模擬移入再還原
          grid[nx][ny] = grid[x][y];
          grid[x][y] = null;
          const foundEmpty = findAllMatches(grid, width, height, blocked).length > 0;
          grid[x][y] = grid[nx][ny];
          grid[nx][ny] = null;
          if (foundEmpty) return [{ x, y }, { x: nx, y: ny }];
          continue;
        }
        swapInGrid(grid, x, y, nx, ny);
        const found = findAllMatches(grid, width, height, blocked).length > 0;
        swapInGrid(grid, x, y, nx, ny);
        if (found) return [{ x, y }, { x: nx, y: ny }];
      }
    }
  }
  return [];
}

function swapInGrid(grid, x1, y1, x2, y2) {
  const t = grid[x1][y1];
  grid[x1][y1] = grid[x2][y2];
  grid[x2][y2] = t;
}
