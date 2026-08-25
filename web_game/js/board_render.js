// board_render.js — 移植 board_bg.gd：盤面背景 + 障礙物繪製（含郵戳/罐頭/雙櫃 composite）
import { K, XY } from './util.js';
import { Tween } from './tween.js';
import { resolveSpriteKey, BEVERAGE_BOTTLE_TEXTURE_KEY } from './tiles.js';
import { ArtTheme } from './theme.js';

const STAMP_FLASH_DURATION = 0.28;

export class BoardRenderer {
  constructor(board, bgLayer, obstacleLayer, mudLayer) {
    this.board = board;
    this.bgLayer = bgLayer;             // 底色 + 水窪
    this.obstacleLayer = obstacleLayer; // 中/上層障礙物
    this.mudLayer = mudLayer;           // 泥巴（蓋在糖上）
    this._stampFlashUntil = new Map();  // key → 結束時間(秒)
    this._obsFallOffset = new Map();    // key → {x,y} 掉落動畫偏移
    ArtTheme.onThemeReady(() => this.redraw());
  }

  triggerStampFlash(gridPos) {
    this._stampFlashUntil.set(K(gridPos.x, gridPos.y), performance.now() / 1000 + STAMP_FLASH_DURATION);
    this.redrawObstacles();
    setTimeout(() => this.redrawObstacles(), STAMP_FLASH_DURATION * 1000 + 30);
  }

  // 障礙物位移動畫（可移動障礙物掉落 / spawner 掉入）— 對齊 notify_obstacle_moved
  notifyObstacleMoved(fromPos, toPos, duration = 0.15) {
    const cs = this.board.cellSize;
    const pixelDiff = { x: (fromPos.x - toPos.x) * cs, y: (fromPos.y - toPos.y) * cs };
    const key = K(toPos.x, toPos.y);
    this._obsFallOffset.set(key, { ...pixelDiff });
    this.redrawObstacles();
    return new Tween()
      .tweenMethod((t) => {
        this._obsFallOffset.set(key, { x: pixelDiff.x * (1 - t), y: pixelDiff.y * (1 - t) });
        this.redrawObstacles();
      }, 0, 1, duration)
      .tweenCallback(() => {
        this._obsFallOffset.delete(key);
        this.redrawObstacles();
      });
  }

  _tex(name) { return ArtTheme.get(name); }

  _drawTexRect(container, name, x, y, w, h, alpha = 1) {
    const tex = this._tex(name);
    if (!tex) return false;
    const sp = new PIXI.Sprite(tex);
    sp.position.set(x, y);
    sp.width = w;
    sp.height = h;
    sp.alpha = alpha;
    container.addChild(sp);
    return true;
  }

  redraw() {
    this.redrawBg();
    this.redrawObstacles();
  }

  redrawBg() {
    const b = this.board;
    const layer = this.bgLayer;
    layer.removeChildren().forEach((c) => c.destroy({ children: true }));
    if (!b.filler) return;
    const offset = b.boardOffset;
    const w = b.gridWidth, h = b.gridHeight, cs = b.cellSize;

    // 邊框：亮金 #f7c04a，仿 #avatarFrame 的立體感（下方投影 + 暗金底層錯位當斜面）
    const g = new PIXI.Graphics();
    g.roundRect(offset.x - 3, offset.y + 2, w * cs + 6, h * cs + 6, 14)
      .stroke({ width: 9, color: 0x000000, alpha: 0.22 });          // 投影
    g.roundRect(offset.x, offset.y, w * cs, h * cs, 14).fill(0xd6e6f7); // 淺藍底
    g.roundRect(offset.x - 3, offset.y - 1, w * cs + 6, h * cs + 6, 14)
      .stroke({ width: 6, color: 0xb8860b });                       // 暗金（下緣斜面）
    g.roundRect(offset.x - 3, offset.y - 3, w * cs + 6, h * cs + 6, 14)
      .stroke({ width: 6, color: 0xf7c04a });                       // 主金框

    // 棋盤格：接近底色的淺藍圓角方格（void 除外），深淺微交錯
    for (let x = 0; x < w; x++) {
      for (let y = 0; y < h; y++) {
        const k = K(x, y);
        if (b.blockedCells.has(k) && !b.obstacleMap.has(k) && !b.bottomObstacleMap.has(k)) continue;
        const shade = (x + y) % 2 === 0 ? 0xc5daf1 : 0xcde0f4;
        g.roundRect(offset.x + x * cs + 2, offset.y + y * cs + 2, cs - 4, cs - 4, 10).fill(shade);
      }
    }
    layer.addChild(g);

    // 下層水窪
    for (const [k, obs] of b.bottomObstacleMap) {
      const p = XY(k);
      const key = resolveSpriteKey(String(obs.tile_id || ''), obs.hp ?? 1);
      this._drawTexRect(layer, key, offset.x + p.x * cs + 2, offset.y + p.y * cs + 2, cs - 4, cs - 4);
    }
  }

