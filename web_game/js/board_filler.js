// board_filler.js — 移植 board_filler.gd：grid 資料、初始填盤、重力（直落+斜落）、補糖、Spawner
import { K, randi } from './util.js';
import { Candy } from './candy.js';
import { GameManager } from './game_manager.js';
import { tileFamily } from './tiles.js';

const FALL_TIME_PER_CELL = 0.07;
const FALL_TIME_BASE = 0.08;
export const fallDuration = (dist) => FALL_TIME_PER_CELL * dist + FALL_TIME_BASE;

const MAX_SPAWN_PER_TURN = 8;

export class BoardFiller {
  constructor() {
    this.grid = [];
    this.width = 9;
    this.height = 9;
    this.cellSize = 70;
    this.boardOffset = { x: 0, y: 0 };
    this.blockedCells = new Set();       // Set of "x,y"（跟 board 共用同一個 Set）
    this.voidCells = new Set();
    this.movableObstacleCells = new Set();
    this.candyContainer = null;
    this.numColors = 6;
    this.spawnerData = [];
    this._turnSpawnCount = 0;
    this.obstacleMapRef = new Map();
    this.onObstacleSpawned = null;       // (pos, tileId) => void
  }

  resetTurnSpawn() { this._turnSpawnCount = 0; }

  setup(w, h, cSize, offset, container, blocked) {
    this.width = w;
    this.height = h;
    this.cellSize = cSize;
    this.boardOffset = offset;
    this.candyContainer = container;
    this.blockedCells = blocked;
    this.grid = [];
    for (let x = 0; x < w; x++) this.grid.push(new Array(h).fill(null));
  }

  setSpawners(data) {
    this.spawnerData = data;
    this._turnSpawnCount = 0;
  }

  gridToWorld(pos) {
    return {
      x: this.boardOffset.x + pos.x * this.cellSize + this.cellSize / 2,
      y: this.boardOffset.y + pos.y * this.cellSize + this.cellSize / 2,
    };
  }

  fillInitial() {
    const reachable = this._computeReachableCells();
    for (let y = 0; y < this.height; y++) {
      for (let x = 0; x < this.width; x++) {
        if (this.blockedCells.has(K(x, y))) continue;
        if (!reachable.has(K(x, y))) continue;
        const color = this._pickNoMatchColor(x, y);
        this.grid[x][y] = this._createCandy(color, { x, y });
      }
    }
  }

  _pickNoMatchColor(x, y) {
    for (let attempts = 0; attempts < 100; attempts++) {
      const color = randi(this.numColors);
      let hMatch = false;
      if (x >= 2 && this.grid[x - 1][y] && this.grid[x - 2][y]) {
        if (this.grid[x - 1][y].candyColor === color && this.grid[x - 2][y].candyColor === color) hMatch = true;
      }
      let vMatch = false;
      if (y >= 2 && this.grid[x][y - 1] && this.grid[x][y - 2]) {
        if (this.grid[x][y - 1].candyColor === color && this.grid[x][y - 2].candyColor === color) vMatch = true;
      }
      if (!hMatch && !vMatch) return color;
    }
    return randi(this.numColors);
  }

  _createCandy(color, gridPos, candyType = 0) {
    const candy = new Candy(this.candyContainer);
    candy.cellSize = this.cellSize;
    candy.init(color, gridPos, candyType);
    const w = this.gridToWorld(gridPos);
    candy.node.position.set(w.x, w.y);
    return candy;
  }

