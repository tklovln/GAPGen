// candy.js — 移植 candy.gd：糖果節點（Pixi Container + Sprite）與各種 Tween 動畫
import { Tween, Ease } from './tween.js';
import { CandyType, ELEMENT_NAMES, SPECIAL_SPRITE, COLOR_MAP } from './tiles.js';
import { ArtTheme } from './theme.js';

export class Candy {
  constructor(container) {
    this.candyColor = 0;
    this.candyType = CandyType.NORMAL;
    this.gridPos = { x: 0, y: 0 };
    this.isBeingDestroyed = false;
    this.isMoving = false;
    this.cellSize = 70;

    this._selected = false;
    this._scaleTween = null;

    this.node = new PIXI.Container();
    this.sprite = new PIXI.Sprite();
    this.sprite.anchor.set(0.5);
    this.node.addChild(this.sprite);
    this.selectRing = new PIXI.Graphics();
    this.selectRing.visible = false;
    this.node.addChild(this.selectRing);
    container.addChild(this.node);
  }

  get position() { return this.node.position; }

  init(colorIdx, gridPosition, type = CandyType.NORMAL) {
    this.candyColor = colorIdx;
    this.gridPos = { ...gridPosition };
    this.candyType = type;
    this.redraw();
  }

  setCandyType(type) { this.candyType = type; this.redraw(); }
  setCandyColor(colorIdx) { this.candyColor = colorIdx; this.redraw(); }

  redraw() {
    const sz = this.cellSize;
    let tex = null;
    let sizeFactor = 0.92;
    if (this.candyType !== CandyType.NORMAL) {
      tex = ArtTheme.get(SPECIAL_SPRITE[this.candyType]);
      sizeFactor = this.candyType === CandyType.COLOR_BOMB ? 0.92 : 0.95;
    } else {
      tex = ArtTheme.get(ELEMENT_NAMES[this.candyColor]);
    }
    if (tex) {
      this.sprite.texture = tex;
      const target = sz * sizeFactor;
      this.sprite.width = target;
      this.sprite.height = target;
      this.sprite.visible = true;
      if (this._fallbackG) this._fallbackG.visible = false;
    } else {
      // 罕見 fallback（6 色關卡）：向量圓形
      this.sprite.visible = false;
      if (!this._fallbackG) {
        this._fallbackG = new PIXI.Graphics();
        this.node.addChildAt(this._fallbackG, 0);
      }
      const g = this._fallbackG;
      g.visible = true;
      g.clear();
      const base = COLOR_MAP[this.candyColor] ?? 0xffffff;
      g.circle(1, 2, sz * 0.45).fill({ color: 0x000000, alpha: 0.25 });
      g.circle(0, 0, sz * 0.45).fill(base);
      g.circle(-sz * 0.11, -sz * 0.11, sz * 0.16).fill({ color: 0xffffff, alpha: 0.45 });
    }
    // 選取白圈
    this.selectRing.clear();
    this.selectRing.circle(0, 0, sz * 0.48).stroke({ width: 2, color: 0xffffff, alpha: 0.6 });
    this.selectRing.visible = this._selected;
  }

  _killScaleTween() {
    if (this._scaleTween) { this._scaleTween.kill(); this._scaleTween = null; }
  }

  setSelected(selected) {
    this._selected = selected;
    this._killScaleTween();
    if (selected) {
      this._scaleTween = new Tween()
        .tweenProps(this.node.scale, { x: { to: 1.15 }, y: { to: 1.15 } }, 0.3, Ease.sineInOut)
        .tweenProps(this.node.scale, { x: { to: 1.0 }, y: { to: 1.0 } }, 0.3, Ease.sineInOut)
        .setLoops(Infinity);
    } else {
      this._scaleTween = new Tween()
        .tweenProps(this.node.scale, { x: { to: 1 }, y: { to: 1 } }, 0.15, Ease.sineInOut);
    }
    this.selectRing.visible = selected;
  }

