// Tiny synthesized sound effects (WebAudio, no audio files).
// Sound is on by default, but nothing plays until the player's first tap or key press
// (browsers require a gesture to start audio). Mute is remembered in localStorage.
import { useEffect, useState } from 'react'

export type Sfx = 'thunk' | 'ding' | 'bwomp' | 'flip' | 'tile'

const KEY = 'gos.muted'
let ctx: AudioContext | null = null
let noise: AudioBuffer | null = null
let muted = readMuted()
const listeners = new Set<(m: boolean) => void>()

function readMuted(): boolean {
  try {
    return window.localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function isMuted(): boolean {
  return muted
}

export function setMuted(m: boolean) {
  muted = m
  try {
    window.localStorage.setItem(KEY, m ? '1' : '0')
  } catch {
    /* storage blocked: remembered for this tab only */
  }
  if (!m) unlock()
  listeners.forEach((fn) => fn(m))
}

export function useMuted(): [boolean, (m: boolean) => void] {
  const [m, setM] = useState(muted)
  useEffect(() => {
    listeners.add(setM)
    return () => {
      listeners.delete(setM)
    }
  }, [])
  return [m, setMuted]
}

function unlock() {
  try {
    if (!ctx) {
      const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!AC) return
      ctx = new AC()
    }
    if (ctx.state === 'suspended') void ctx.resume()
  } catch {
    ctx = null
  }
}

/** Call once at startup: the first tap or key press unlocks audio. */
export function installAudioUnlock() {
  const once = () => {
    unlock()
    window.removeEventListener('pointerdown', once, true)
    window.removeEventListener('keydown', once, true)
  }
  window.addEventListener('pointerdown', once, true)
  window.addEventListener('keydown', once, true)
}

function noiseBuffer(c: AudioContext): AudioBuffer {
  if (noise && noise.sampleRate === c.sampleRate) return noise
  const len = Math.floor(c.sampleRate * 0.4)
  noise = c.createBuffer(1, len, c.sampleRate)
  const d = noise.getChannelData(0)
  for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1
  return noise
}

function env(c: AudioContext, t: number, peak: number, attack: number, decay: number): GainNode {
  const g = c.createGain()
  g.gain.setValueAtTime(0.0001, t)
  g.gain.exponentialRampToValueAtTime(peak, t + attack)
  g.gain.exponentialRampToValueAtTime(0.0001, t + attack + decay)
  return g
}

function tone(c: AudioContext, out: AudioNode, type: OscillatorType, f0: number, f1: number, t: number, dur: number, peak: number) {
  const o = c.createOscillator()
  o.type = type
  o.frequency.setValueAtTime(f0, t)
  if (f1 !== f0) o.frequency.exponentialRampToValueAtTime(f1, t + dur)
  const g = env(c, t, peak, 0.005, dur)
  o.connect(g).connect(out)
  o.start(t)
  o.stop(t + dur + 0.05)
}

function hiss(c: AudioContext, out: AudioNode, t: number, dur: number, peak: number, filter: BiquadFilterType, f0: number, f1: number) {
  const s = c.createBufferSource()
  s.buffer = noiseBuffer(c)
  const f = c.createBiquadFilter()
  f.type = filter
  f.frequency.setValueAtTime(f0, t)
  f.frequency.exponentialRampToValueAtTime(f1, t + dur)
  const g = env(c, t, peak, 0.004, dur)
  s.connect(f).connect(g).connect(out)
  s.start(t)
  s.stop(t + dur + 0.05)
}

export function play(name: Sfx) {
  if (muted || !ctx || ctx.state !== 'running') return
  try {
    const c = ctx
    const t = c.currentTime + 0.005
    const out = c.createGain()
    out.gain.value = 0.55
    out.connect(c.destination)
    switch (name) {
      case 'thunk': // a rubber stamp hitting paper
        tone(c, out, 'sine', 150, 55, t, 0.16, 0.7)
        hiss(c, out, t, 0.06, 0.35, 'lowpass', 1400, 300)
        break
      case 'ding': // a bright two-note chime
        tone(c, out, 'triangle', 880, 880, t, 0.35, 0.28)
        tone(c, out, 'sine', 1320, 1320, t + 0.09, 0.5, 0.22)
        break
      case 'bwomp': // a sad trombone-ish slide
        {
          const f = c.createBiquadFilter()
          f.type = 'lowpass'
          f.frequency.value = 900
          f.connect(out)
          tone(c, f, 'sawtooth', 233, 196, t, 0.18, 0.2)
          tone(c, f, 'sawtooth', 185, 110, t + 0.17, 0.38, 0.22)
        }
        break
      case 'flip': // a paper card turning over
        hiss(c, out, t, 0.11, 0.22, 'bandpass', 900, 3200)
        break
      case 'tile': // a small tick as an end-card tile lands
        tone(c, out, 'triangle', 660, 520, t, 0.07, 0.14)
        break
    }
  } catch {
    /* audio is decoration; never let it break the game */
  }
}
