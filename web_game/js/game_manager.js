// game_manager.js — 移植 game_manager.gd（分數/步數/目標/勝負狀態機）
import { tileFamily } from './tiles.js';

export const GameState = {
  MENU: 0, PLAYING: 2, PAUSED: 3, LEVEL_COMPLETE: 4, LEVEL_FAILED: 5,
};

const POINTS_BASE = 50;
const COMBO_MULTIPLIER = 1.5;

class GameManagerClass {
  constructor() {
    this.currentState = GameState.MENU;
    this.currentLevelId = 0;
    this.currentScore = 0;
    this.movesRemaining = 0;
    this.maxMoves = 0;
    this.comboCount = 0;
    this.levelObjectives = [];
    this.starThresholds = [];
    this._listeners = {};
  }

  on(event, fn) {
    (this._listeners[event] ??= []).push(fn);
  }
  _emit(event, ...args) {
    for (const fn of this._listeners[event] || []) fn(...args);
  }
  clearListeners() { this._listeners = {}; }

  startLevel(levelData) {
    this.currentLevelId = levelData.levelId;
    this.currentScore = 0;
    this.movesRemaining = levelData.maxMoves;
    this.maxMoves = levelData.maxMoves;
    this.comboCount = 0;
    this.starThresholds = [...levelData.starThresholds];
    this.levelObjectives = levelData.objectives.map((o) => ({ ...o }));
    this.currentState = GameState.PLAYING;
    this._emit('score_changed', this.currentScore);
    this._emit('moves_changed', this.movesRemaining);
    this._emit('level_started', this.currentLevelId);
  }

  useMove() {
    if (this.currentState !== GameState.PLAYING) return;
    this.movesRemaining -= 1;
    this.comboCount = 0;
    this._emit('moves_changed', this.movesRemaining);
  }

  addScore(matchedCount, isSpecial = false) {
    let base = POINTS_BASE * matchedCount;
    if (isSpecial) base *= 2;
    const points = Math.floor(base * Math.pow(COMBO_MULTIPLIER, this.comboCount));
    this.currentScore += points;
    this._emit('score_changed', this.currentScore);
  }

  incrementCombo() { this.comboCount += 1; }
  resetCombo() { this.comboCount = 0; }

  updateObjective(objType, color = -1, amount = 1, tileId = '') {
    for (const obj of this.levelObjectives) {
      if (obj.type !== objType) continue;
      if (obj.color !== undefined && color >= 0 && obj.color !== color) continue;
      if (tileId !== '' && obj.tile_id) {
        if (tileFamily(String(obj.tile_id)) !== tileFamily(tileId)) continue;
      }
      obj.current = (obj.current || 0) + amount;
      this._emit('objective_updated', obj);
    }
  }

  checkWinCondition() {
    for (const obj of this.levelObjectives) {
      if (obj.type === 'score') {
        if (this.currentScore < obj.target) return false;
      } else if ((obj.current || 0) < obj.target) return false;
    }
    return true;
  }

  checkLoseCondition() { return this.movesRemaining <= 0; }

  calculateStars() {
    let stars = 0;
    for (const th of this.starThresholds) if (this.currentScore >= th) stars++;
    return stars;
  }

  completeLevel() {
    this.currentState = GameState.LEVEL_COMPLETE;
    this._emit('level_completed', this.currentLevelId, this.currentScore, this.calculateStars());
  }

  failLevel() {
    this.currentState = GameState.LEVEL_FAILED;
    this._emit('level_failed', this.currentLevelId);
  }
}

export const GameManager = new GameManagerClass();