  // 重力 — 3-phase：直落 / 左斜落 / 右斜落（僅 cavity 格允許斜落）
  applyGravity() {
    const tweens = [];
    const originPos = new Map();  // candy → {x,y}
    for (let x = 0; x < this.width; x++) {
      for (let y = 0; y < this.height; y++) {
        const c = this.grid[x][y];
        if (c) originPos.set(c, { x, y });
      }
    }

    let overallMoved = true;
    let safety = 0;
    while (overallMoved && safety < this.width * this.height * 4) {
      safety++;
      overallMoved = false;

      // Phase 1: 全欄直落
      for (let x = 0; x < this.width; x++) {
        let g1 = 0;
        while (this._columnDrop(x)) {
          overallMoved = true;
          if (++g1 > this.height + 2) break;
        }
      }

      // Phase 2: 左斜落
      let leftMoved = true, lg = 0;
      while (leftMoved && lg < this.width * this.height) {
        lg++;
        leftMoved = false;
        for (let y = this.height - 2; y >= 0; y--) {
          for (let x = 0; x < this.width; x++) {
            const c = this.grid[x][y];
            if (!c) continue;
            if (this._canFallTo(x, y + 1)) continue;
            if (x > 0 && this._canFallTo(x - 1, y + 1) && !this._reachableFromTop(x - 1, y + 1)) {
              this.grid[x - 1][y + 1] = c;
              this.grid[x][y] = null;
              let g2 = 0;
              while (this._columnDrop(x - 1)) if (++g2 > this.height + 2) break;
              leftMoved = true;
              overallMoved = true;
            }
          }
        }
      }

      // Phase 3: 右斜落
      let rightMoved = true, rg = 0;
      while (rightMoved && rg < this.width * this.height) {
        rg++;
        rightMoved = false;
        for (let y = this.height - 2; y >= 0; y--) {
          for (let x = 0; x < this.width; x++) {
            const c = this.grid[x][y];
            if (!c) continue;
            if (this._canFallTo(x, y + 1)) continue;
            if (x < this.width - 1 && this._canFallTo(x + 1, y + 1) && !this._reachableFromTop(x + 1, y + 1)) {
              this.grid[x + 1][y + 1] = c;
              this.grid[x][y] = null;
              let g3 = 0;
              while (this._columnDrop(x + 1)) if (++g3 > this.height + 2) break;
              rightMoved = true;
              overallMoved = true;
            }
          }
        }
      }
    }

    // 對移動過的糖建 tween
    for (let x = 0; x < this.width; x++) {
      for (let y = 0; y < this.height; y++) {
        const c = this.grid[x][y];
        if (!c || !originPos.has(c)) continue;
        const orig = originPos.get(c);
        if (orig.x !== x || orig.y !== y) {
          c.gridPos = { x, y };
          const dist = Math.max(Math.abs(x - orig.x), Math.abs(y - orig.y));
          tweens.push(c.animateFall(this.gridToWorld({ x, y }), fallDuration(dist)));
        }
      }
    }
    return tweens;
  }

  _columnDrop(x) {
    let moved = false;
    for (let y = this.height - 2; y >= 0; y--) {
      const c = this.grid[x][y];
      if (!c) continue;
      let targetY = y + 1;
      while (targetY < this.height && this.voidCells.has(K(x, targetY))) targetY++;
      if (!this._canFallTo(x, targetY)) continue;
      this.grid[x][targetY] = c;
      this.grid[x][y] = null;
      moved = true;
    }
    return moved;
  }

  _canFallTo(x, y) {
    if (x < 0 || x >= this.width || y < 0 || y >= this.height) return false;
    if (this.blockedCells.has(K(x, y))) return false;
    return this.grid[x][y] === null;
  }

  _reachableFromTop(x, y) {
    for (let ty = 0; ty < y; ty++) {
      const k = K(x, ty);
      if (this.blockedCells.has(k) && !this.voidCells.has(k) && !this.movableObstacleCells.has(k)) return false;
    }
    return true;
  }

  _computeReachableCells() {
    const reachable = new Set();
    const visited = new Set();
    const queue = [];
    for (let x = 0; x < this.width; x++) {
      const k = K(x, 0);
      if (!this.blockedCells.has(k)) {
        reachable.add(k);
        visited.add(k);
        queue.push({ x, y: 0 });
      } else if (this.voidCells.has(k) || this.movableObstacleCells.has(k)) {
        visited.add(k);
        queue.push({ x, y: 0 });
      }
    }
    let head = 0;
    while (head < queue.length) {
      const cur = queue[head++];
      for (const dx of [-1, 0, 1]) {
        const nx = cur.x + dx, ny = cur.y + 1;
        if (nx < 0 || nx >= this.width || ny >= this.height) continue;
        const nk = K(nx, ny);
        if (visited.has(nk)) continue;
        visited.add(nk);
        if (this.voidCells.has(nk) || this.movableObstacleCells.has(nk)) {
          queue.push({ x: nx, y: ny });
          continue;
        }
        if (this.blockedCells.has(nk)) continue;
        reachable.add(nk);
        queue.push({ x: nx, y: ny });
      }
    }
    return reachable;
  }

