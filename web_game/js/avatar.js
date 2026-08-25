// avatar.js — DEM02 動畫頭像。
// 做法：底圖照畫，表情用 canvas 在「來源圖座標」上局部重繪（眨眼＝黃底+閉眼線、
// 看右下＝黃底重畫瞳孔偏移、微笑＝白底蓋掉 ^ 嘴重畫笑弧）。
// 控制邏輯是一個 2 節點的 behavior tree：Celebrate（優先）→ Idle（偶爾眨眼）。

// ---- 來源圖（1772×1772）上量測到的幾何常數 ----
const SRC = 1772;
const EYES = [
  { cx: 605, cy: 1006, rx: 233, ry: 146 },  // 左眼（畫面左）
  { cx: 1068, cy: 957, rx: 228, ry: 155 },  // 右眼
];
const EYE_YELLOW = 'rgb(255,219,150)';
const FACE_WHITE = 'rgb(251,251,251)';
const MOUTH = { x: 665, y: 1215, w: 290, h: 130, cx: 805, cy: 1235 };

// ---- 純邏輯：behavior tree 的 tick（可獨立測試） ----
// state: { celebrateUntil, nextBlinkAt, blinkUntil }
// 回傳 pose: 'celebrate' | 'blink' | 'neutral'，並就地更新排程欄位。
export function tickPose(state, now, rand = Math.random) {
  // 節點 1：Celebrate（條件：celebrateUntil 未過期）
  if (now < state.celebrateUntil) return 'celebrate';
  // 節點 2：Idle — 偶爾眨眼
  if (now < state.blinkUntil) return 'blink';
  if (now >= state.nextBlinkAt) {
    state.blinkUntil = now + 130;                       // 閉眼 130ms
    state.nextBlinkAt = now + 1800 + rand() * 2700;     // 下次 1.8~4.5s 後
    return 'blink';
  }
  return 'neutral';
}

export class AvatarBT {
  constructor(canvas, src) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.state = { celebrateUntil: 0, nextBlinkAt: performance.now() + 2000, blinkUntil: 0 };
    this._lastPose = null;
    this.img = new Image();
    this.img.onload = () => {
      this._lastPose = null;
      requestAnimationFrame(this._loop.bind(this));
    };
    this.img.src = src;
  }

  // 有消除時呼叫：往右下看＋微笑（連續 combo 會刷新持續時間）
  onMatch() { this.state.celebrateUntil = performance.now() + 900; }

  _loop(now) {
    const pose = tickPose(this.state, now);
    if (pose !== this._lastPose) {
      this._lastPose = pose;
      this._draw(pose);
    }
    requestAnimationFrame(this._loop.bind(this));
  }

  _draw(pose) {
    const { ctx, canvas } = this;
    const s = canvas.width / SRC;
    ctx.setTransform(s, 0, 0, s, 0, 0);
    ctx.clearRect(0, 0, SRC, SRC);
    ctx.drawImage(this.img, 0, 0, SRC, SRC);
    if (pose === 'blink') {
      for (const e of EYES) { this._fillEye(e); this._closedLid(e); }
    } else if (pose === 'celebrate') {
      for (const e of EYES) { this._fillEye(e); this._pupil(e, 60, 50); }
      this._smile();
    }
  }

  // 眼睛內部鋪黃色（蓋掉原本的瞳孔；內縮避免吃到黑框）
  _fillEye(e) {
    const { ctx } = this;
    ctx.fillStyle = EYE_YELLOW;
    ctx.beginPath();
    ctx.ellipse(e.cx, e.cy, e.rx - 34, e.ry - 30, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  _closedLid(e) {
    const { ctx } = this;
    ctx.strokeStyle = '#111';
    ctx.lineWidth = 34;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(e.cx - e.rx + 70, e.cy);
    ctx.quadraticCurveTo(e.cx, e.cy + 55, e.cx + e.rx - 70, e.cy);
    ctx.stroke();
  }

  // 直立長條瞳孔，偏移 (dx,dy) = 視線方向
  _pupil(e, dx, dy) {
    const { ctx } = this;
    ctx.fillStyle = '#111';
    const w = 46, h = 120;
    const x = e.cx + dx, y = e.cy + dy;
    ctx.beginPath();
    ctx.roundRect(x - w / 2, y - h / 2, w, h, w / 2);
    ctx.fill();
  }

  _smile() {
    const { ctx } = this;
    ctx.fillStyle = FACE_WHITE;
    ctx.fillRect(MOUTH.x, MOUTH.y, MOUTH.w, MOUTH.h);
    ctx.strokeStyle = '#111';
    ctx.lineWidth = 20;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.arc(MOUTH.cx, MOUTH.cy, 62, Math.PI * 0.18, Math.PI * 0.82);
    ctx.stroke();
  }
}
