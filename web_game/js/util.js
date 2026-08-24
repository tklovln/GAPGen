// 共用小工具 — 座標 key、sleep、隨機
export const K = (x, y) => x + ',' + y;
export const XY = (k) => { const [x, y] = k.split(',').map(Number); return { x, y }; };

export const sleep = (sec) => new Promise((r) => setTimeout(r, sec * 1000));

export const randi = (n) => Math.floor(Math.random() * n);
export const randf = (a = 0, b = 1) => a + Math.random() * (b - a);
export const pick = (arr) => arr[randi(arr.length)];

export function shuffleArray(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = randi(i + 1);
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

export const DIRS4 = [{ x: -1, y: 0 }, { x: 1, y: 0 }, { x: 0, y: -1 }, { x: 0, y: 1 }];

export const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
export const lerp = (a, b, t) => a + (b - a) * t;
