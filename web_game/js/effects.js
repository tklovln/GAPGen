// effects.js — 移植 effect_spawner.gd：程式化粒子點/擴張環/煙火/紙飛機/光球/郵戳特效
import { Tween, Ease } from './tween.js';
import { COLOR_MAP } from './tiles.js';
import { ArtTheme } from './theme.js';
import { randf } from './util.js';
import { GameManager } from './game_manager.js';
import { playExplosionSound } from './audio.js';

const TAU = Math.PI * 2;
const STAMP_INK_COLOR = 0xbf1f2e;

function lighten(color, amount) {
  const r = Math.min(255, ((color >> 16) & 0xff) + amount * 255);
  const g = Math.min(255, ((color >> 8) & 0xff) + amount * 255);
  const b = Math.min(255, (color & 0xff) + amount * 255);
  return (r << 16) | (g << 8) | b;
}

export class EffectSpawner {
  constructor(container, ticker) {
    this.container = container;   // PIXI.Container（effect layer）
    this._items = new Set();      // 自更新粒子/環
    this.shakeTarget = null;      // 震動目標（board root），由 board 設定
    this._shake = null;           // {base:{x,y}, intensity, remain, duration}
    ticker.add((tk) => this._update(tk.deltaMS / 1000));
  }

  // 螢幕震動：隨機偏移線性衰減；重複觸發取較強者
  shake(intensity = 7, duration = 0.28) {
    const t = this.shakeTarget;
    if (!t || t.destroyed) return;
    if (this._shake) {
      this._shake.intensity = Math.max(this._shake.intensity, intensity);
      this._shake.remain = Math.max(this._shake.remain, duration);
      this._shake.duration = Math.max(this._shake.duration, duration);
      return;
    }
    this._shake = { base: { x: t.position.x, y: t.position.y }, intensity, remain: duration, duration };
  }

  _updateShake(dt) {
    if (!this._shake) return;
    const s = this._shake;
    const t = this.shakeTarget;
    if (!t || t.destroyed) { this._shake = null; return; }
    s.remain -= dt;
    if (s.remain <= 0) {
      t.position.set(s.base.x, s.base.y);
      this._shake = null;
      return;
    }
    const amp = s.intensity * (s.remain / s.duration);
    t.position.set(s.base.x + randf(-amp, amp), s.base.y + randf(-amp, amp));
  }

  _update(dt) {
    this._updateShake(dt);
    for (const it of [...this._items]) {
      try {
        it.update(dt);
      } catch (_e) {
        this._items.delete(it);
        if (it.g && !it.g.destroyed) it.g.destroy();
      }
    }
  }

  _addDot(pos, color, velocity, lifetime, sz) {
    const g = new PIXI.Graphics();
    g.position.set(pos.x, pos.y);
    this.container.addChild(g);
    const dot = {
      g, color, velocity: { ...velocity }, lifetime, age: 0, sz, initialSz: sz,
      update: (dt) => {
        dot.age += dt;
        if (dot.age >= dot.lifetime) {
          this._items.delete(dot);
          g.destroy();
          return;
        }
        dot.velocity.y += 200 * dt;
        dot.velocity.x *= 0.98;
        dot.velocity.y *= 0.98;
        g.position.x += dot.velocity.x * dt;
        g.position.y += dot.velocity.y * dt;
        const t = dot.age / dot.lifetime;
        dot.sz = dot.initialSz + (0.5 - dot.initialSz) * t;
        g.clear();
        g.circle(0, 0, dot.sz).fill({ color: dot.color, alpha: 1 - t });
      },
    };
    this._items.add(dot);
  }

  _addRing(pos, color, expandSpeed = 200, maxRadius = 60) {
    const g = new PIXI.Graphics();
    g.position.set(pos.x, pos.y);
    this.container.addChild(g);
    const ring = {
      g, radius: 5, expandSpeed, maxRadius,
      update: (dt) => {
        ring.radius += ring.expandSpeed * dt;
        const alpha = 1 - ring.radius / ring.maxRadius;
        if (alpha <= 0) {
          this._items.delete(ring);
          g.destroy();
          return;
        }
        g.clear();
        g.circle(0, 0, ring.radius).stroke({ width: 3, color, alpha });
      },
    };
    this._items.add(ring);
  }

