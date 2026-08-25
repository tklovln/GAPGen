// selfcheck.mjs — match_finder 純邏輯自檢（node web_game/selfcheck.mjs）
// 若 match 判定壞掉，這裡會最先炸。
import assert from 'node:assert';
import { findAllMatches, findHintMove } from './js/match_finder.js';

const W = 6, H = 6;
const mk = (color) => ({ candyColor: color, candyType: 0 });

// 無 match 基底（水平/垂直/2x2 皆無），再注入要測的圖形
const BASE = [
  '012012',
  '201201',
  '120120',
  '012012',
  '201201',
  '120120',
];

// rows: y 為列；grid[x][y]
function gridFromRows(rows) {
  const g = Array.from({ length: W }, () => new Array(H).fill(null));
  rows.forEach((row, y) => [...row].forEach((c, x) => { g[x][y] = c === '.' ? null : mk(Number(c)); }));
  return g;
}
const withRow0 = (row0, row1 = null, row2 = null) => {
  const rows = [...BASE];
  rows[0] = row0;
  if (row1) rows[1] = row1;
  if (row2) rows[2] = row2;
  return gridFromRows(rows);
};
const none = new Set();

// 0. 基底本身無 match
assert.strictEqual(findAllMatches(gridFromRows(BASE), W, H, none).length, 0, '基底不應有 match');

// 1. 水平三連
let m = findAllMatches(withRow0('333012'), W, H, none);
assert.strictEqual(m.length, 1, '應只有一組 match');
assert.strictEqual(m[0].cells.length, 3);
assert.strictEqual(m[0].shape, 'line');

// 2. 水平四連 → four / horizontal（產生直條紋）
m = findAllMatches(withRow0('333312'), W, H, none);
assert.strictEqual(m[0].shape, 'four');
assert.strictEqual(m[0].direction, 'horizontal');

// 3. 五連 → color bomb
m = findAllMatches(withRow0('333332'), W, H, none);
assert.strictEqual(m[0].shape, 'five');

// 4. 2x2 方塊 → spiral
m = findAllMatches(withRow0('332012', '331201'), W, H, none);
assert.strictEqual(m.length, 1);
assert.strictEqual(m[0].shape, 'block_2x2');
assert.strictEqual(m[0].cells.length, 4);

// 5. T 形（橫3 + x1 直臂）→ special (wrapped)
m = findAllMatches(withRow0('333012', '231201', '130120'), W, H, none);
assert.strictEqual(m.length, 1, 'T 形應合併成一組');
assert.strictEqual(m[0].shape, 'special');
assert.strictEqual(m[0].cells.length, 5);

// 6. blocked 格阻斷 match
m = findAllMatches(withRow0('333012'), W, H, new Set(['1,0']));
assert.strictEqual(m.length, 0, 'blocked 阻斷後不成三連');

// 7. hint：swap (1,0)↔(1,1) 可成 333
const hint = findHintMove(withRow0('313012', '231201'), W, H, none);
assert.strictEqual(hint.length, 2, '應找得到提示步');
assert.deepStrictEqual(hint, [{ x: 1, y: 0 }, { x: 1, y: 1 }]);

console.log('selfcheck OK — match_finder 8 項全過');

// ===== avatar behavior tree（tickPose 純邏輯）=====
const { tickPose } = await import('./js/avatar.js');
const st = { celebrateUntil: 0, nextBlinkAt: 1000, blinkUntil: 0 };
assert.strictEqual(tickPose(st, 0), 'neutral', '未到眨眼時間應為 neutral');
assert.strictEqual(tickPose(st, 1000, () => 0.5), 'blink', '到時間應眨眼');
assert.ok(st.blinkUntil === 1130 && st.nextBlinkAt > 1130, '眨眼後應排下次');
assert.strictEqual(tickPose(st, 1100), 'blink', '閉眼期間維持 blink');
assert.strictEqual(tickPose(st, 1200), 'neutral', '眨完回 neutral');
st.celebrateUntil = 2000;
assert.strictEqual(tickPose(st, 1500), 'celebrate', '消除時 celebrate 優先');
assert.strictEqual(tickPose(st, 2000), 'neutral', 'celebrate 過期即結束');
console.log('selfcheck OK — avatar tickPose 6 項全過');
