// Promise-based tween — 對齊 Godot Tween 的用法（animate → await tween.finished）。
// 全域單一 ticker 驅動（requestAnimationFrame），board 端用 awaitTweensSafe 收尾防卡死。

export const Ease = {
  linear: (t) => t,
  sineInOut: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
  sineOut: (t) => Math.sin((t * Math.PI) / 2),
  sineIn: (t) => 1 - Math.cos((t * Math.PI) / 2),
  quadOut: (t) => 1 - (1 - t) * (1 - t),
  // Godot TRANS_BACK EASE_OUT
  backOut: (t) => {
    const c1 = 1.70158;
    const c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  },
};

const active = new Set();
let last = performance.now();

function frame(now) {
  const dt = Math.min((now - last) / 1000, 0.1);
  last = now;
  for (const tw of [...active]) {
    try {
      tw._step(dt);
    } catch (e) {
      // 目標物件可能已被 destroy（例如糖果中途被炸掉）→ 殺掉該 tween，不能讓整個迴圈死掉
      console.warn('[tween] step 失敗，強制結束該 tween:', e);
      tw.kill();
    }
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

export class Tween {
  constructor() {
    this.running = true;
    this._steps = [];      // [{type:'props'|'interval'|'call', ...}]
    this._idx = 0;
    this._t = 0;
    this.finished = new Promise((res) => { this._resolve = res; });
    active.add(this);
  }

  // 對 target 的多個屬性同時 tween（等同 Godot set_parallel(true) 的一組）。
  // props: { key: {to, from?, delay?, duration?, ease?} }，duration 為本步預設秒數
  tweenProps(target, props, duration, ease = Ease.sineInOut) {
    this._steps.push({ type: 'props', target, props, duration, ease, started: false });
    return this;
  }

  tweenInterval(sec) {
    this._steps.push({ type: 'interval', duration: sec });
    return this;
  }

  tweenCallback(fn) {
    this._steps.push({ type: 'call', fn });
    return this;
  }

  // 自訂逐幀方法（Godot tween_method）
  tweenMethod(fn, from, to, duration, ease = Ease.linear) {
    this._steps.push({ type: 'method', fn, from, to, duration, ease });
    return this;
  }

  setLoops(n = Infinity) { this._loops = n; return this; }

  kill() {
    if (!this.running) return;
    this.running = false;
    active.delete(this);
    this._resolve();
  }

  _step(dt) {
    if (!this.running) return;
    let guard = 0;
    while (dt > 0 && guard++ < 16) {
      if (this._idx >= this._steps.length) {
        if (this._loops && --this._loops > 0) { this._idx = 0; this._t = 0; continue; }
        this.kill();
        return;
      }
      const st = this._steps[this._idx];
      if (st.type === 'call') { st.fn(); this._idx++; continue; }
      const dur = st.duration ?? 0;
      if (st.type === 'props' && !st.started) {
        st.started = true;
        for (const key of Object.keys(st.props)) {
          const p = st.props[key];
          if (p.from === undefined) p.from = st.target[key];
        }
      }
      this._t += dt;
      const t = dur > 0 ? Math.min(this._t / dur, 1) : 1;
      if (st.type === 'props') {
        for (const key of Object.keys(st.props)) {
          const p = st.props[key];
          const pDur = p.duration ?? dur;
          const pDelay = p.delay ?? 0;
          let pt = pDur > 0 ? (this._t - pDelay) / pDur : 1;
          pt = Math.min(Math.max(pt, 0), 1);
          const e = p.ease ?? st.ease;
          st.target[key] = p.from + (p.to - p.from) * e(pt);
        }
      } else if (st.type === 'method') {
        st.fn(st.from + (st.to - st.from) * st.ease(t));
      }
      if (this._t >= dur) {
        dt = this._t - dur;
        this._t = 0;
        if (st.type === 'props') st.started = false;
        this._idx++;
      } else {
        dt = 0;
      }
    }
  }
}

// 等一批 tween 全部結束，含逾時保護 — 對齊 game_board._await_tweens_safe
export async function awaitTweensSafe(tweens, maxSec = 2.5) {
  const pending = tweens.filter((t) => t && t.running);
  if (pending.length === 0) return;
  await Promise.race([
    Promise.all(pending.map((t) => t.finished)),
    new Promise((r) => setTimeout(r, maxSec * 1000)),
  ]);
}
