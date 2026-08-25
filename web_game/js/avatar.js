// avatar.js — DEO 貓動畫頭像。
// 底圖 DEM02 照畫，眨眼/看右下+微笑用 canvas 在來源圖座標上局部重繪；
// 其他情緒（吼/嫌棄/冷汗/發綠/勝/敗）直接整張換 DEO_emotion 的表情圖。
// 控制邏輯是一個小 behavior tree（tickPose，純函式可測）。

// ---- 底圖 DEM02（1772×1772）量測到的幾何常數 ----
const SRC = 1772;
const EYES = [
  { cx: 605, cy: 1006, rx: 233, ry: 146 },  // 左眼（畫面左）
  { cx: 1068, cy: 957, rx: 228, ry: 155 },  // 右眼
];
const EYE_YELLOW = 'rgb(255,219,150)';
const FACE_WHITE = 'rgb(251,251,251)';
const MOUTH = { x: 665, y: 1215, w: 290, h: 130, cx: 805, cy: 1235 };

// pose → 表情圖檔（base 上另外疊眨眼/微笑；其餘整張替換）
export const EMOTES = {
  base: 'DEM02.png',
  boom: 'DEM03.png',   // 大爆炸狂吼
  meh: 'DEM07.png',    // 無效交換嫌棄
  sweat: 'DEM09.png',  // 剩 ≤5 步冒冷汗
  panic: 'DEM12.png',  // 剩 ≤2 步臉發綠
  win: 'DEM04.png',    // 過關星星眼
  lose: 'DEM05.png',   // 失敗趴平
};

// ---- 純邏輯：behavior tree 的 tick（可獨立測試） ----
// state: { mood, react, reactUntil, movesLeft, celebrateUntil, nextBlinkAt, blinkUntil }
// 優先序：勝負 > 一次性反應(吼/嫌棄) > 發綠(≤2步) > 消除微笑 > 冷汗(≤5步) > 眨眼 > neutral
export function tickPose(state, now, rand = Math.random) {
  if (state.mood === 'win' || state.mood === 'lose') return state.mood;
  if (now < state.reactUntil) return state.react;
  const m = state.movesLeft;
  if (m > 0 && m <= 2) return 'panic';
  if (now < state.celebrateUntil) return 'celebrate';
  if (m > 0 && m <= 5) return 'sweat';
  if (now < state.blinkUntil) return 'blink';
  if (now >= state.nextBlinkAt) {
    state.blinkUntil = now + 130;                       // 閉眼 130ms
    state.nextBlinkAt = now + 1800 + rand() * 2700;     // 下次 1.8~4.5s 後
    return 'blink';
  }
  return 'neutral';
}

export class AvatarBT {
  constructor(canvas, emotionDir) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.state = {
      mood: '', react: '', reactUntil: 0, movesLeft: 99,
      celebrateUntil: 0, nextBlinkAt: performance.now() + 2000, blinkUntil: 0,
    };
    this._lastPose = null;
    this.imgs = {};
    for (const [pose, file] of Object.entries(EMOTES)) {
      const im = new Image();
      im.onload = () => { if (pose === 'base') requestAnimationFrame(this._loop.bind(this)); this._lastPose = null; };
      im.src = emotionDir + file;
      this.imgs[pose] = im;
    }
  }

  // ---- 遊戲事件 API ----
  onMatch() { this.state.celebrateUntil = performance.now() + 900; }
  onExplosion() { this.state.react = 'boom'; this.state.reactUntil = performance.now() + 1200; }
  onBadSwap() { this.state.react = 'meh'; this.state.reactUntil = performance.now() + 800; }
  setMoves(m) { this.state.movesLeft = m; }
  setMood(mood) { this.state.mood = mood; this._lastPose = null; }

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
    // 整張替換的表情圖（載入完成才用，否則先畫底圖）
    const emoteImg = this.imgs[pose];
    if (emoteImg && emoteImg.complete && emoteImg.naturalWidth > 0 && pose !== 'base') {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(emoteImg, 0, 0, canvas.width, canvas.height);
      return;
    }
    // 底圖 + 局部重繪（neutral / blink / celebrate）
    const s = canvas.width / SRC;
    ctx.setTransform(s, 0, 0, s, 0, 0);
    ctx.clearRect(0, 0, SRC, SRC);
    ctx.drawImage(this.imgs.base, 0, 0, SRC, SRC);
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
