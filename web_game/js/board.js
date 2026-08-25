// board.js — 移植 game_board.gd：swap/道具觸發/連鎖爆炸/障礙物傷害/cascade/勝負
import { K, XY, DIRS4, sleep, randi, shuffleArray } from './util.js';
import { awaitTweensSafe } from './tween.js';
import * as MatchFinder from './match_finder.js';
import * as Audio from './audio.js';
import { GameManager, GameState } from './game_manager.js';
import { BoardFiller, fallDuration } from './board_filler.js';
import { BoardRenderer } from './board_render.js';
import { EffectSpawner } from './effects.js';
import {
  CandyType, CANDY_IDX_TO_COLOR_NAME, elimRule, isMovableObstacle,
  isHitsModeObstacle, tileFamily, PLANE_WEIGHT_BY_PREFIX,
  getComboResult, getStripedHTargets, getStripedVTargets,
  getWrappedTargets, getBigWrappedTargets, getCrossTargets, SPECIAL_SPRITE,
} from './tiles.js';
import { ArtTheme } from './theme.js';

const EXPLODE_MODE_MATCH = 0;
const EXPLODE_MODE_SPECIAL = 1;
const EXPLODE_MODE_PLANE = 2;

export class GameBoard {
  constructor(app, root) {
    this.app = app;
    this.root = root;                 // PIXI.Container
    this.gridWidth = 9;
    this.gridHeight = 9;
    this.cellSize = 70;
    this.boardOffset = { x: 0, y: 0 };
    this.blockedCells = new Set();    // "x,y"
    this.obstacleMap = new Map();     // "x,y" → obs
    this.bottomObstacleMap = new Map();
    this._obstacleDamageMode = EXPLODE_MODE_MATCH;

    this.selectedCandy = null;
    this.selectedMovableObs = null;   // {x,y} | null
    this._obsDragFrom = null;
    this._obsDragging = false;
    this._obsDragStart = { x: 0, y: 0 };
    this.isProcessing = false;
    this.cascadeLevel = 0;
    this._damageTickId = 0;
    this._upperBlockedBottomTick = new Map();
    this._stampGoalLastTick = new Map();
    this._planeBatchClaimed = [];
    this._deferredQueue = [];
    this._deferredRunning = false;
    this._destroyed = false;

    this._hintTimer = 0;
    this._hintDelay = 3.0;
    this._hintCandies = [];
    this._hintShown = false;
    this._lockWatchdog = 0;
    this._flushWatchdog = 0;
    this._stuckWatchdog = 0;

    this.onGoalFly = null;            // (worldPos, family) → void，HUD 接
    this.onTurnCompleted = null;

    // 圖層
    this.bgLayer = new PIXI.Container();
    this.obstacleLayer = new PIXI.Container();
    this.candyContainer = new PIXI.Container();
    this.mudLayer = new PIXI.Container();
    this.effectLayer = new PIXI.Container();
    this.effectLayer.sortableChildren = true;
    root.addChild(this.bgLayer, this.obstacleLayer, this.candyContainer, this.mudLayer, this.effectLayer);

    this.renderer = new BoardRenderer(this, this.bgLayer, this.obstacleLayer, this.mudLayer);
    this.effects = new EffectSpawner(this.effectLayer, app.ticker);
    this.effects.shakeTarget = root;   // 爆炸時震整個盤面
    this.filler = null;

    this._tickerFn = (tk) => {
      try {
        this._process(tk.deltaMS / 1000);
      } catch (e) {
        console.warn('[board] process 例外:', e);
      }
    };
    app.ticker.add(this._tickerFn);
    this._setupInput();
  }

  destroy() {
    this._destroyed = true;
    this.app.ticker.remove(this._tickerFn);
    this._teardownInput();
    this.root.destroy({ children: true });
  }

  // ============ 佈局 ============

  calculateOffset(viewportW, viewportH) {
    // 固定版面配額：上 HUD 130px、下排 UI 120px，棋盤只用中間區並在其中置中
    const TOP = 130, BOTTOM = 120;
    const availH = Math.max(viewportH - TOP - BOTTOM, 200);
    const maxW = viewportW * 0.90;
    const maxH = availH * 0.96;
    const fit = Math.min(maxW / this.gridWidth, maxH / this.gridHeight);
    this.cellSize = Math.min(Math.max(fit, 24), 70);
    if (this.filler) this.filler.cellSize = this.cellSize;
    const boardW = this.gridWidth * this.cellSize;
    const boardH = this.gridHeight * this.cellSize;
    this.boardOffset = {
      x: (viewportW - boardW) / 2,
      y: TOP + (availH - boardH) / 2,
    };
  }

  relayout(viewportW, viewportH) {
    this.calculateOffset(viewportW, viewportH);
    if (this.filler) {
      this.filler.boardOffset = this.boardOffset;
      for (let x = 0; x < this.gridWidth; x++) {
        for (let y = 0; y < this.gridHeight; y++) {
          const candy = this.filler.getCandyAt({ x, y });
          if (candy) {
            candy.cellSize = this.cellSize;
            candy.redraw();
            const w = this.filler.gridToWorld({ x, y });
            candy.node.position.set(w.x, w.y);
          }
        }
      }
    }
    this.renderer.redraw();
  }

  setObstacleMap(obs) { this.obstacleMap = obs; }
  setBottomObstacleMap(obs) { this.bottomObstacleMap = obs; }

  // ============ 初始化 ============

  initBoard(levelData, viewportW, viewportH) {
    this.levelData = levelData;
    this.gridWidth = levelData.gridWidth;
    this.gridHeight = levelData.gridHeight;
    this.blockedCells = new Set(levelData.blockedCells.map((p) => K(p.x, p.y)));
    this.calculateOffset(viewportW, viewportH);
    this.filler = new BoardFiller();

    const prePlaced = levelData.prePlacedSpecials || [];
    const initSkip = new Set(this.blockedCells);
    for (const sp of prePlaced) initSkip.add(K(sp.pos.x, sp.pos.y));

    this.filler.setup(this.gridWidth, this.gridHeight, this.cellSize, this.boardOffset, this.candyContainer, initSkip);
    if (levelData.numColors > 0) this.filler.numColors = levelData.numColors;
    this.filler.voidCells = new Set(levelData.voidCells.map((p) => K(p.x, p.y)));

    const movableCells = new Set();
    for (const [k, obs] of this.obstacleMap) {
      if (isMovableObstacle(String(obs.tile_id || ''))) movableCells.add(k);
    }
    this.filler.movableObstacleCells = movableCells;

    this.filler.fillInitial();

    // 重洗到「沒有預先連線 + 有可走一步」
    let retry = 0;
    while (retry < 50) {
      const hasMatch = MatchFinder.findAllMatches(this.filler.grid, this.gridWidth, this.gridHeight, initSkip).length > 0;
      const hasMove = MatchFinder.findHintMove(this.filler.grid, this.gridWidth, this.gridHeight, initSkip).length >= 2;
      if (!hasMatch && hasMove) break;
      this._clearBoard();
      this.filler.setup(this.gridWidth, this.gridHeight, this.cellSize, this.boardOffset, this.candyContainer, initSkip);
      if (levelData.numColors > 0) this.filler.numColors = levelData.numColors;
      this.filler.fillInitial();
      retry++;
    }

    // Puddle/預置道具格解封 — blockedCells 與 filler 共用同一個 Set
    this.filler.blockedCells = this.blockedCells;

    if (levelData.spawnerData.length > 0) {
      this.filler.setSpawners(levelData.spawnerData);
      this.filler.obstacleMapRef = this.obstacleMap;
      this.filler.onObstacleSpawned = (pos, tileId) => this._onObstacleSpawned(pos, tileId);
    }

    // 預置道具
    for (const sp of prePlaced) {
      const candyType = { striped_h: 1, striped_v: 2, wrapped: 3, spiral: 5, color_bomb: 4 }[sp.type_name] ?? -1;
      if (candyType < 0) continue;
      const color = candyType === CandyType.COLOR_BOMB ? 0 : randi(this.filler.numColors);
      this.filler.createSpecialCandy(color, sp.pos, candyType);
    }

    this._syncCandyLayerVisibility();
    this.renderer.redraw();
  }

  _clearBoard() {
    this.candyContainer.removeChildren().forEach((c) => c.destroy({ children: true }));
  }

  // ============ 看門狗 + 提示 ============

  _process(delta) {
    if (this._destroyed) return;
    if (this.isProcessing) {
      this._stuckWatchdog += delta;
      if (this._deferredQueue.length === 0 && !this._deferredRunning) {
        this._lockWatchdog += delta;
        this._flushWatchdog = 0;
      } else if (this._deferredRunning) {
        this._flushWatchdog += delta;
        this._lockWatchdog = 0;
      } else {
        this._lockWatchdog = 0;
        this._flushWatchdog = 0;
      }
      if (this._lockWatchdog > 4 || this._flushWatchdog > 5 || this._stuckWatchdog > 5) {
        this._lockWatchdog = this._flushWatchdog = this._stuckWatchdog = 0;
        console.warn('[watchdog] is_processing 卡住 → 強制解鎖');
        this._deferredRunning = false;
        this._deferredQueue = [];
        this.isProcessing = false;
        this._postTurnCheck();
      }
    } else {
      this._lockWatchdog = this._flushWatchdog = this._stuckWatchdog = 0;
    }

    if (!this.filler || this.isProcessing || this._hintShown) return;
    this._hintTimer += delta;
    if (this._hintTimer >= this._hintDelay) this._showHint();
  }

  _resetHintTimer() {
    this._hintTimer = 0;
    if (this._hintShown) this._clearHint();
  }