  redrawObstacles() {
    const b = this.board;
    const layer = this.obstacleLayer;
    const mudLayer = this.mudLayer;
    layer.removeChildren().forEach((c) => c.destroy({ children: true }));
    mudLayer.removeChildren().forEach((c) => c.destroy({ children: true }));
    if (!b.filler) return;
    const offset = b.boardOffset;
    const cs = b.cellSize;
    const now = performance.now() / 1000;

    const drawnInstances = new Set();
    for (const [k, obs] of b.obstacleMap) {
      const pos = XY(k);
      const tid = String(obs.tile_id || '');
      const instId = String(obs.instance_id || '');

      // 泥巴另外畫（蓋在糖上）
      if (tid.startsWith('Mud')) {
        this._drawTexRect(mudLayer, 'Mud', offset.x + pos.x * cs + 2, offset.y + pos.y * cs + 2, cs - 4, cs - 4);
        continue;
      }
      if (obs.layer === 'bottom' || tid.startsWith('Puddle')) continue;

      let anchorPos = pos;
      let sizeCells = { x: 1, y: 1 };
      if (instId !== '') {
        if (drawnInstances.has(instId)) continue;
        drawnInstances.add(instId);
        const cells = obs.instance_cells || [pos];
        let minX = pos.x, minY = pos.y, maxX = pos.x, maxY = pos.y;
        for (const c of cells) {
          minX = Math.min(minX, c.x); minY = Math.min(minY, c.y);
          maxX = Math.max(maxX, c.x); maxY = Math.max(maxY, c.y);
        }
        anchorPos = { x: minX, y: minY };
        sizeCells = { x: maxX - minX + 1, y: maxY - minY + 1 };
      }

      let fallOff = { x: 0, y: 0 };
      if (instId === '' && this._obsFallOffset.has(k)) fallOff = this._obsFallOffset.get(k);
      const rx = offset.x + anchorPos.x * cs + 2 + fallOff.x;
      const ry = offset.y + anchorPos.y * cs + 2 + fallOff.y;
      const rw = sizeCells.x * cs - 4;
      const rh = sizeCells.y * cs - 4;
      const hp = obs.hp ?? 1;

      let spriteDrawn = false;
      if (tid !== '') {
        if (tid.startsWith('BeverageChiller') && obs.bottle_colors && Object.keys(obs.bottle_colors).length > 0) {
          this._drawBeverageChillerComposite(layer, rx, ry, rw, rh, cs, offset, obs);
          spriteDrawn = true;
        } else if (tid === 'Stamp' || obs.type === 'manufacturer') {
          this._drawPostmarkComposite(layer, rx, ry, rw, rh, obs, k, now);
          spriteDrawn = true;
        } else if (tid.startsWith('SalmonCan') && this._tex('SalmonCan_body')) {
          this._drawTexRect(layer, 'SalmonCan_body', rx, ry, rw, rh);
          const state = String(obs.salmon_state || 'sealed');
          this._drawTexRect(layer, state === 'sealed' ? 'SalmonCan_top1' : 'SalmonCan_top2', rx, ry, rw, rh);
          spriteDrawn = true;
        } else {
          const spriteKey = resolveSpriteKey(tid, hp);
          if (this._drawTexRect(layer, spriteKey, rx, ry, rw, rh)) spriteDrawn = true;
          if (tid.startsWith('WaterChiller') && hp >= 11) {
            this._drawTexRect(layer, 'WaterChiller_door', rx, ry, rw, rh, 0.6);
          }
        }
      }

      if (!spriteDrawn) {
        // fallback 程序畫法
        const g = new PIXI.Graphics();
        if (obs.type === 'wire') {
          g.rect(rx + 1, ry + 1, rw - 2, rh - 2).stroke({ width: 2.5, color: 0x808080, alpha: 0.4 });
        } else {
          g.rect(rx, ry, rw, rh).fill({ color: 0xe64d80, alpha: Math.min(0.2 + hp * 0.15, 0.9) });
        }
        layer.addChild(g);
      }
    }

    // 可移動障礙物選取框（selected_movable_obs）
    if (b.selectedMovableObs) {
      const p = b.selectedMovableObs;
      const g = new PIXI.Graphics();
      g.rect(offset.x + p.x * cs + 2, offset.y + p.y * cs + 2, cs - 4, cs - 4)
        .stroke({ width: 3, color: 0xffffff, alpha: 0.85 });
      layer.addChild(g);
    }
  }