  // swap / 一般位移：SINE ease in-out
  animateTo(targetPos, duration = 0.2) {
    this.isMoving = true;
    return new Tween()
      .tweenProps(this.node.position, { x: { to: targetPos.x }, y: { to: targetPos.y } }, duration, Ease.sineInOut)
      .tweenCallback(() => { this.isMoving = false; });
  }

  // 掉落：等速線性
  animateFall(targetPos, duration = 0.2) {
    this.isMoving = true;
    return new Tween()
      .tweenProps(this.node.position, { x: { to: targetPos.x }, y: { to: targetPos.y } }, duration, Ease.linear)
      .tweenCallback(() => { this.isMoving = false; });
  }

  // 消除：放大 1.3(0.1s) + 淡出(0.2s, delay 0.05) → destroy；delay = 延後起爆（整排掃射用）
  animateDestroy(delay = 0) {
    this.isBeingDestroyed = true;
    this._killScaleTween();
    const t1 = new Tween();
    if (delay > 0) t1.tweenInterval(delay);
    t1.tweenProps(this.node.scale, { x: { to: 1.3 }, y: { to: 1.3 } }, 0.1, Ease.quadOut);
    const t2 = new Tween();
    if (delay > 0) t2.tweenInterval(delay);
    return t2
      .tweenProps(this.node, { alpha: { to: 0, delay: 0.05, duration: 0.2 } }, 0.25, Ease.linear)
      .tweenCallback(() => { if (!this.node.destroyed) this.node.destroy({ children: true }); });
  }

  // 生成：scale 0→1 TRANS_BACK 彈出
  animateSpawn(delay = 0) {
    this.node.scale.set(0);
    this.node.alpha = 0;
    const tw = new Tween();
    if (delay > 0) tw.tweenInterval(delay);
    tw.tweenProps(this.node.scale, { x: { to: 1 }, y: { to: 1 } }, 0.25, Ease.backOut);
    new Tween().tweenInterval(delay).tweenProps(this.node, { alpha: { to: 1 } }, 0.15, Ease.linear);
    return tw;
  }

  // 道具觸發前奏：自轉由慢到快（轉速 0.8 → 7 圈/秒，加速感明顯）+ 體積微放大。
  // frames 有 10 幀 turntable 圖就逐幀換貼圖，否則直接旋轉貼圖 fallback。
  playSpinUp(frames = null, duration = 1.0) {
    this._killScaleTween();
    const spr = this.sprite;
    const w0 = 0.8, w1 = 7;
    const baseW = spr.width, baseH = spr.height;
    new Tween().tweenProps(this.node.scale, { x: { to: 1.18 }, y: { to: 1.18 } }, duration, Ease.quadOut);
    this._scaleTween = new Tween().tweenMethod((p) => {
      if (this.node.destroyed) return;
      // 轉速線性升 → 累積圈數 = ∫w dt = D*(w0*p + (w1-w0)*p²/2)
      const turns = duration * (w0 * p + (w1 - w0) * p * p / 2);
      if (frames && frames.length) {
        const idx = Math.floor(turns * frames.length) % frames.length;
        if (spr.texture !== frames[idx]) {
          spr.texture = frames[idx];
          spr.width = baseW;
          spr.height = baseH;
        }
      } else {
        spr.rotation = turns * Math.PI * 2;
      }
    }, 0, 1, duration);
    return this._scaleTween;
  }

  playHint() {
    this._killScaleTween();
    this._scaleTween = new Tween()
      .tweenProps(this.node.scale, { x: { to: 1.2 }, y: { to: 1.2 } }, 0.25, Ease.sineInOut)
      .tweenProps(this.node.scale, { x: { to: 1 }, y: { to: 1 } }, 0.25, Ease.sineInOut)
      .setLoops(3);
    this._scaleTween.finished.then(() => {
      if (!this.node.destroyed) this.node.scale.set(1);
    });
  }

  stopHint() {
    this._killScaleTween();
    if (!this.node.destroyed) this.node.scale.set(1);
  }
}
