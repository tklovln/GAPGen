// audio.js — 音效：優先播 sfx/*.mp3 取樣，載入失敗回退到程式合成（公式對齊 audio_manager.gd）
const SAMPLE_RATE = 44100;
const MASTER_VOLUME = 0.8;
const SFX_VOLUME = 0.7;

let ctx = null;
let muted = false;

function ensureCtx() {
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

// ============ 取樣音效 ============
// name → 音量。缺檔/解碼失敗的項目留在 _missing，playSample 就回 false 讓呼叫端用合成。
const SFX = {
  match: 0.7, swap: 0.5, swap_back: 0.5, special_create: 0.8,
  special_trigger: 0.8, cascade: 0.6, level_complete: 0.9,
  button: 0.4, obstacle_break: 0.7, explosion: 1.0, explosion_big: 1.0, spin_up: 0.8,
};
const _buffers = new Map();
const _missing = new Set();

// SFX_VERSION: 換音檔時 +1，避免瀏覽器沿用舊快取（檔名不變）
const SFX_VERSION = 2;

// 首次互動時預載全部（都很短，總計 ~280KB）
export async function preloadSamples() {
  const ac = ensureCtx();
  await Promise.all(Object.keys(SFX).map(async (name) => {
    if (_buffers.has(name) || _missing.has(name)) return;
    try {
      const res = await fetch(`sfx/${name}.mp3?v=${SFX_VERSION}`);
      if (!res.ok) throw new Error(res.status);
      _buffers.set(name, await ac.decodeAudioData(await res.arrayBuffer()));
    } catch (_e) {
      _missing.add(name);
    }
  }));
}

// 播放取樣。rate 用來做音高變化（combo/cascade 爬升）。回傳是否播成功。
function playSample(name, rate = 1, volScale = 1) {
  if (muted) return true;                 // 靜音時視為已處理，不要再走合成
  const buf = _buffers.get(name);
  if (!buf) {
    if (!_missing.has(name)) preloadSamples();   // 尚未載完 → 背景補載，本次用合成
    return false;
  }
  const ac = ensureCtx();
  const src = ac.createBufferSource();
  src.buffer = buf;
  src.playbackRate.value = rate;
  const gain = ac.createGain();
  gain.gain.value = (SFX[name] ?? 0.7) * volScale * SFX_VOLUME * MASTER_VOLUME;
  src.connect(gain).connect(ac.destination);
  src.start();
  return true;
}

// 第一次使用者互動時解鎖 AudioContext + 預載取樣
export function unlockAudio() { ensureCtx(); preloadSamples(); }

export function setMuted(m) { muted = m; }
export function toggleMuted() { muted = !muted; return muted; }
export function isMuted() { return muted; }

function playBuffer(fillFn, duration) {
  if (muted) return;
  const ac = ensureCtx();
  const samples = Math.floor(SAMPLE_RATE * duration);
  const buffer = ac.createBuffer(1, samples, SAMPLE_RATE);
  const data = buffer.getChannelData(0);
  fillFn(data, samples);
  const src = ac.createBufferSource();
  src.buffer = buffer;
  const gain = ac.createGain();
  gain.gain.value = SFX_VOLUME * MASTER_VOLUME;
  src.connect(gain).connect(ac.destination);
  src.start();
}

const TAU = Math.PI * 2;

function tone(freq, duration, volume = 1.0) {
  playBuffer((data, samples) => {
    for (let i = 0; i < samples; i++) {
      const t = i / SAMPLE_RATE;
      let env = 1.0 - i / samples;
      env *= env;
      let v = Math.sin(TAU * freq * t) * volume * env;
      v += Math.sin(TAU * freq * 2.0 * t) * volume * env * 0.3;
      data[i] = Math.min(Math.max(v, -1), 1);
    }
  }, duration);
}

function sweep(freqStart, freqEnd, duration) {
  playBuffer((data, samples) => {
    for (let i = 0; i < samples; i++) {
      const t = i / SAMPLE_RATE;
      const progress = i / samples;
      const freq = freqStart + (freqEnd - freqStart) * progress;
      const env = 1.0 - progress;
      data[i] = Math.min(Math.max(Math.sin(TAU * freq * t) * env * 0.6, -1), 1);
    }
  }, duration);
}

function chord(freqs, duration) {
  playBuffer((data, samples) => {
    for (let i = 0; i < samples; i++) {
      const t = i / SAMPLE_RATE;
      const env = 1.0 - i / samples;
      let v = 0;
      for (const f of freqs) v += Math.sin(TAU * f * t) * env;
      v = (v / freqs.length) * 0.7;
      data[i] = Math.min(Math.max(v, -1), 1);
    }
  }, duration);
}

export function playMatchSound(combo = 0) {
  // combo 越高音越亮：取樣用 playbackRate，合成用頻率
  if (playSample('match', Math.min(1 + combo * 0.08, 1.9))) return;
  const freq = Math.min(523.25 * Math.pow(1.12, combo), 1800.0);
  tone(freq, 0.15, 0.6);
}

export function playSwapSound() {
  if (playSample('swap')) return;
  sweep(400, 600, 0.1);
}

export function playSwapBackSound() {
  if (playSample('swap_back', 0.85)) return;
  sweep(500, 300, 0.12);
}

export function playSpecialCreateSound() {
  if (playSample('special_create')) return;
  chord([523.25, 659.25, 783.99], 0.3);
}

export function playSpecialTriggerSound() {
  if (playSample('special_trigger')) return;
  playBuffer((data, samples) => {
    for (let i = 0; i < samples; i++) {
      const t = i / SAMPLE_RATE;
      const progress = i / samples;
      const env = (1.0 - progress) * (1.0 - progress);
      const noise = Math.random() * 2 - 1;
      const toneV = Math.sin(TAU * 120.0 * t * (1.0 - progress * 0.5));
      data[i] = Math.min(Math.max((noise * 0.4 + toneV * 0.6) * env * 0.7, -1), 1);
    }
  }, 0.4);
}

// 道具旋轉加速前奏（蓄力上膛）
export function playSpinUpSound() {
  if (playSample('spin_up')) return;
  sweep(200, 900, 0.9);
}

export function playCascadeSound(cascadeLevel) {
  if (playSample('cascade', Math.min(1 + cascadeLevel * 0.12, 2.0))) return;
  tone(440.0 * Math.pow(1.2, cascadeLevel), 0.2, 0.5);
}

export function playLevelCompleteSound() {
  if (playSample('level_complete')) return;
  const notes = [523.25, 659.25, 783.99, 1046.5];
  const noteDuration = 0.2;
  const total = notes.length * noteDuration;
  playBuffer((data, samples) => {
    for (let i = 0; i < samples; i++) {
      const t = i / SAMPLE_RATE;
      const noteIdx = Math.min(Math.floor(t / noteDuration), notes.length - 1);
      const noteT = t % noteDuration;
      const env = 1.0 - (noteT / noteDuration) * 0.5;
      const freq = notes[noteIdx];
      let v = Math.sin(TAU * freq * t) * env * 0.5;
      v += Math.sin(TAU * freq * 2.0 * t) * env * 0.2;
      data[i] = Math.min(Math.max(v, -1), 1);
    }
  }, total);
}

export function playLevelFailedSound() { sweep(400, 150, 0.5); }

export function playButtonSound() {
  if (playSample('button')) return;
  tone(880, 0.08, 0.3);
}

export function playObstacleBreakSound() {
  if (playSample('obstacle_break')) return;
  playBuffer((data, samples) => {
    for (let i = 0; i < samples; i++) {
      const env = 1.0 - i / samples;
      data[i] = (Math.random() * 2 - 1) * env * 0.5;
    }
  }, 0.15);
}

// 爆炸 boom：低頻掃降 + 噪音衝擊（wrapped/TNT、combo、紙飛機命中用）
export function playExplosionSound(big = false) {
  if (playSample(big ? 'explosion_big' : 'explosion')) return;
  playBuffer((data, samples) => {
    for (let i = 0; i < samples; i++) {
      const t = i / SAMPLE_RATE;
      const progress = i / samples;
      const env = Math.pow(1.0 - progress, 1.6);
      const freq = 150.0 - 110.0 * progress;          // 150Hz → 40Hz 低頻墜落
      const boom = Math.sin(TAU * freq * t);
      const noise = (Math.random() * 2 - 1) * Math.pow(1.0 - progress, 3); // 前段噪音爆點
      data[i] = Math.min(Math.max((boom * 0.8 + noise * 0.6) * env, -1), 1);
    }
  }, 0.5);
}
