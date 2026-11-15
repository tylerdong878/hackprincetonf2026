// Static copy: the Con's fallback lines (SPEC §5) and the Casebook (SPEC §3.9, §4).
import type { PerTrick } from './types'
import { TRICK_FORMAT } from './format'

export const CON_LINES = {
  idle: [
    'Take your time. I already took mine.',
    'Every post here looks honest. That’s rather the point.',
    'Real news, mostly. Mostly is my favorite word.',
  ],
  evidence: ['Checking the receipts? How old-fashioned.', 'Reading the fine print. Bold move.', 'Go on, look closer. I dare you.'],
  outOfClues: ['No more clues. Now it’s just you and your gut.'],
  markReal: ['Trusting. I like that in a detective.', 'Real, you say? We’ll see.'],
  markDoctored: ['Suspicious, are we? Careful: real posts bite back.', 'Doctored? Prove it. Or don’t.'],
  allMarked: ['All marked. Submit when you’re sure. Or when you’re not.'],
  submitting: ['Let’s see how you did…'],
}

/** Fallback quips for a Daily reveal when the server sends no con_line (e.g. a trusted real post). */
export const CON_QUIPS: Record<string, string[]> = {
  trusted: ['Real. I didn’t lay a finger on that one.', 'You trusted the truth. Annoyingly sensible.', 'Real, and you knew it. Fine.'],
  // Honest lines only (CONTRACT §8.4): never claim the player checked evidence they didn't open.
  caught: ['Caught. I’ll be subtler tomorrow.', 'Good eye. That one was mine.'],
  fooled: ['Got you. It looked so official, didn’t it?', 'Slipped right past. My favorite kind.'],
  false_alarm: ['That one was real. I didn’t even have to lie.', 'A grain of salt, detective. Not the whole shaker.'],
}

export const LEAN_EXPLAINER = 'Too gullible and fakes slip by. Too paranoid and you doubt the truth. Both cost points.'

export function pick(lines: string[], seed = Math.random()): string {
  return lines[Math.floor(seed * lines.length) % lines.length]
}

/** "What the Con thinks of you", from the dossier stats (SPEC §3.8). */
export function conVerdictOnPlayer(perTrick: Record<string, PerTrick> | undefined, cases: number): string {
  if (!cases) return 'No cases yet. I’ve been looking forward to meeting you.'
  const entries = Object.entries(perTrick ?? {})
  const worstMiss = entries.slice().sort((a, b) => b[1].miss_rate - a[1].miss_rate)[0]
  const worstAlarm = entries.slice().sort((a, b) => b[1].false_alarm_rate - a[1].false_alarm_rate)[0]
  const miss = worstMiss && worstMiss[1].miss_rate >= 0.34 ? TRICK_FORMAT[worstMiss[0]] ?? worstMiss[0] : null
  const alarm = worstAlarm && worstAlarm[1].false_alarm_rate >= 0.34 ? TRICK_FORMAT[worstAlarm[0]] ?? worstAlarm[0] : null
  if (miss && alarm && miss !== alarm) return `You trust ${miss} too easily, and you doubt honest ${alarm}. Delicious.`
  if (miss) return `You trust ${miss} too easily. I’ve made a note.`
  if (alarm) return `You doubt honest ${alarm}. A grain of salt, detective. Not the whole shaker.`
  return 'Annoyingly sharp. I’ll have to try harder.'
}

export interface TrickPage {
  id: string
  name: string
  icon: string
  what: string
  example: string
  tell: string
  tool: string
  realWorld: string
}

export const CASEBOOK: TrickPage[] = [
  {
    id: 'misleading-chart',
    name: 'Misleading chart',
    icon: '📊',
    what: 'Real numbers drawn to tell a story they don’t support: an axis that doesn’t start at zero, a hand-picked date window, or an uneven scale.',
    example:
      'Two bars, April 2025 and July 2026, on an axis that starts at 19¢. The gap looks like a cliff. Same month a year apart, prices barely moved (25.11¢ → 25.19¢, EIA).',
    tell: 'Look at where the axis starts and which months were chosen. A suspiciously narrow window or a floor above zero is a red flag.',
    tool: '📊 Check the data: the raw table plus an honest chart with a zero baseline and the full date range.',
    realWorld: 'Find the original dataset (EIA, BLS, Census), compare the same period year over year, and redraw it in your head from zero.',
  },
  {
    id: 'out-of-context-quote',
    name: 'Out of context',
    icon: '📄',
    what: 'A real quote from a real person, cut at the point where it flips or exaggerates its meaning. Dropping “but”, “if”, or “not yet” is enough.',
    example: 'Quoting “these actions will result in no net increase” without the next sentence explaining that some charges rise while others fall.',
    tell: 'The quote feels unusually clean or absolute, and the post doesn’t link the full remarks.',
    tool: '📄 Open source: the full article or transcript, with the quoted passage highlighted in context.',
    realWorld: 'Lateral reading: search the quote, find the original article or video, and read the sentences before and after.',
  },
  {
    id: 'cherry-picked-stat',
    name: 'Cherry-picked stat',
    icon: '🔢',
    what: 'A real number stated without its denominator or baseline, or the one month that happens to support the claim.',
    example: '“Bills up $4.09!” without the same article’s next line: other charges fall $4.14, so the bill ends up 5 cents cheaper.',
    tell: 'A big number with no “out of what” or “compared to when”.',
    tool: '📊 Check the data: the full numbers, with the missing denominator or time range highlighted.',
    realWorld: 'Ask “percent of what?” and “since when?”, then find the full table the number came from.',
  },
  {
    id: 'edited-detail',
    name: 'Edited detail',
    icon: '✏️',
    what: 'A real headline with one detail swapped: a number, a date or a place. Everything else is word for word, which is why it feels trustworthy.',
    example: '“NJ bills jumped roughly 20 percent last year” becomes “NJ bills jumped roughly 40 percent last year”, posted by a made-up account.',
    tell: 'The story checks out, but one specific number, date or place doesn’t match the original.',
    tool: '📄 Open source: compare the exact figures, dates and places against the original article.',
    realWorld: 'Search the headline’s key phrase and compare the numbers in the first few results from reputable outlets.',
  },
  {
    id: 'made-up-story',
    name: 'Made up',
    icon: '✨',
    what: 'A whole story the Con invented: a plausible claim from a made-up account, loosely modeled on something real. No outlet ever ran it.',
    example:
      'A made-up account posts “Scientists just taught octopuses to open childproof jars in exactly 9 seconds.” It borrows the feel of real octopus stories, but no outlet ran it, no study is named, and “exactly 9 seconds” is too neat.',
    tell: 'Nothing behind it: no outlet, study or place you could look up, and it sounds a little too perfect. Real news can be strange; the Con’s stories are usually too neat.',
    tool: '📄 Open source: the closest real story, which says something different.',
    realWorld: 'Search the claim and look for who reported it. If no reputable outlet ran it, treat it as made up.',
  },
]