  _showHint() {
    let move = MatchFinder.findHintMove(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells);
    if (move.length < 2) move = this._findMovableSwapHint();
    if (move.length < 2) return;
    this._hintShown = true;
    for (const pos of move) {
      const candy = this.filler.getCandyAt(pos);
      if (candy && !candy.node.destroyed) {
        candy.playHint();
        this._hintCandies.push(candy);
      }
    }
  }

  _clearHint() {
    for (const candy of this._hintCandies) {
      if (!candy.node.destroyed) candy.stopHint();
    }
    this._hintCandies = [];
    this._hintShown = false;
  }

  // ============ 輸入（點選 / 滑動 / 拖障礙物）============

  _setupInput() {
    const canvas = this.app.canvas;
    this._pointerDown = (e) => this._onPointerDown(e);
    this._pointerMove = (e) => this._onPointerMove(e);
    this._pointerUp = () => { this._dragCandy = null; this._obsDragging = false; this._obsDragFrom = null; };
    canvas.addEventListener('pointerdown', this._pointerDown);
    canvas.addEventListener('pointermove', this._pointerMove);
    window.addEventListener('pointerup', this._pointerUp);
  }

  _teardownInput() {
    const canvas = this.app.canvas;
    canvas.removeEventListener('pointerdown', this._pointerDown);
    canvas.removeEventListener('pointermove', this._pointerMove);
    window.removeEventListener('pointerup', this._pointerUp);
  }