  fillEmptyCells() {
    const tweens = [];
    for (let x = 0; x < this.width; x++) {
      const reachableEmptyYs = [];
      let pathClear = true;
      for (let y = 0; y < this.height; y++) {
        const k = K(x, y);
        if (this.blockedCells.has(k)) {
          if (!this.voidCells.has(k) && !this.movableObstacleCells.has(k)) pathClear = false;
          continue;
        }
        if (this.grid[x][y] === null && pathClear) reachableEmptyYs.push(y);
      }
      for (let i = 0; i < reachableEmptyYs.length; i++) {
        const targetY = reachableEmptyYs[reachableEmptyYs.length - 1 - i];
        const startY = -(i + 1);
        const spawnedTile = this._trySpawnObstacle(x);
        if (spawnedTile !== '') {
          if (this.onObstacleSpawned) this.onObstacleSpawned({ x, y: targetY }, spawnedTile);
          continue;
        }
        const color = randi(this.numColors);
        const candy = this._createCandy(color, { x, y: targetY });
        const startW = this.gridToWorld({ x, y: startY });
        candy.node.position.set(startW.x, startW.y);
        this.grid[x][targetY] = candy;
        const dist = Math.abs(targetY - startY);
        tweens.push(candy.animateFall(this.gridToWorld({ x, y: targetY }), fallDuration(dist)));
      }
    }
    return tweens;
  }

  _trySpawnObstacle(col) {
    if (this._turnSpawnCount >= MAX_SPAWN_PER_TURN) return '';
    for (const s of this.spawnerData) {
      const spawnCols = s.spawn_cols || [];
      if (!spawnCols.includes(col)) continue;
      const elements = s.elements || [];
      if (this._spawnerGoalSatisfied(elements)) continue;
      const setRatio = Number(s.set_ratio ?? 1);
      let totalWeight = Number(s.total_weight ?? setRatio);
      if (totalWeight <= 0) totalWeight = setRatio;
      if (Math.random() >= setRatio / totalWeight) continue;
      if (elements.length === 0) continue;
      let totalRatio = 0;
      for (const e of elements) totalRatio += Number(e.ratio ?? 1);
      const roll = randi(totalRatio);
      let accum = 0;
      for (const e of elements) {
        accum += Number(e.ratio ?? 1);
        if (roll < accum) {
          this._turnSpawnCount++;
          return String(e.tile_id || '');
        }
      }
    }
    return '';
  }

  _spawnerGoalSatisfied(elements) {
    for (const e of elements) {
      const tileId = String(e.tile_id || '');
      if (tileId === '') continue;
      const family = tileFamily(tileId);
      for (const obj of GameManager.levelObjectives) {
        if (tileFamily(String(obj.tile_id || '')) !== family) continue;
        const target = Number(obj.target || 0);
        const current = Number(obj.current || 0);
        if (current + this._countFamilyOnBoard(family) >= target) return true;
      }
    }
    return false;
  }

  _countFamilyOnBoard(family) {
    let count = 0;
    const counted = new Set();
    for (const obs of this.obstacleMapRef.values()) {
      const tid = String(obs.tile_id || '');
      if (tileFamily(tid) !== family) continue;
      const instId = String(obs.instance_id || '');
      if (instId !== '') {
        if (counted.has(instId)) continue;
        counted.add(instId);
      }
      count++;
    }
    return count;
  }

  removeCandyAt(pos) {
    if (pos.x < 0 || pos.x >= this.width || pos.y < 0 || pos.y >= this.height) return null;
    const candy = this.grid[pos.x][pos.y];
    this.grid[pos.x][pos.y] = null;
    return candy;
  }

  setCandyAt(pos, candy) {
    this.grid[pos.x][pos.y] = candy;
    if (candy) candy.gridPos = { ...pos };
  }

  getCandyAt(pos) {
    if (pos.x < 0 || pos.x >= this.width || pos.y < 0 || pos.y >= this.height) return null;
    return this.grid[pos.x][pos.y];
  }

  createSpecialCandy(color, gridPos, candyType) {
    const candy = this._createCandy(color, gridPos, candyType);
    this.grid[gridPos.x][gridPos.y] = candy;
    candy.animateSpawn();
    return candy;
  }
}
