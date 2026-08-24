// audio.js — WebAudio 版程式合成音效，波形公式對齊 audio_manager.gd
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

// 第一次使用者互動時解鎖 AudioContext
export function unlockAudio() { ensureCtx(); }

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
  const freq = Math.min(523.25 * Math.pow(1.12, combo), 1800.0);
  tone(freq, 0.15, 0.6);
}

export function playSwapSound() { sweep(400, 600, 0.1); }
export function playSwapBackSound() { sweep(500, 300, 0.12); }
export function playSpecialCreateSound() { chord([523.25, 659.25, 783.99], 0.3); }

export function playSpecialTriggerSound() {
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

export function playCascadeSound(cascadeLevel) {
  tone(440.0 * Math.pow(1.2, cascadeLevel), 0.2, 0.5);
}

export function playLevelCompleteSound() {
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
export function playButtonSound() { tone(880, 0.08, 0.3); }

export function playObstacleBreakSound() {
  playBuffer((data, samples) => {
    for (let i = 0; i < samples; i++) {
      const env = 1.0 - i / samples;
      data[i] = (Math.random() * 2 - 1) * env * 0.5;
    }
  }, 0.15);
}