  spawnParticles(pos, color, count, spread) {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * TAU;
      const speed = randf(spread * 0.3, spread);
      this._addDot(pos, lighten(color, Math.random() * 0.3),
        { x: Math.cos(angle) * speed, y: Math.sin(angle) * speed },
        randf(0.3, 0.6), 4);
    }
  }

  spawnScoreText(pos) {
    const text = new PIXI.Text({
      text: '+' + 50 * Math.max(1, GameManager.comboCount),
      style: { fontSize: 18, fill: 0xffff80, fontWeight: 'bold', stroke: { color: 0x000000, width: 3 } },
    });
    text.position.set(pos.x - 20, pos.y - 10);
    text.zIndex = 100;
    this.container.addChild(text);
    new Tween()
      .tweenProps(text.position, { y: { to: pos.y - 60, ease: Ease.quadOut } }, 0.6)
      .tweenCallback(() => text.destroy());
    new Tween()
      .tweenInterval(0.3)
      .tweenProps(text, { alpha: { to: 0 } }, 0.3, Ease.linear);
  }

  spawnDestroyEffect(pos, candyColor) {
    const color = COLOR_MAP[candyColor] ?? 0xffffff;
    this.spawnParticles(pos, color, 12, 80);
    this.spawnScoreText(pos);
  }

  spawnShockwave(pos) {
    this._addRing(pos, 0xffe680);
    this.spawnParticles(pos, 0xffffff, 20, 120);
    playExplosionSound();
    this.shake(7, 0.28);
    GameManager._emit('explosion');   // 頭像等 UI 反應用
  }

  spawnFirework(pos) {
    for (let i = 0; i < 5; i++) {
      const offset = { x: pos.x + randf(-100, 100), y: pos.y + randf(-100, 100) };
      const hue = Math.random() * 360;
      const color = hslToHex(hue, 0.9, 0.6);
      this.spawnParticles(offset, color, 16, 100);
    }
  }

  // 紙飛機飛行：弧形拋物線 + 尾跡；回傳 Promise（await 落地）
  spawnPlaneFlight(fromPos, toPos, _candyColor = -1, flightTime = 1.0) {
    const tex = ArtTheme.get('TrPr');
    const plane = tex ? new PIXI.Sprite(tex) : new PIXI.Graphics().circle(0, 0, 20).fill(0xffffff);
    if (tex) {
      plane.anchor.set(0.5);
      const scale = 64 / Math.max(tex.width, tex.height);
      plane.scale.set(scale);
    }
    plane.position.set(fromPos.x, fromPos.y);
    plane.zIndex = 200;
    const dir = { x: toPos.x - fromPos.x, y: toPos.y - fromPos.y };
    plane.rotation = Math.atan2(dir.y, dir.x) + Math.PI / 2;
    this.container.addChild(plane);

    // 尾跡點（每 0.02s）
    const trailTimer = setInterval(() => {
      if (plane.destroyed) { clearInterval(trailTimer); return; }
      this._addDot({ x: plane.position.x, y: plane.position.y }, 0xffeb8c, { x: 0, y: 0 }, 0.5, 6);
    }, 20);

    const mid = { x: (fromPos.x + toPos.x) * 0.5, y: (fromPos.y + toPos.y) * 0.5 - 60 };
    const tw = new Tween()
      .tweenProps(plane.position, { x: { to: mid.x }, y: { to: mid.y } }, flightTime * 0.5, Ease.sineOut)
      .tweenProps(plane.position, { x: { to: toPos.x }, y: { to: toPos.y } }, flightTime * 0.5, Ease.sineIn)
      .tweenCallback(() => { clearInterval(trailTimer); plane.destroy(); });
    return tw.finished;
  }

  spawnPlaneImpact(pos) {
    this._addRing(pos, 0xffb333, 360, 55);
    this._addRing(pos, 0xffffff, 520, 70);
    this.spawnParticles(pos, 0xffd94d, 22, 220);
    this.spawnParticles(pos, 0xff8033, 12, 160);
    this._addDot(pos, 0xffffff, { x: 0, y: 0 }, 0.18, 32);
    playExplosionSound();
    this.shake(9, 0.32);
  }

  // 光球 orb：LtBl sprite 浮起 + 旋轉 + 淡出
  spawnColorBombOrb(pos, duration) {
    const tex = ArtTheme.get('LtBl');
    if (!tex) return;
    const orb = new PIXI.Sprite(tex);
    orb.anchor.set(0.5);
    orb.position.set(pos.x, pos.y);
    orb.zIndex = 199;
    orb.scale.set(61 / Math.max(tex.width, tex.height));
    this.container.addChild(orb);
    new Tween()
      .tweenProps(orb.position, { y: { to: pos.y - 30 } }, duration, Ease.sineOut)
      .tweenProps(orb, { alpha: { to: 0 } }, 0.2, Ease.linear)
      .tweenCallback(() => orb.destroy());
    new Tween().tweenProps(orb, { rotation: { to: TAU * 2.5 } }, duration, Ease.linear);
  }

  spawnStampTrigger(pos) {
    this._addRing(pos, STAMP_INK_COLOR, 120, 32);
    this.spawnParticles(pos, STAMP_INK_COLOR, 6, 55);
  }

  // 整排/整欄消除：兩枚火箭從觸發點往兩側飛出 + 尾跡
  // axis 'h'|'v'；span = {neg, pos} 兩側到盤面邊緣的像素距離；secPerCell 與爆炸 stagger 對齊
  spawnRocketSweep(pos, axis, span, cellSize, secPerCell = 0.03) {
    const tex = ArtTheme.get(axis === 'h' ? 'Soda0d' : 'Soda90');
    const speed = cellSize / secPerCell;
    for (const s of [-1, 1]) {
      const dist = s < 0 ? span.neg : span.pos;
      if (dist <= cellSize * 0.25) continue;
      let rocket;
      if (tex) {
        rocket = new PIXI.Sprite(tex);
        rocket.anchor.set(0.5);
        const scale = (cellSize * 0.9) / Math.max(tex.width, tex.height);
        rocket.scale.set(scale);
        // 素材朝正向（Soda0d→右、Soda90→下），反向翻轉
        if (axis === 'h') rocket.scale.x *= s;
        else rocket.scale.y *= s;
      } else {
        rocket = new PIXI.Graphics().circle(0, 0, cellSize * 0.28).fill(0xffffff);
      }
      rocket.position.set(pos.x, pos.y);
      rocket.zIndex = 195;
      this.container.addChild(rocket);

      const trailTimer = setInterval(() => {
        if (rocket.destroyed) { clearInterval(trailTimer); return; }
        this._addDot({ x: rocket.position.x, y: rocket.position.y }, 0xffe680, { x: 0, y: 0 }, 0.3, 5);
      }, 16);

      const to = axis === 'h'
        ? { x: { to: pos.x + s * dist } }
        : { y: { to: pos.y + s * dist } };
      new Tween()
        .tweenProps(rocket.position, to, dist / speed, Ease.linear)
        .tweenCallback(() => {
          clearInterval(trailTimer);
          this.spawnParticles({ x: rocket.position.x, y: rocket.position.y }, 0xffd94d, 8, 90);
          rocket.destroy();
        });
    }
  }

  spawnTargetHighlight(pos, candyColor) {
    const color = COLOR_MAP[candyColor] ?? 0xffffff;
    this._addDot(pos, 0xffffff, { x: 0, y: 0 }, 0.25, 14);
    this._addRing(pos, color, 220, 45);
  }

  // 目標飛行回饋（play_objective_fly 的畫面內版本）：sprite 弧線飛向 HUD 目標位置
  spawnGoalFly(fromPos, toPos, texName) {
    const tex = ArtTheme.get(texName);
    if (!tex) return;
    const sprite = new PIXI.Sprite(tex);
    sprite.anchor.set(0.5);
    sprite.position.set(fromPos.x, fromPos.y);
    sprite.zIndex = 210;
    const startScale = 44 / Math.max(tex.width, tex.height);
    sprite.scale.set(startScale);
    this.container.addChild(sprite);
    const duration = 0.75;
    const mid = {
      x: fromPos.x + (toPos.x - fromPos.x) * 0.45,
      y: fromPos.y + (toPos.y - fromPos.y) * 0.45 - 42,
    };
    new Tween()
      .tweenProps(sprite.position, { x: { to: mid.x }, y: { to: mid.y } }, duration * 0.45, Ease.sineOut)
      .tweenProps(sprite.position, { x: { to: toPos.x }, y: { to: toPos.y } }, duration * 0.55, Ease.sineIn)
      .tweenCallback(() => sprite.destroy());
    new Tween()
      .tweenProps(sprite.scale, { x: { to: startScale * 0.7 }, y: { to: startScale * 0.7 } }, duration, Ease.linear);
    new Tween()
      .tweenInterval(duration - 0.15)
      .tweenProps(sprite, { alpha: { to: 0 } }, 0.15, Ease.linear);
  }
}

function hslToHex(h, s, l) {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return (Math.round((r + m) * 255) << 16) | (Math.round((g + m) * 255) << 8) | Math.round((b + m) * 255);
}