  _eventPos(e) {
    const rect = this.app.canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  _globalToGrid(p) {
    const gx = Math.floor((p.x - this.boardOffset.x) / this.cellSize);
    const gy = Math.floor((p.y - this.boardOffset.y) / this.cellSize);
    if (gx < 0 || gx >= this.gridWidth || gy < 0 || gy >= this.gridHeight) return null;
    return { x: gx, y: gy };
  }

  _onPointerDown(e) {
    if (this.isProcessing || !this.filler) return;
    Audio.unlockAudio();
    const p = this._eventPos(e);
    const gridPos = this._globalToGrid(p);
    if (!gridPos) return;
    const candy = this.filler.getCandyAt(gridPos);
    if (candy && !candy.isBeingDestroyed && !candy.isMoving) {
      // 距糖中心 < 0.5 cell 才算點中（對齊 candy._input）
      const w = this.filler.gridToWorld(gridPos);
      const dx = p.x - w.x, dy = p.y - w.y;
      if (Math.hypot(dx, dy) < this.cellSize * 0.5) {
        this._dragCandy = candy;
        this._dragStart = p;
        this._onCandySelected(candy);
        return;
      }
    }
    // 該格只有桶/錐、沒有糖 → 當障礙物拖動
    if (this._isMovableObstacleAt(gridPos) && this.filler.getCandyAt(gridPos) === null) {
      this._obsDragFrom = gridPos;
      this._obsDragging = true;
      this._obsDragStart = p;
      this._onMovableObstaclePressed(gridPos);
    }
  }

  _onPointerMove(e) {
    if (this.isProcessing || !this.filler) return;
    const p = this._eventPos(e);
    if (this._dragCandy) {
      const diff = { x: p.x - this._dragStart.x, y: p.y - this._dragStart.y };
      if (Math.hypot(diff.x, diff.y) > this.cellSize * 0.35) {
        const candy = this._dragCandy;
        this._dragCandy = null;
        const dir = Math.abs(diff.x) > Math.abs(diff.y)
          ? { x: diff.x > 0 ? 1 : -1, y: 0 }
          : { x: 0, y: diff.y > 0 ? 1 : -1 };
        this._onCandySwiped(candy, dir);
      }
    } else if (this._obsDragging && this._obsDragFrom) {
      const diff = { x: p.x - this._obsDragStart.x, y: p.y - this._obsDragStart.y };
      if (Math.hypot(diff.x, diff.y) > this.cellSize * 0.35) {
        this._obsDragging = false;
        const dir = Math.abs(diff.x) > Math.abs(diff.y)
          ? { x: diff.x > 0 ? 1 : -1, y: 0 }
          : { x: 0, y: diff.y > 0 ? 1 : -1 };
        this._onMovableObstacleSwiped(this._obsDragFrom, dir);
        this._obsDragFrom = null;
      }
    }
  }

  _onCandySelected(candy) {
    if (this.isProcessing) return;
    this._resetHintTimer();
    this._clearSelectedMovableObs();

    if (this.selectedCandy === null) {
      this.selectedCandy = candy;
      candy.setSelected(true);
      return;
    }
    if (this.selectedCandy === candy) {
      if (candy.candyType !== CandyType.NORMAL) {
        this.selectedCandy.setSelected(false);
        this.selectedCandy = null;
        this._activateSpecialDirectly(candy);
        return;
      }
      this.selectedCandy.setSelected(false);
      this.selectedCandy = null;
      return;
    }
    const dist = {
      x: Math.abs(candy.gridPos.x - this.selectedCandy.gridPos.x),
      y: Math.abs(candy.gridPos.y - this.selectedCandy.gridPos.y),
    };
    if ((dist.x === 1 && dist.y === 0) || (dist.x === 0 && dist.y === 1)) {
      if (this._isMovableObstacleAt(candy.gridPos)) {
        this._trySwapWithMovableObstacle(this.selectedCandy, candy.gridPos);
      } else if (this._isMovableObstacleAt(this.selectedCandy.gridPos)) {
        this._trySwapWithMovableObstacle(candy, this.selectedCandy.gridPos);
      } else {
        this._trySwap(this.selectedCandy, candy);
      }
    } else {
      this.selectedCandy.setSelected(false);
      this.selectedCandy = candy;
      candy.setSelected(true);
    }
  }

  _onCandySwiped(candy, direction) {
    if (this.isProcessing) return;
    this._resetHintTimer();
    const targetPos = { x: candy.gridPos.x + direction.x, y: candy.gridPos.y + direction.y };
    if (targetPos.x < 0 || targetPos.x >= this.gridWidth || targetPos.y < 0 || targetPos.y >= this.gridHeight) return;
    const tk = K(targetPos.x, targetPos.y);
    if (this.blockedCells.has(tk)) {
      // 可移動障礙物可被 swap
      if (this.obstacleMap.has(tk)) {
        const tidObs = String(this.obstacleMap.get(tk).tile_id || '');
        if (isMovableObstacle(tidObs)
            && !this._isCandyLocked(candy.gridPos)
            && this._canCandySwapWithMovable(candy.gridPos)) {
          if (this.selectedCandy) { this.selectedCandy.setSelected(false); this.selectedCandy = null; }
          this._trySwapWithMovableObstacle(candy, targetPos);
        }
      }
      return;
    }
    const targetCandy = this.filler.getCandyAt(targetPos);
    if (targetCandy === null) {
      if (!this._isPlayableCell(targetPos)) return;
      if (this._isCandyLocked(candy.gridPos)) return;
      if (this.selectedCandy) { this.selectedCandy.setSelected(false); this.selectedCandy = null; }
      this._tryMoveIntoEmpty(candy, targetPos);
      return;
    }
    if (this._isCandyLocked(candy.gridPos) || this._isCandyLocked(targetPos)) return;
    if (this.selectedCandy) { this.selectedCandy.setSelected(false); this.selectedCandy = null; }
    this._trySwap(candy, targetCandy);
  }

  _isPlayableCell(pos) {
    return pos.x >= 0 && pos.x < this.gridWidth && pos.y >= 0 && pos.y < this.gridHeight
      && !this.blockedCells.has(K(pos.x, pos.y));
  }

  _isMovableObstacleAt(pos) {
    const obs = this.obstacleMap.get(K(pos.x, pos.y));
    return !!obs && isMovableObstacle(String(obs.tile_id || ''));
  }

  _canCandySwapWithMovable(fromPos) {
    if (this.filler.getCandyAt(fromPos) === null) return false;
    const obs = this.obstacleMap.get(K(fromPos.x, fromPos.y));
    if (!obs) return true;
    const tid = String(obs.tile_id || '');
    if (tid.startsWith('Puddle') || tid.startsWith('Rope') || tid.startsWith('Mud')) return true;
    return isMovableObstacle(tid);
  }

  _clearSelectedMovableObs() {
    this.selectedMovableObs = null;
    this.renderer.redrawObstacles();
  }

  _isCandyLocked(pos) {
    const obs = this.obstacleMap.get(K(pos.x, pos.y));
    return !!obs && obs.type === 'wire';
  }

  _hasMudAt(pos) {
    const obs = this.obstacleMap.get(K(pos.x, pos.y));
    return !!obs && String(obs.tile_id || '').startsWith('Mud');
  }

  _obstacleCoversBottomAt(pos) { return this.obstacleMap.has(K(pos.x, pos.y)); }

  _syncCandyLayerVisibility() {
    if (!this.filler) return;
    for (let x = 0; x < this.gridWidth; x++) {
      for (let y = 0; y < this.gridHeight; y++) {
        const c = this.filler.getCandyAt({ x, y });
        if (!c || c.node.destroyed) continue;
        c.node.visible = !this._hasMudAt({ x, y });
      }
    }
  }

  // ============ Swap 流程 ============

  async _tryMoveIntoEmpty(candy, emptyPos) {
    this.isProcessing = true;
    this._resetHintTimer();
    const fromPos = { ...candy.gridPos };
    const worldTo = this.filler.gridToWorld(emptyPos);
    Audio.playSwapSound();
    this.filler.removeCandyAt(fromPos);
    this.filler.setCandyAt(emptyPos, candy);
    await awaitTweensSafe([candy.animateTo(worldTo)]);
    const matches = MatchFinder.findAllMatches(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells);
    if (matches.length === 0) {
      this.filler.removeCandyAt(emptyPos);
      this.filler.setCandyAt(fromPos, candy);
      await awaitTweensSafe([candy.animateTo(this.filler.gridToWorld(fromPos))]);
      this.isProcessing = false;
      return;
    }
    GameManager.useMove();
    this.cascadeLevel = 0;
    await this._processMatches(matches, [fromPos, emptyPos]);
    if (this._deferredQueue.length === 0 && !this._deferredRunning) this._postTurnCheck();
  }

  async _trySwap(candyA, candyB) {
    this.isProcessing = true;
    this._resetHintTimer();
    this._clearSelectedMovableObs();
    if (this.selectedCandy) { this.selectedCandy.setSelected(false); this.selectedCandy = null; }
    Audio.playSwapSound();

    const posA = { ...candyA.gridPos };
    const posB = { ...candyB.gridPos };
    const worldA = this.filler.gridToWorld(posA);
    const worldB = this.filler.gridToWorld(posB);

    this.filler.setCandyAt(posA, candyB);
    this.filler.setCandyAt(posB, candyA);

    // 道具+道具 → 合成動畫：A 滑到 B 上疊合
    const bothSpecial = candyA.candyType !== CandyType.NORMAL && candyB.candyType !== CandyType.NORMAL;
    let tweenA;
    if (bothSpecial) {
      candyA.node.zIndex = 1;
      this.candyContainer.sortableChildren = true;
      tweenA = candyA.animateTo(worldB, 0.18);
    } else {
      tweenA = candyA.animateTo(worldB, 0.2);
      candyB.animateTo(worldA, 0.2);
    }
    await tweenA.finished;

    if (candyA.candyType === CandyType.COLOR_BOMB || candyB.candyType === CandyType.COLOR_BOMB) {
      this._handleColorBombSwap(candyA, candyB, posB);
      return;
    }

    const combo = getComboResult(candyA.candyType, candyB.candyType);
    if (combo.effect !== 'none') {
      GameManager.useMove();
      this.cascadeLevel = 0;
      await this._handleSpecialCombo(candyA, candyB, combo.effect);
      if (this._deferredQueue.length === 0 && !this._deferredRunning) this._postTurnCheck();
      return;
    }

    const matches = MatchFinder.findAllMatches(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells);
    const aSpecial = candyA.candyType !== CandyType.NORMAL;
    const bSpecial = candyB.candyType !== CandyType.NORMAL;

    if (matches.length === 0) {
      // 沒 match — special 當「滑出去施放」
      if (aSpecial || bSpecial) {
        const triggerCandy = aSpecial ? candyA : candyB;
        const spPos = { ...triggerCandy.gridPos };
        const spType = triggerCandy.candyType;
        const spColor = triggerCandy.candyColor;
        GameManager.useMove();
        this.cascadeLevel = 0;
        Audio.playSpecialTriggerSound();
        await this._spinUpIfStriped(triggerCandy);
        this._destroyCandyAt(spPos, spColor, EXPLODE_MODE_SPECIAL);
        this._chainTrigger(spType, spPos, spColor);
        await sleep(0.3);
        await this._cascadeLoop();
        if (this._deferredQueue.length === 0 && !this._deferredRunning) this._postTurnCheck();
        return;
      }
      // 真的無效 → 換回去
      Audio.playSwapBackSound();
      GameManager._emit('bad_swap');
      this.filler.setCandyAt(posA, candyA);
      this.filler.setCandyAt(posB, candyB);
      const tweenBack = candyA.animateTo(worldA, 0.2);
      candyB.animateTo(worldB, 0.2);
      await tweenBack.finished;
      this.isProcessing = false;
      return;
    }

    GameManager.useMove();
    this.cascadeLevel = 0;

    // 道具+元素 swap 成 match：道具先在落點引爆，與 match 同一波
    if (aSpecial !== bSpecial) {
      const pending = aSpecial ? candyA : candyB;
      const spType = pending.candyType;
      const spColor = pending.candyColor;
      Audio.playSpecialTriggerSound();
      await this._spinUpIfStriped(pending);
      this._destroyCandyAt(pending.gridPos, spColor, EXPLODE_MODE_SPECIAL);
      this._chainTrigger(spType, pending.gridPos, spColor);
      await sleep(0.05);
    }

    await this._processMatches(matches, [posA, posB]);
    if (this._deferredQueue.length === 0 && !this._deferredRunning) this._postTurnCheck();
  }

  // ============ 可移動障礙物（Barrel / TrafficCone）============

  _onMovableObstaclePressed(obsPos) {
    this._resetHintTimer();
    if (this.selectedCandy) {
      const dist = {
        x: Math.abs(this.selectedCandy.gridPos.x - obsPos.x),
        y: Math.abs(this.selectedCandy.gridPos.y - obsPos.y),
      };
      if ((dist.x === 1 && dist.y === 0) || (dist.x === 0 && dist.y === 1)) {
        this.selectedCandy.setSelected(false);
        const c = this.selectedCandy;
        this.selectedCandy = null;
        this._trySwapWithMovableObstacle(c, obsPos);
        return;
      }
      this.selectedCandy.setSelected(false);
      this.selectedCandy = null;
    }
    if (this.selectedMovableObs && this.selectedMovableObs.x === obsPos.x && this.selectedMovableObs.y === obsPos.y) {
      this._clearSelectedMovableObs();
      return;
    }
    this.selectedMovableObs = obsPos;
    this.renderer.redrawObstacles();
  }

  _onMovableObstacleSwiped(obsPos, direction) {
    if (!this._isMovableObstacleAt(obsPos)) return;
    this._resetHintTimer();
    this._clearSelectedMovableObs();
    const target = { x: obsPos.x + direction.x, y: obsPos.y + direction.y };
    if (target.x < 0 || target.x >= this.gridWidth || target.y < 0 || target.y >= this.gridHeight) return;
    const targetCandy = this.filler.getCandyAt(target);
    if (targetCandy && !this._isCandyLocked(targetCandy.gridPos)
        && this._canCandySwapWithMovable(targetCandy.gridPos)) {
      this._trySwapWithMovableObstacle(targetCandy, obsPos);
    } else if (this._isPlayableCell(target)) {
      this._runSwapMovableIntoEmpty(obsPos, target);
    }
  }

  _findMovableSwapHint() {
    if (!this.filler) return [];
    for (const k of this.obstacleMap.keys()) {
      const obsPos = XY(k);
      if (!this._isMovableObstacleAt(obsPos)) continue;
      for (const dir of DIRS4) {
        const candyPos = { x: obsPos.x + dir.x, y: obsPos.y + dir.y };
        if (candyPos.x < 0 || candyPos.x >= this.gridWidth || candyPos.y < 0 || candyPos.y >= this.gridHeight) continue;
        const candy = this.filler.getCandyAt(candyPos);
        if (candy === null) continue;
        if (this._wouldMatchAfterMovableSwap(candyPos, obsPos)) return [candyPos, obsPos];
      }
    }
    return [];
  }

  _wouldMatchAfterMovableSwap(candyPos, obsPos) {
    if (!this._canCandySwapWithMovable(candyPos)) return false;
    const cObs = this.obstacleMap.get(K(candyPos.x, candyPos.y));
    if (cObs && String(cObs.tile_id || '').startsWith('Puddle')) return false;
    const candy = this.filler.getCandyAt(candyPos);
    if (candy === null) return false;
    const obs = this.obstacleMap.get(K(obsPos.x, obsPos.y));
    // 模擬互換
    this.filler.setCandyAt(candyPos, null);
    this.filler.setCandyAt(obsPos, candy);
    this.obstacleMap.delete(K(obsPos.x, obsPos.y));
    this.obstacleMap.set(K(candyPos.x, candyPos.y), obs);
    const blockedSnapshot = new Set(this.blockedCells);
    this.blockedCells.delete(K(obsPos.x, obsPos.y));
    this.blockedCells.add(K(candyPos.x, candyPos.y));
    const found = MatchFinder.findAllMatches(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells).length > 0;
    // 還原
    this.filler.setCandyAt(obsPos, null);
    this.filler.setCandyAt(candyPos, candy);
    this.obstacleMap.delete(K(candyPos.x, candyPos.y));
    this.obstacleMap.set(K(obsPos.x, obsPos.y), obs);
    this.blockedCells.clear();
    for (const b of blockedSnapshot) this.blockedCells.add(b);
    return found;
  }

  async _runSwapMovableIntoEmpty(obsPos, emptyPos) {
    if (!this._isMovableObstacleAt(obsPos) || !this._isPlayableCell(emptyPos)) return;
    if (this.filler.getCandyAt(emptyPos) !== null) return;
    const obsK = K(obsPos.x, obsPos.y);
    const emptyK = K(emptyPos.x, emptyPos.y);
    const obs = this.obstacleMap.get(obsK);
    this.obstacleMap.delete(obsK);
    this.blockedCells.delete(obsK);
    this.filler.movableObstacleCells.delete(obsK);
    this.obstacleMap.set(emptyK, obs);
    this.blockedCells.add(emptyK);
    this.filler.movableObstacleCells.add(emptyK);
    this.renderer.redrawObstacles();
    const matches = MatchFinder.findAllMatches(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells);
    if (matches.length === 0) {
      this.obstacleMap.delete(emptyK);
      this.blockedCells.delete(emptyK);
      this.filler.movableObstacleCells.delete(emptyK);
      this.obstacleMap.set(obsK, obs);
      this.blockedCells.add(obsK);
      this.filler.movableObstacleCells.add(obsK);
      this.renderer.redrawObstacles();
      return;
    }
    this.isProcessing = true;
    this._resetHintTimer();
    GameManager.useMove();
    this.cascadeLevel = 0;
    await this._processMatches(matches, [obsPos, emptyPos]);
    if (this._deferredQueue.length === 0 && !this._deferredRunning) this._postTurnCheck();
  }

  async _trySwapWithMovableObstacle(candy, obsPos) {
    this.isProcessing = true;
    this._resetHintTimer();
    this._clearSelectedMovableObs();
    if (this.selectedCandy) { this.selectedCandy.setSelected(false); this.selectedCandy = null; }
    Audio.playSwapSound();

    const candyPos = { ...candy.gridPos };
    const cObs = this.obstacleMap.get(K(candyPos.x, candyPos.y));
    if (cObs && String(cObs.tile_id || '').startsWith('Puddle')) {
      this.isProcessing = false;
      return;
    }
    const worldCandy = this.filler.gridToWorld(candyPos);
    const worldObs = this.filler.gridToWorld(obsPos);
    const obsK = K(obsPos.x, obsPos.y);
    const candyK = K(candyPos.x, candyPos.y);
    const obs = this.obstacleMap.get(obsK);

    this.filler.setCandyAt(candyPos, null);
    this.filler.setCandyAt(obsPos, candy);
    this.obstacleMap.delete(obsK);
    this.obstacleMap.set(candyK, obs);
    this.blockedCells.delete(obsK);
    this.blockedCells.add(candyK);
    this.filler.movableObstacleCells.delete(obsK);
    this.filler.movableObstacleCells.add(candyK);

    const tweenA = candy.animateTo(worldObs, 0.2);
    this.renderer.redrawObstacles();
    await tweenA.finished;

    const matches = MatchFinder.findAllMatches(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells);
    const isSpecial = candy.candyType !== CandyType.NORMAL;
    if (matches.length === 0 && !isSpecial) {
      Audio.playSwapBackSound();
      GameManager._emit('bad_swap');
      this.filler.setCandyAt(obsPos, null);
      this.filler.setCandyAt(candyPos, candy);
      this.obstacleMap.delete(candyK);
      this.obstacleMap.set(obsK, obs);
      this.blockedCells.delete(candyK);
      this.blockedCells.add(obsK);
      this.filler.movableObstacleCells.delete(candyK);
      this.filler.movableObstacleCells.add(obsK);
      const tweenBack = candy.animateTo(worldCandy, 0.2);
      this.renderer.redrawObstacles();
      await tweenBack.finished;
      this.isProcessing = false;
      return;
    }

    GameManager.useMove();
    this.cascadeLevel = 0;

    if (matches.length === 0 && isSpecial) {
      Audio.playSpecialTriggerSound();
      const spType = candy.candyType;
      const spColor = candy.candyColor;
      await this._spinUpIfStriped(candy);
      this._destroyCandyAt(obsPos, spColor, EXPLODE_MODE_SPECIAL);
      this._chainTrigger(spType, obsPos, spColor);
      await sleep(0.3);
      await this._cascadeLoop();
      if (this._deferredQueue.length === 0 && !this._deferredRunning) this._postTurnCheck();
      return;
    }

    await this._processMatches(matches, [candyPos, obsPos]);
    if (this._deferredQueue.length === 0 && !this._deferredRunning) this._postTurnCheck();
  }

  // ============ 道具直接觸發 / 光球 ============

  // 條紋道具觸發前奏：自轉加速 + 微放大，播完才真正引爆。
  // ponytail: 只掛在「玩家直接觸發」路徑；cascade 連鎖引爆若也各等 1 秒會拖垮節奏
  async _spinUpIfStriped(candy) {
    if (!candy || candy.node.destroyed || candy.isBeingDestroyed) return;
    const ct = candy.candyType;
    if (ct !== CandyType.STRIPED_H && ct !== CandyType.STRIPED_V) return;
    const frames = await ArtTheme.loadSpinFrames(SPECIAL_SPRITE[ct]);
    Audio.playSpinUpSound();
    await candy.playSpinUp(frames).finished;
  }

  async _activateSpecialDirectly(candy) {
    this.isProcessing = true;
    GameManager.useMove();
    this.cascadeLevel = 0;
    Audio.playSpecialTriggerSound();
    const pos = { ...candy.gridPos };
    const ct = candy.candyType;

    if (ct === CandyType.COLOR_BOMB) {
      // 挑盤面最多的顏色 + 點亮動畫
      const colorCount = new Map();
      for (let x = 0; x < this.gridWidth; x++) {
        for (let y = 0; y < this.gridHeight; y++) {
          const c = this.filler.getCandyAt({ x, y });
          if (c && !c.isBeingDestroyed && c.candyType === CandyType.NORMAL) {
            colorCount.set(c.candyColor, (colorCount.get(c.candyColor) || 0) + 1);
          }
        }
      }
      let targetColor = 0, best = -1;
      for (const [col, cnt] of colorCount) {
        if (cnt > best) { best = cnt; targetColor = col; }
      }
      this._destroyCandyAt(pos, candy.candyColor, EXPLODE_MODE_SPECIAL);
      const ncTargets = [];
      for (let x = 0; x < this.gridWidth; x++) {
        for (let y = 0; y < this.gridHeight; y++) {
          const c = this.filler.getCandyAt({ x, y });
          if (c && !c.isBeingDestroyed && c.candyColor === targetColor && c.candyType === CandyType.NORMAL) {
            ncTargets.push({ x, y });
          }
        }
      }
      await this._animateColorBombSequence(ncTargets, pos, -1);
    } else {
      await this._spinUpIfStriped(candy);
      this._triggerSpecialCandy(candy);
      if (this.obstacleMap.has(K(pos.x, pos.y))) this._damageObstacle(pos);
      this.effects.spawnDestroyEffect(this.filler.gridToWorld(pos), candy.candyColor);
      this.filler.removeCandyAt(pos);
      candy.animateDestroy();
    }

    await sleep(0.3);
    await this._cascadeLoop();
    this._syncCandyLayerVisibility();
    if (this._deferredQueue.length === 0 && !this._deferredRunning) this._postTurnCheck();
  }

  async _handleColorBombSwap(candyA, candyB, dragDest) {
    GameManager.useMove();
    this.cascadeLevel = 0;
    const bomb = candyA.candyType === CandyType.COLOR_BOMB ? candyA : candyB;
    const other = bomb === candyA ? candyB : candyA;
    const targetColor = other.candyColor;
    const orbPos = other.candyType === CandyType.NORMAL
      ? { ...bomb.gridPos }
      : (dragDest && dragDest.x >= 0 ? dragDest : { ...bomb.gridPos });
    Audio.playSpecialTriggerSound();

    const collectColorTargets = (normalOnly) => {
      const out = [];
      for (let x = 0; x < this.gridWidth; x++) {
        for (let y = 0; y < this.gridHeight; y++) {
          const c = this.filler.getCandyAt({ x, y });
          if (c && !c.isBeingDestroyed && c.candyColor === targetColor
              && (!normalOnly || c.candyType === CandyType.NORMAL)) {
            out.push({ x, y });
          }
        }
      }
      return out;
    };

    if (other.candyType === CandyType.COLOR_BOMB) {
      const toDestroy = [];
      for (let x = 0; x < this.gridWidth; x++) {
        for (let y = 0; y < this.gridHeight; y++) {
          const cc = this.filler.getCandyAt({ x, y });
          if (cc && !cc.isBeingDestroyed) toDestroy.push({ x, y });
        }
      }
      this._destroyCandyAt(bomb.gridPos, targetColor, EXPLODE_MODE_SPECIAL);
      this._destroyCandyAt(other.gridPos, targetColor, EXPLODE_MODE_SPECIAL);
      await this._animateColorBombSequence(toDestroy, orbPos, -1, false, 0.03);
    } else if (other.candyType === CandyType.STRIPED_H || other.candyType === CandyType.STRIPED_V) {
      this._destroyCandyAt(bomb.gridPos, targetColor, EXPLODE_MODE_SPECIAL);
      this._destroyCandyAt(other.gridPos, targetColor, EXPLODE_MODE_SPECIAL);
      await this._animateColorBombSequence(collectColorTargets(false), orbPos, CandyType.STRIPED_H, true);
    } else if (other.candyType === CandyType.WRAPPED) {
      this._destroyCandyAt(bomb.gridPos, targetColor, EXPLODE_MODE_SPECIAL);
      this._destroyCandyAt(other.gridPos, targetColor, EXPLODE_MODE_SPECIAL);
      await this._animateColorBombSequence(collectColorTargets(false), orbPos, CandyType.WRAPPED);
    } else if (other.candyType === CandyType.SPIRAL) {
      this._destroyCandyAt(bomb.gridPos, targetColor, EXPLODE_MODE_SPECIAL);
      this._destroyCandyAt(other.gridPos, targetColor, EXPLODE_MODE_SPECIAL);
      await this._animateColorBombSequence(collectColorTargets(false), orbPos, CandyType.SPIRAL);
    } else {
      this._destroyCandyAt(bomb.gridPos, targetColor, EXPLODE_MODE_SPECIAL);
      await this._animateColorBombSequence(collectColorTargets(true), orbPos, -1);
    }

    await sleep(0.3);
    await this._cascadeLoop();
    this._syncCandyLayerVisibility();
    if (this._deferredQueue.length === 0 && !this._deferredRunning) this._postTurnCheck();
  }

  async _animateColorBombSequence(targets, bombPos, transformTo, randomizeStriped = false, stagger = 0.05) {
    const n = targets.length;
    if (n === 0) return;
    const maxSteps = 12;
    const stepSize = Math.max(1, Math.ceil(n / maxSteps));
    const steps = Math.ceil(n / stepSize);
    const batchWait = Math.min(stagger * stepSize, 0.06);
    const orbDuration = Math.max(steps * batchWait + 0.2, 0.45);
    this.effects.spawnColorBombOrb(this.filler.gridToWorld(bombPos), orbDuration);
    let i = 0;
    while (i < n) {
      const batchEnd = Math.min(i + stepSize, n);
      for (let j = i; j < batchEnd; j++) {
        const pos2 = targets[j];
        const c2 = this.filler.getCandyAt(pos2);
        if (!c2 || c2.isBeingDestroyed) continue;
        this.effects.spawnTargetHighlight(this.filler.gridToWorld(pos2), c2.candyColor);
        if (transformTo >= 0) {
          let ttype = transformTo;
          if (randomizeStriped) ttype = [CandyType.STRIPED_H, CandyType.STRIPED_V][randi(2)];
          c2.setCandyType(ttype);
        }
      }
      i = batchEnd;
      await sleep(batchWait);
    }
    await sleep(0.15);
    if (transformTo < 0) {
      this._explodeCellsNoChain(targets);
    } else {
      this._planeBatchClaimed = [];
      this._explodeCells(targets, EXPLODE_MODE_SPECIAL);
      this._planeBatchClaimed = [];
    }
  }

  _destroyCandyAt(pos, colorForSignal, mode = EXPLODE_MODE_MATCH) {
    const c = this.filler.getCandyAt(pos);
    if (c && !c.isBeingDestroyed) {
      if (mode === EXPLODE_MODE_PLANE || mode === EXPLODE_MODE_SPECIAL) {
        if (this.obstacleMap.has(K(pos.x, pos.y))) this._damageObstacle(pos);
        if (this.bottomObstacleMap.has(K(pos.x, pos.y))) this._damageBottomObstacle(pos);
      } else {
        this._triggerObstacleAdjacent(pos, c.candyColor);
      }
      this.effects.spawnDestroyEffect(this.filler.gridToWorld(pos), c.candyColor);
      this.filler.removeCandyAt(pos);
      c.animateDestroy();
      GameManager.addScore(1, true);
    }
  }

  // ============ 連鎖消除 ============

  // 整排掃射每格延遲（秒）— 與 spawnRocketSweep 的火箭速度對齊
  static SWEEP_SEC_PER_CELL = 0.03;

  // 條紋糖掃射視覺：火箭往兩側飛 + 回傳「依距離起爆」的 delayFn
  _stripedSweepFx(pos, axis) {
    const cs = this.cellSize;
    const sec = GameBoard.SWEEP_SEC_PER_CELL;
    const span = axis === 'h'
      ? { neg: pos.x * cs, pos: (this.gridWidth - 1 - pos.x) * cs }
      : { neg: pos.y * cs, pos: (this.gridHeight - 1 - pos.y) * cs };
    this.effects.spawnRocketSweep(this.filler.gridToWorld(pos), axis, span, cs, sec);
    return (p) => (axis === 'h' ? Math.abs(p.x - pos.x) : Math.abs(p.y - pos.y)) * sec;
  }

  _explodeCells(targets, mode = EXPLODE_MODE_MATCH, delayFn = null) {
    this._obstacleDamageMode = mode;
    this._damageTickId++;
    const chainQueue = [];
    const destroyedCells = [];
    for (const pos of targets) {
      const k = K(pos.x, pos.y);
      const c = this.filler.getCandyAt(pos);
      if (!c || c.isBeingDestroyed) {
        if (mode === EXPLODE_MODE_PLANE || mode === EXPLODE_MODE_SPECIAL) {
          if (this.obstacleMap.has(k)) {
            this._damageObstacle(pos);
            this.effects.spawnDestroyEffect(this.filler.gridToWorld(pos), 0);
          }
          if (this.bottomObstacleMap.has(k)) {
            this._damageBottomObstacle(pos);
            if (!this.obstacleMap.has(k)) this.effects.spawnDestroyEffect(this.filler.gridToWorld(pos), 0);
          }
          destroyedCells.push(pos);
        } else {
          this._triggerObstacleAdjacent(pos, -1);
        }
        continue;
      }
      const ct = c.candyType;
      const color = c.candyColor;
      if (ct !== CandyType.NORMAL) chainQueue.push({ pos, type: ct, color });
      if (mode === EXPLODE_MODE_PLANE || mode === EXPLODE_MODE_SPECIAL) {
        if (this.obstacleMap.has(k)) this._damageObstacle(pos);
        if (this.bottomObstacleMap.has(k)) this._damageBottomObstacle(pos);
      } else {
        this._triggerObstacleAdjacent(pos, color);
      }
      const d = delayFn ? delayFn(pos) : 0;
      if (d > 0) {
        const w = this.filler.gridToWorld(pos);
        setTimeout(() => { if (!this._destroyed) this.effects.spawnDestroyEffect(w, color); }, d * 1000);
      } else {
        this.effects.spawnDestroyEffect(this.filler.gridToWorld(pos), color);
      }
      this.filler.removeCandyAt(pos);
      c.animateDestroy(d);
      destroyedCells.push(pos);
    }
    if (mode !== EXPLODE_MODE_MATCH && destroyedCells.length > 0) {
      this._triggerManufacturersAdjacentToCells(destroyedCells);
    }
    for (const ch of chainQueue) this._chainTrigger(ch.type, ch.pos, ch.color);
  }

  _explodeCellsNoChain(targets) {
    this._obstacleDamageMode = EXPLODE_MODE_MATCH;
    this._damageTickId++;
    for (const pos of targets) {
      const c = this.filler.getCandyAt(pos);
      if (!c || c.isBeingDestroyed) {
        this._triggerObstacleAdjacent(pos, -1);
        continue;
      }
      const color = c.candyColor;
      this._triggerObstacleAdjacent(pos, color);
      this.effects.spawnDestroyEffect(this.filler.gridToWorld(pos), color);
      this.filler.removeCandyAt(pos);
      c.animateDestroy();
    }
  }

  _chainTrigger(ct, pos, color) {
    const subTargets = [];
    let delayFn = null;
    switch (ct) {
      case CandyType.STRIPED_H:
        Audio.playSpecialTriggerSound();
        for (let x = 0; x < this.gridWidth; x++) if (x !== pos.x) subTargets.push({ x, y: pos.y });
        delayFn = this._stripedSweepFx(pos, 'h');
        break;
      case CandyType.STRIPED_V:
        Audio.playSpecialTriggerSound();
        for (let y = 0; y < this.gridHeight; y++) if (y !== pos.y) subTargets.push({ x: pos.x, y });
        delayFn = this._stripedSweepFx(pos, 'v');
        break;
      case CandyType.WRAPPED:
        Audio.playSpecialTriggerSound();
        this.effects.spawnShockwave(this.filler.gridToWorld(pos));
        subTargets.push(...getWrappedTargets(pos, this.gridWidth, this.gridHeight));
        break;
      case CandyType.SPIRAL: {
        Audio.playSpecialTriggerSound();
        this.effects.spawnShockwave(this.filler.gridToWorld(pos));
        for (const off of DIRS4) {
          const tp = { x: pos.x + off.x, y: pos.y + off.y };
          if (tp.x >= 0 && tp.x < this.gridWidth && tp.y >= 0 && tp.y < this.gridHeight) subTargets.push(tp);
        }
        const exclPlane = [pos, ...this._planeBatchClaimed];
        const picks = this._pickTopPlaneTargets(1, exclPlane);
        if (picks.length > 0) {
          const tgt = picks[0];
          this._planeBatchClaimed.push(tgt);
          const fromWs = this.filler.gridToWorld(pos);
          const toWs = this.filler.gridToWorld(tgt);
          this.effects.spawnPlaneFlight(fromWs, toWs, color, 1.0);
          this._deferredPlaneImpact(toWs, 0.92);
          this._deferredExplode([tgt], 1.0, EXPLODE_MODE_PLANE);
        }
        break;
      }
      case CandyType.COLOR_BOMB: {
        Audio.playSpecialTriggerSound();
        this.effects.spawnFirework(this.filler.gridToWorld(pos));
        const picked = randi(this.filler ? this.filler.numColors : 4);
        for (let x = 0; x < this.gridWidth; x++) {
          for (let y = 0; y < this.gridHeight; y++) {
            const c2 = this.filler.getCandyAt({ x, y });
            if (c2 && !c2.isBeingDestroyed && c2.candyColor === picked && c2.candyType === CandyType.NORMAL) {
              subTargets.push({ x, y });
            }
          }
        }
        break;
      }
    }
    this._explodeCells(subTargets, EXPLODE_MODE_SPECIAL, delayFn);
  }

  _deferredExplode(targets, delay, mode = EXPLODE_MODE_MATCH) {
    const entry = { targets, mode, ready: false };
    this._deferredQueue.push(entry);
    setTimeout(() => {
      entry.ready = true;
      this._tryFlushDeferredQueue();
    }, delay * 1000);
  }

  async _tryFlushDeferredQueue() {
    if (this._deferredRunning || this._destroyed) return;
    this._deferredRunning = true;
    while (this._deferredQueue.length > 0 && this._deferredQueue[0].ready) {
      const entry = this._deferredQueue.shift();
      if (this._destroyed) break;
      if (GameManager.currentState === GameState.LEVEL_COMPLETE) break;
      this._explodeCells(entry.targets, entry.mode);
      await this._cascadeLoop();
      this._syncCandyLayerVisibility();
    }
    this._deferredRunning = false;
    if (this._deferredQueue.length === 0) {
      this._postTurnCheck();
    } else {
      setTimeout(() => this._tryFlushDeferredQueue(), 120);
    }
  }

  _deferredPlaneImpact(worldPos, delay) {
    setTimeout(() => {
      if (!this._destroyed) this.effects.spawnPlaneImpact(worldPos);
    }, delay * 1000);
  }

  // ============ 道具 + 道具 combo ============

  async _handleSpecialCombo(candyA, candyB, effect) {
    const posA = { ...candyA.gridPos };
    const posB = { ...candyB.gridPos };
    const midPos = posA;
    Audio.playSpecialTriggerSound();
    const midW = this.filler.gridToWorld(midPos);
    const neighbors4 = (p) => {
      const out = [];
      for (const off of DIRS4) {
        const tp = { x: p.x + off.x, y: p.y + off.y };
        if (tp.x >= 0 && tp.x < this.gridWidth && tp.y >= 0 && tp.y < this.gridHeight) out.push(tp);
      }
      return out;
    };

    switch (effect) {
      case 'double_striped': {
        this.effects.spawnShockwave(midW);
        this._destroyCandyAt(posA, candyA.candyColor, EXPLODE_MODE_SPECIAL);
        this._destroyCandyAt(posB, candyB.candyColor, EXPLODE_MODE_SPECIAL);
        const dh = this._stripedSweepFx(midPos, 'h');
        const dv = this._stripedSweepFx(midPos, 'v');
        // 十字：橫排格照橫向距離、直欄格照縱向距離起爆
        const crossDelay = (p) => (p.y === midPos.y ? dh(p) : dv(p));
        this._explodeCells(getCrossTargets(midPos, this.gridWidth, this.gridHeight), EXPLODE_MODE_MATCH, crossDelay);
        break;
      }

      case 'double_wrapped':
        this.effects.spawnShockwave(midW);
        this.effects.spawnFirework(midW);
        this._destroyCandyAt(posA, candyA.candyColor, EXPLODE_MODE_SPECIAL);
        this._destroyCandyAt(posB, candyB.candyColor, EXPLODE_MODE_SPECIAL);
        this._explodeCells(getBigWrappedTargets(midPos, this.gridWidth, this.gridHeight), EXPLODE_MODE_SPECIAL);
        break;

      case 'wrapped_striped': {
        this.effects.spawnShockwave(midW);
        this.effects.spawnShockwave(midW);
        this._destroyCandyAt(posA, candyA.candyColor, EXPLODE_MODE_SPECIAL);
        this._destroyCandyAt(posB, candyB.candyColor, EXPLODE_MODE_SPECIAL);
        const wsTargets = [];
        for (let dy = -1; dy <= 1; dy++) {
          const rowY = midPos.y + dy;
          if (rowY < 0 || rowY >= this.gridHeight) continue;
          for (let x = 0; x < this.gridWidth; x++) wsTargets.push({ x, y: rowY });
        }
        for (let dx = -1; dx <= 1; dx++) {
          const colX = midPos.x + dx;
          if (colX < 0 || colX >= this.gridWidth) continue;
          for (let y = 0; y < this.gridHeight; y++) wsTargets.push({ x: colX, y });
        }
        this._explodeCells(wsTargets, EXPLODE_MODE_SPECIAL);
        break;
      }

      case 'double_spiral': {
        // 合成點 4 鄰消除 + 起飛 3 台紙飛機
        this.effects.spawnShockwave(midW);
        this._destroyCandyAt(posA, candyA.candyColor, EXPLODE_MODE_SPECIAL);
        this._destroyCandyAt(posB, candyB.candyColor, EXPLODE_MODE_SPECIAL);
        this._explodeCells(neighbors4(midPos), EXPLODE_MODE_MATCH);
        const picks = this._pickTopPlaneTargets(3, [midPos, posA, posB]);
        for (const tgt of picks) {
          const toW = this.filler.gridToWorld(tgt);
          this.effects.spawnPlaneFlight(midW, toW, candyA.candyColor, 1.0);
          this._deferredPlaneImpact(toW, 0.92);
        }
        await sleep(1.05);
        for (const tgt2 of picks) {
          this._detonateAt(tgt2, 'spiral');
          await sleep(0.1);
        }
        break;
      }

      case 'spiral_wrapped': {
        // 合成點 4 鄰 + 飛到新位置使用炸彈（5x5）
        this.effects.spawnShockwave(midW);
        this._destroyCandyAt(posA, candyA.candyColor, EXPLODE_MODE_SPECIAL);
        this._destroyCandyAt(posB, candyB.candyColor, EXPLODE_MODE_SPECIAL);
        this._explodeCells(neighbors4(midPos), EXPLODE_MODE_MATCH);
        await sleep(0.15);
        const picksW = this._pickTopPlaneTargetsForCombo(1, [midPos, posA, posB], 'wrapped');
        if (picksW.length > 0) {
          const tgt = picksW[0];
          const toW = this.filler.gridToWorld(tgt);
          this._deferredPlaneImpact(toW, 0.92);
          await this.effects.spawnPlaneFlight(midW, toW, candyA.candyColor, 1.0);
          this._detonateAt(tgt, 'wrapped');
        }
        break;
      }

      case 'spiral_striped': {
        // 合成點 4 鄰 + 飛到新位置使用火箭
        let stripedKind = 'striped_h';
        if (candyA.candyType === CandyType.STRIPED_V || candyB.candyType === CandyType.STRIPED_V) {
          stripedKind = 'striped_v';
        }
        this.effects.spawnShockwave(midW);
        this._destroyCandyAt(posA, candyA.candyColor, EXPLODE_MODE_SPECIAL);
        this._destroyCandyAt(posB, candyB.candyColor, EXPLODE_MODE_SPECIAL);
        this._explodeCells(neighbors4(midPos), EXPLODE_MODE_MATCH);
        await sleep(0.15);
        const picksS = this._pickTopPlaneTargetsForCombo(1, [midPos, posA, posB], stripedKind);
        if (picksS.length > 0) {
          const tgt = picksS[0];
          const toW = this.filler.gridToWorld(tgt);
          this._deferredPlaneImpact(toW, 0.92);
          await this.effects.spawnPlaneFlight(midW, toW, candyA.candyColor, 1.0);
          this._detonateAt(tgt, stripedKind);
        }
        break;
      }
    }

    await sleep(0.3);
    await this._cascadeLoop();
  }

  // ============ Match 處理 + cascade ============

  async _processMatches(matches, swapCells = []) {
    for (const matchData of matches) {
      this._damageTickId++;
      const cells = matchData.cells;
      const shape = matchData.shape || 'line';
      const firstCandy = this.filler.getCandyAt(cells[0]);
      const matchColor = firstCandy ? firstCandy.candyColor : 0;

      Audio.playMatchSound(this.cascadeLevel);
      GameManager.incrementCombo();

      let specialPos = matchData.specialPos || cells[0];
      if (swapCells.length === 2) {
        const inCells = (p) => cells.some((c) => c.x === p.x && c.y === p.y);
        if (inCells(swapCells[1])) specialPos = swapCells[1];
        else if (inCells(swapCells[0])) specialPos = swapCells[0];
      }

      // 延伸消除
      if (this.filler) {
        const extra = MatchFinder.collectExtendedElimination(
          this.filler.grid, this.gridWidth, this.gridHeight, cells, shape, specialPos,
          matchColor, this.blockedCells);
        for (const ep of extra) {
          if (!cells.some((c) => c.x === ep.x && c.y === ep.y)) cells.push(ep);
        }
      }

      let specialType = -1;
      if (shape === 'five') specialType = CandyType.COLOR_BOMB;
      else if (shape === 'special') specialType = CandyType.WRAPPED;
      else if (shape === 'four') {
        specialType = (matchData.direction || 'horizontal') === 'horizontal'
          ? CandyType.STRIPED_V : CandyType.STRIPED_H;
      } else if (shape === 'block_2x2') specialType = CandyType.SPIRAL;

      for (const cell of cells) {
        const candy = this.filler.getCandyAt(cell);
        if (candy) {
          if (candy.candyType !== CandyType.NORMAL && candy.candyType !== CandyType.COLOR_BOMB) {
            this._triggerSpecialCandy(candy);
          }
          this._triggerObstacleAdjacent(cell, matchColor);
          this.effects.spawnDestroyEffect(this.filler.gridToWorld(cell), candy.candyColor);
          GameManager.updateObjective('collect', candy.candyColor, 1);
          this.filler.removeCandyAt(cell);
          candy.animateDestroy();
        }
      }
      this._triggerManufacturersAdjacentToCells(cells);

      GameManager.addScore(cells.length, specialType >= 0);

      if (specialType >= 0) {
        Audio.playSpecialCreateSound();
        this.filler.createSpecialCandy(
          specialType !== CandyType.COLOR_BOMB ? matchColor : 0,
          specialPos, specialType);
      }
    }

    await sleep(0.25);
    await this._cascadeLoop();
  }

  async _cascadeLoop() {
    let firstRound = true;
    let safety = 0;
    while (safety < (this.gridWidth + this.gridHeight) * 2) {
      safety++;
      const obsTweens = this._applyMovableObstacleGravity();
      const gravityTweens = this.filler.applyGravity();
      const fillTweens = this.filler.fillEmptyCells();
      const allTweens = [...obsTweens, ...gravityTweens, ...fillTweens];
      if (allTweens.length === 0) break;
      await awaitTweensSafe(allTweens);
      if (firstRound) {
        await sleep(0.08);
        firstRound = false;
      }
    }

    const newMatches = MatchFinder.findAllMatches(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells);
    if (newMatches.length > 0) {
      if (GameManager.currentState !== GameState.LEVEL_COMPLETE && GameManager.checkWinCondition()) {
        this._markAllStampsVictory();
        GameManager.completeLevel();
      }
      this.cascadeLevel++;
      Audio.playCascadeSound(this.cascadeLevel);
      await this._processMatches(newMatches);
    }
    this._tryFlushDeferredQueue();
  }

  _triggerSpecialCandy(candy) {
    this._chainTrigger(candy.candyType, candy.gridPos, candy.candyColor);
  }

  // ============ 紙飛機目標優先級 ============

  _isPlaneObjectiveTile(tileId) {
    const myPrefix = tileId.split('-')[0];
    if (myPrefix === '') return false;
    for (const obj of GameManager.levelObjectives) {
      const objTid = String(obj.tile_id || '');
      if (objTid !== '' && objTid.split('-')[0] === myPrefix) return true;
    }
    return false;
  }

  _obsPlaneWeight(obs) {
    const tid = String(obs.tile_id || '');
    let baseW = 0;
    for (const prefix of Object.keys(PLANE_WEIGHT_BY_PREFIX)) {
      if (tid.startsWith(prefix)) { baseW = PLANE_WEIGHT_BY_PREFIX[prefix]; break; }
    }
    if (baseW <= 0) return 0;
    if (Number(obs.hp ?? 1) === 1) baseW += 1;
    if (this._isPlaneObjectiveTile(tid)) baseW += 100;
    return baseW;
  }

  _computePlaneTargetWeights() {
    const weights = new Map(); // key → weight
    const seenInst = new Set();
    for (const [k, obs] of this.obstacleMap) {
      const instId = String(obs.instance_id || '');
      if (instId !== '' && seenInst.has(instId)) continue;
      const w = this._obsPlaneWeight(obs);
      if (w <= 0) continue;
      weights.set(k, w);
      if (instId !== '') seenInst.add(instId);
    }
    return weights;
  }

  _powerupBlastCellsAt(center, detonateKind) {
    const uniq = new Map();
    uniq.set(K(center.x, center.y), center);
    let list = [];
    if (detonateKind === 'wrapped') list = getWrappedTargets(center, this.gridWidth, this.gridHeight);
    else if (detonateKind === 'striped_h') list = getStripedHTargets(center, this.gridWidth);
    else if (detonateKind === 'striped_v') list = getStripedVTargets(center, this.gridHeight);
    for (const tp of list) uniq.set(K(tp.x, tp.y), tp);
    return [...uniq.values()];
  }

  _sumObstacleWeightsInCells(cells) {
    let total = 0;
    const seenInst = new Set();
    for (const pos of cells) {
      const obs = this.obstacleMap.get(K(pos.x, pos.y));
      if (!obs) continue;
      const instId = String(obs.instance_id || '');
      if (instId !== '') {
        if (seenInst.has(instId)) continue;
        seenInst.add(instId);
      }
      total += this._obsPlaneWeight(obs);
    }
    return total;
  }

  _pickTopPlaneTargetsForCombo(n, exclude, detonateKind) {
    const inList = (list, p) => list.some((e) => e.x === p.x && e.y === p.y);
    const scored = [];
    for (let x = 0; x < this.gridWidth; x++) {
      for (let y = 0; y < this.gridHeight; y++) {
        const p = { x, y };
        if (inList(exclude, p)) continue;
        const score = this._sumObstacleWeightsInCells(this._powerupBlastCellsAt(p, detonateKind));
        if (score > 0) scored.push({ pos: p, score });
      }
    }
    scored.sort((a, b) => b.score - a.score);
    const picks = [];
    for (const entry of scored) {
      if (inList(picks, entry.pos)) continue;
      picks.push(entry.pos);
      if (picks.length >= n) break;
    }
    if (picks.length < n) {
      const fallback = this._pickTopPlaneTargets(n - picks.length, [...exclude, ...picks]);
      for (const fp of fallback) {
        if (!inList(picks, fp)) picks.push(fp);
        if (picks.length >= n) break;
      }
    }
    return picks;
  }

  _pickTopPlaneTargets(n, exclude = []) {
    const inList = (list, p) => list.some((e) => e.x === p.x && e.y === p.y);
    const weights = this._computePlaneTargetWeights();
    const sortedKeys = [...weights.keys()].sort((a, b) => weights.get(b) - weights.get(a));
    const picks = [];
    for (const k of sortedKeys) {
      const p = XY(k);
      if (inList(exclude, p) || inList(picks, p)) continue;
      picks.push(p);
      if (picks.length >= n) break;
    }
    if (picks.length < n) {
      const candidates = [];
      for (let x = 0; x < this.gridWidth; x++) {
        for (let y = 0; y < this.gridHeight; y++) {
          const p = { x, y };
          if (inList(exclude, p) || inList(picks, p)) continue;
          if (this.filler.getCandyAt(p) !== null) candidates.push(p);
        }
      }
      shuffleArray(candidates);
      for (const c of candidates) {
        picks.push(c);
        if (picks.length >= n) break;
      }
    }
    return picks;
  }

  _detonateAt(pos, kind) {
    this.effects.spawnShockwave(this.filler.gridToWorld(pos));
    if (kind === 'spiral') {
      this._explodeCells([pos], EXPLODE_MODE_PLANE);
      return;
    }
    const cells = [pos];
    let delayFn = null;
    if (kind === 'wrapped') cells.push(...getWrappedTargets(pos, this.gridWidth, this.gridHeight));
    else if (kind === 'striped_h') {
      cells.push(...getStripedHTargets(pos, this.gridWidth));
      delayFn = this._stripedSweepFx(pos, 'h');
    } else if (kind === 'striped_v') {
      cells.push(...getStripedVTargets(pos, this.gridHeight));
      delayFn = this._stripedSweepFx(pos, 'v');
    }
    this._explodeCells(cells, EXPLODE_MODE_SPECIAL, delayFn);
  }

  // ============ 障礙物傷害 ============

  _triggerManufacturersAdjacentToCells(cells) {
    const seen = new Set();
    for (const cell of cells) {
      for (const dir of DIRS4) {
        const adj = { x: cell.x + dir.x, y: cell.y + dir.y };
        const adjK = K(adj.x, adj.y);
        if (seen.has(adjK)) continue;
        const adjObs = this.obstacleMap.get(adjK);
        if (!adjObs || adjObs.type !== 'manufacturer') continue;
        const adjTid = String(adjObs.tile_id || '');
        if (!elimRule(adjTid, 'adj')) continue;
        seen.add(adjK);
        this._damageObstacle(adj);
      }
    }
  }

  _triggerObstacleAdjacent(pos, matchColorIdx = -1) {
    // 一般 match 語意 → 傷害模式回 MATCH
    this._obstacleDamageMode = EXPLODE_MODE_MATCH;
    const colorName = (matchColorIdx >= 0 && matchColorIdx < CANDY_IDX_TO_COLOR_NAME.length)
      ? CANDY_IDX_TO_COLOR_NAME[matchColorIdx] : '';
    for (const dir of DIRS4) {
      const adj = { x: pos.x + dir.x, y: pos.y + dir.y };
      const adjObs = this.obstacleMap.get(K(adj.x, adj.y));
      if (adjObs && elimRule(String(adjObs.tile_id || ''), 'adj')) {
        this._damageObstacle(adj, colorName);
      }
    }
    const obs = this.obstacleMap.get(K(pos.x, pos.y));
    if (obs && elimRule(String(obs.tile_id || ''), 'inplace')) {
      this._damageObstacle(pos, colorName);
    }
    const bobs = this.bottomObstacleMap.get(K(pos.x, pos.y));
    if (bobs && elimRule(String(bobs.tile_id || ''), 'inplace')) {
      this._damageBottomObstacle(pos);
    }
  }

  _damageBottomObstacle(pos) {
    const k = K(pos.x, pos.y);
    const obs = this.bottomObstacleMap.get(k);
    if (!obs) return;
    // 覆蓋物護盾：同 tick 打死覆蓋物也不穿透
    if (this._obstacleCoversBottomAt(pos)
        || this._upperBlockedBottomTick.get(k) === this._damageTickId) return;
    const tid = String(obs.tile_id || '');
    obs.hp -= 1;
    Audio.playObstacleBreakSound();
    if (obs.hp <= 0) {
      this.bottomObstacleMap.delete(k);
      GameManager.updateObjective('clear_' + (obs.type || 'jelly'), -1, 1, tid);
      this._flyGoalFeedback(pos, tid);
    }
    this.renderer.redrawBg();
  }

  _damageObstacle(pos, adjColorName = '') {
    const k = K(pos.x, pos.y);
    const obs = this.obstacleMap.get(k);
    if (!obs) return;
    const tid = String(obs.tile_id || '');

    // 水窪護盾標記
    this._upperBlockedBottomTick.set(k, this._damageTickId);

    if (tid.startsWith('SalmonCan')
        && this._obstacleDamageMode !== EXPLODE_MODE_SPECIAL
        && this._obstacleDamageMode !== EXPLODE_MODE_PLANE) return;

    if (tid.startsWith('BeverageChiller')) {
      if (!this._tryDamageBeverageChiller(obs, adjColorName)) return;
      this._applyObstacleHpAfterHit(obs, pos, tid);
      return;
    }

    if (this._shouldPerMatchDedup(tid, obs, this._obstacleDamageMode)) {
      if (obs._last_damage_tick === this._damageTickId) return;
      obs._last_damage_tick = this._damageTickId;
    }

    // 郵戳（manufacturer）：不扣 HP，每次 adj 消除 GOAL+1
    if (obs.type === 'manufacturer') {
      Audio.playObstacleBreakSound();
      if (obs.stamp_state !== 'victory') {
        obs.stamp_state = 'pressed';
        this.renderer.triggerStampFlash(pos);
        this.effects.spawnStampTrigger(this.filler.gridToWorld(pos));
        this._scheduleStampReturnIdle(pos, 0.55);
      }
      if (this._stampGoalLastTick.get(k) !== this._damageTickId) {
        this._stampGoalLastTick.set(k, this._damageTickId);
        GameManager.updateObjective('clear_' + obs.type, -1, 1, tid);
        this._flyGoalFeedback(pos, tid);
      }
      this.renderer.redrawObstacles();
      return;
    }

    this._applyObstacleHpAfterHit(obs, pos, tid);
  }

  _tryDamageBeverageChiller(obs, adjColorName) {
    const maxHp = Number(obs.max_hp ?? 5);
    const hp = Number(obs.hp ?? 0);
    const bottleColors = obs.bottle_colors || {};
    if (!obs.bottle_alive) obs.bottle_alive = {};
    const bottleAlive = obs.bottle_alive;
    for (const cell of obs.instance_cells || []) {
      const ck = K(cell.x, cell.y);
      if (!(ck in bottleAlive)) bottleAlive[ck] = true;
    }

    const isPowerup = this._obstacleDamageMode === EXPLODE_MODE_SPECIAL
      || this._obstacleDamageMode === EXPLODE_MODE_PLANE;

    if (isPowerup) {
      if (obs._last_damage_tick === this._damageTickId) return false;
      obs._last_damage_tick = this._damageTickId;
      if (hp >= maxHp) {
        // 關門 → 開門
      } else {
        let killed = false;
        for (const cell of obs.instance_cells || []) {
          const ck = K(cell.x, cell.y);
          if (bottleAlive[ck] !== false) {
            bottleAlive[ck] = false;
            killed = true;
            break;
          }
        }
        if (!killed) return false;
      }
    } else if (adjColorName === '') {
      return false;
    } else if (hp >= maxHp) {
      // 關門：任何相鄰消除都開門（只做 dedup）
      if (obs._last_damage_tick === this._damageTickId) return false;
      obs._last_damage_tick = this._damageTickId;
    } else {
      // 開門：找對色活瓶殺掉
      let target = null;
      for (const cell of obs.instance_cells || []) {
        const ck = K(cell.x, cell.y);
        if (bottleAlive[ck] !== false && String(bottleColors[ck] || '') === adjColorName) {
          target = ck;
          break;
        }
      }
      if (target === null) return false;
      if (obs._last_damage_tick === this._damageTickId) return false;
      obs._last_damage_tick = this._damageTickId;
      bottleAlive[target] = false;
    }

    obs.hp = hp - 1;
    return true;
  }

  _applyObstacleHpAfterHit(obs, pos, tid) {
    if (!tid.startsWith('BeverageChiller')) obs.hp -= 1;
    if (tid.startsWith('SalmonCan') && obs.hp > 0) obs.salmon_state = 'open';
    Audio.playObstacleBreakSound();

    if (isHitsModeObstacle(tid)) {
      GameManager.updateObjective('clear_' + obs.type, -1, 1, tid);
      this._flyGoalFeedback(pos, tid);
    }

    if (obs.hp <= 0) {
      let cellsToClear = obs.instance_cells || [pos];
      if (cellsToClear.length === 0) cellsToClear = [pos];
      if (!isHitsModeObstacle(tid)) {
        GameManager.updateObjective('clear_' + obs.type, -1, 1, tid);
        this._flyGoalFeedback(pos, tid);
      }
      for (const cell of cellsToClear) {
        const ck = K(cell.x, cell.y);
        this.obstacleMap.delete(ck);
        this.blockedCells.delete(ck);
        this.filler.movableObstacleCells.delete(ck);
      }
      if (tid.startsWith('Pool')) this._spawnPoolPuddles(cellsToClear);
    }
    this.renderer.redraw();
    this._syncCandyLayerVisibility();
  }

  _spawnPoolPuddles(poolCells) {
    const puddlePositions = poolCells.map((c) => ({ x: c.x, y: c.y }));
    const poolSet = new Set(puddlePositions.map((p) => K(p.x, p.y)));
    const neighbors = [];
    for (const p of [...puddlePositions]) {
      for (const off of DIRS4) {
        const np = { x: p.x + off.x, y: p.y + off.y };
        const nk = K(np.x, np.y);
        if (poolSet.has(nk)) continue;
        if (np.x < 0 || np.x >= this.gridWidth || np.y < 0 || np.y >= this.gridHeight) continue;
        poolSet.add(nk);
        neighbors.push(np);
      }
    }
    puddlePositions.push(...neighbors);
    for (const p of puddlePositions) {
      const pk = K(p.x, p.y);
      if (this.obstacleMap.has(pk)) continue;
      if (this.blockedCells.has(pk)) continue;
      this.bottomObstacleMap.set(pk, {
        type: 'jelly', hp: 1, max_hp: 1, tile_id: 'Puddle_lv1', layer: 'bottom',
      });
    }
  }

  _shouldPerMatchDedup(tileId, obs, damageMode) {
    if (tileId === 'Stamp') return true;
    if (tileId.startsWith('BeverageChiller')) return true;
    if (tileId.startsWith('WaterChiller')) {
      const hp = Number(obs.hp ?? 0);
      const maxHp = Number(obs.max_hp ?? 11);
      if (damageMode === EXPLODE_MODE_SPECIAL || damageMode === EXPLODE_MODE_PLANE) {
        if (hp < maxHp) return false;
      }
      return true;
    }
    return false;
  }

  _scheduleStampReturnIdle(pos, delay) {
    setTimeout(() => {
      if (this._destroyed) return;
      const obs = this.obstacleMap.get(K(pos.x, pos.y));
      if (obs && obs.stamp_state === 'pressed') {
        obs.stamp_state = 'idle';
        this.renderer.redrawObstacles();
      }
    }, delay * 1000);
  }

  _markAllStampsVictory() {
    let changed = false;
    for (const obs of this.obstacleMap.values()) {
      if (obs.type === 'manufacturer' && obs.stamp_state !== 'victory') {
        obs.stamp_state = 'victory';
        changed = true;
      }
    }
    if (changed) this.renderer.redrawObstacles();
  }

  _flyGoalFeedback(pos, tileId) {
    const family = tileFamily(tileId);
    if (this.onGoalFly) this.onGoalFly(this.filler.gridToWorld(pos), family, tileId);
  }

  // ============ 可移動障礙物重力 ============

  _applyMovableObstacleGravity() {
    const tweens = [];
    let moved = true;
    let safety = 0;
    while (moved && safety < this.gridHeight * this.gridWidth) {
      safety++;
      moved = false;
      for (let y = this.gridHeight - 2; y >= 0; y--) {
        for (let x = 0; x < this.gridWidth; x++) {
          const k = K(x, y);
          const obs = this.obstacleMap.get(k);
          if (!obs || !isMovableObstacle(String(obs.tile_id || ''))) continue;
          const below = { x, y: y + 1 };
          const belowK = K(below.x, below.y);
          if (this.blockedCells.has(belowK)) continue;
          if (this.filler.getCandyAt(below) !== null) continue;
          if (this.filler.voidCells.has(belowK)) continue;
          // 掉一格
          this.obstacleMap.delete(k);
          this.obstacleMap.set(belowK, obs);
          this.blockedCells.delete(k);
          this.blockedCells.add(belowK);
          this.filler.movableObstacleCells.delete(k);
          this.filler.movableObstacleCells.add(belowK);
          tweens.push(this.renderer.notifyObstacleMoved({ x, y }, below, fallDuration(1)));
          moved = true;
        }
      }
    }
    return tweens;
  }

  // ============ 回合結束 ============

  _postTurnCheck() {
    if (this._destroyed) return;
    this._syncCandyLayerVisibility();
    this.filler.resetTurnSpawn();
    GameManager.resetCombo();

    if (GameManager.currentState !== GameState.LEVEL_COMPLETE && GameManager.checkWinCondition()) {
      this._markAllStampsVictory();
      GameManager.completeLevel();
      this.isProcessing = false;
      return;
    }
    if (GameManager.currentState === GameState.PLAYING && GameManager.movesRemaining <= 0) {
      GameManager.failLevel();
      this.isProcessing = false;
      return;
    }

    // 死盤自動洗牌
    if (GameManager.currentState === GameState.PLAYING) {
      const hasMove = MatchFinder.findHintMove(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells).length >= 2
        || this._findMovableSwapHint().length >= 2;
      if (!hasMove) {
        this._shuffleBoard();
        return; // _shuffleBoard 自己解鎖
      }
    }

    this.isProcessing = false;
    this._resetHintTimer();
    if (this.onTurnCompleted) this.onTurnCompleted();
  }

  async _shuffleBoard() {
    this.isProcessing = true;
    const candies = [];
    const positions = [];
    for (let x = 0; x < this.gridWidth; x++) {
      for (let y = 0; y < this.gridHeight; y++) {
        const c = this.filler.getCandyAt({ x, y });
        if (c && !c.isBeingDestroyed && c.candyType === CandyType.NORMAL) {
          candies.push(c);
          positions.push({ x, y });
        }
      }
    }
    if (candies.length < 2) { this.isProcessing = false; return; }

    let ok = false;
    for (let attempt = 0; attempt < 30; attempt++) {
      shuffleArray(candies);
      for (let i = 0; i < positions.length; i++) this.filler.setCandyAt(positions[i], candies[i]);
      const noMatch = MatchFinder.findAllMatches(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells).length === 0;
      const hasMove = MatchFinder.findHintMove(this.filler.grid, this.gridWidth, this.gridHeight, this.blockedCells).length >= 2;
      if (noMatch && hasMove) { ok = true; break; }
    }
    const tweens = [];
    for (let i = 0; i < positions.length; i++) {
      tweens.push(candies[i].animateTo(this.filler.gridToWorld(positions[i]), 0.35));
    }
    await awaitTweensSafe(tweens);
    if (!ok) {
      // ponytail: 30 次仍死盤機率極低，直接接受可能出現的直接消除，讓 cascade 收拾
      await this._cascadeLoop();
    }
    this.isProcessing = false;
    this._resetHintTimer();
  }

  // ============ Spawner 生成障礙物 ============

  _onObstacleSpawned(pos, tileId) {
    const k = K(pos.x, pos.y);
    const isTNT = tileId.startsWith('TNT');
    const isSoda = tileId.startsWith('Soda');
    const obs = {
      type: isTNT ? 'bomb' : (isSoda ? 'soda' : 'crate'),
      hp: 1, max_hp: 1,
      tile_id: tileId,
      layer: 'middle',
    };
    if (isMovableObstacle(tileId)) this.filler.movableObstacleCells.add(k);
    this.obstacleMap.set(k, obs);
    this.blockedCells.add(k);
    this.renderer.notifyObstacleMoved({ x: pos.x, y: -1 - pos.y }, pos, fallDuration(pos.y + 1));
    this.renderer.redrawObstacles();
  }
}