  _drawPostmarkComposite(layer, rx, ry, rw, rh, obs, key, now) {
    let state = String(obs.stamp_state || 'idle');
    const until = this._stampFlashUntil.get(key);
    if (until !== undefined) {
      if (until > now && state === 'idle') state = 'pressed';
      else if (until <= now) this._stampFlashUntil.delete(key);
    }
    if (state === 'victory') {
      this._drawTexRect(layer, 'Postmark_card', rx, ry, rw, rh);
      const tex = this._tex('Postmark_02');
      if (tex) {
        const sp = new PIXI.Sprite(tex);
        sp.anchor.set(0.5);
        sp.width = rw * 0.55;
        sp.height = rh * 0.55;
        sp.rotation = -Math.PI * 0.5;
        sp.position.set(rx + rw * 0.3, ry + rh * 0.62);
        layer.addChild(sp);
      }
    } else if (state === 'pressed') {
      this._drawTexRect(layer, 'Postmark_bundle', rx, ry, rw, rh);
      this._drawTexRect(layer, 'Postmark_02', rx, ry, rw, rh);
      if (until !== undefined && until > now) {
        const ft = 1 - (until - now) / STAMP_FLASH_DURATION;
        const pulse = Math.sin(ft * Math.PI) * 0.25;
        const g = new PIXI.Graphics();
        g.rect(rx, ry, rw, rh).fill({ color: 0xf23326, alpha: pulse });
        layer.addChild(g);
      }
    } else {
      this._drawTexRect(layer, 'Postmark_bundle', rx, ry, rw, rh);
      this._drawTexRect(layer, 'Postmark_01', rx, ry, rw, rh);
    }
  }

  _drawBeverageChillerComposite(layer, rx, ry, rw, rh, cs, offset, obs) {
    this._drawTexRect(layer, 'BeverageChiller_body', rx, ry, rw, rh);
    const bottleColors = obs.bottle_colors || {};
    const bottleAlive = obs.bottle_alive || {};
    const cells = [...(obs.instance_cells || [])].sort((a, b) => (a.y - b.y) || (a.x - b.x));
    for (const cell of cells) {
      const ck = K(cell.x, cell.y);
      if (bottleAlive[ck] === false) continue;
      const colorId = String(bottleColors[ck] || '');
      const key = BEVERAGE_BOTTLE_TEXTURE_KEY[colorId];
      if (!key) continue;
      const inset = cs * 0.10;
      this._drawTexRect(layer, key,
        offset.x + cell.x * cs + inset, offset.y + cell.y * cs + inset,
        cs - inset * 2, cs - inset * 2);
    }
    const hp = obs.hp ?? 0;
    const maxHp = obs.max_hp ?? 5;
    if (hp >= maxHp) this._drawTexRect(layer, 'BeverageChiller_door', rx, ry, rw, rh, 0.92);
  }
}
