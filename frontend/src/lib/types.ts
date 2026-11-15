// Shapes from CONTRACT.md §2.1, §3, §5, §6. Fields the server may omit are optional.

export type TrickId = 'out-of-context-quote' | 'misleading-chart' | 'cherry-picked-stat' | 'edited-detail' | (string & {})
export type ToolId = 'source' | 'data' | 'account'

export interface ChartPoint {
  label: string
  value: number
}

export interface ChartSpec {
  type: 'bar' | 'line'
  title?: string | null
  unit?: string | null
  points: ChartPoint[]
  y_min?: number | null
  y_max?: number | null
}

export interface Author {
  name: string
  handle: string
  kind: 'outlet' | 'official' | 'person' | (string & {})
  verified: boolean
  avatar_color?: string | null
}

export interface Quote {
  text: string
  speaker?: string | null
}

export interface Post {
  id: string
  author: Author
  posted_at: string
  body: string
  quote?: Quote | null
  chart?: ChartSpec | null
  source_label?: string | null
  tools: ToolId[]
  /** v2 display hint for Daily cards; derived from the contents when absent. */
  card_style?: 'headline' | 'quote' | 'chart' | 'stat' | null
}

export interface GameCase {
  id: string
  number: number
  title: string
  topic: string
  briefing: string
  clue_budget: number
  trick_options: TrickId[]
  posts: Post[]
  /** One line shown muted under the feed, never inside a card (same text on every case). */
  notice?: string | null
}

export interface CaseSummary {
  id: string
  number: number
  title: string
  topic: string
  daily?: boolean
  origin?: string
  difficulty?: string
}

// ---- Evidence (one tool at a time) ----
export interface SourceEvidence {
  outlet?: string
  date?: string
  url?: string
  before?: string
  highlight?: string
  after?: string
}

export interface DataEvidence {
  title?: string
  unit?: string
  url?: string
  table?: ChartPoint[]
  honest_chart?: ChartSpec | null
  note?: string
}

export interface AccountEvidence {
  name?: string
  handle?: string
  created?: string | null
  followers?: number | null
  verified?: boolean
  bio?: string
  recent_posts?: string[]
}

export type AnyEvidence = SourceEvidence | DataEvidence | AccountEvidence

export interface EvidenceResponse {
  evidence: AnyEvidence | Record<string, unknown>
  clues_left: number
}

// ---- Verdict ----
export interface VerdictChoice {
  doctored: boolean
  trick: TrickId | null
  confidence: number | null
}

export type Outcome = 'caught' | 'trusted' | 'fooled' | 'false_alarm'

export interface ChartDiff {
  type: 'chart'
  shown: ChartSpec
  original: ChartSpec
}
export interface QuoteDiff {
  type: 'quote'
  shown: string
  original: string
  removed?: string[]
}
export interface StatDiff {
  type: 'stat'
  shown: string
  original: string
  missing?: string
}
export interface DetailDiff {
  type: 'detail'
  shown: string
  original: string
  changed?: { from: string; to: string }[]
}
export type Diff = ChartDiff | QuoteDiff | StatDiff | DetailDiff

export interface PostResult {
  post_id: string
  outcome: Outcome
  points: number
  doctored: boolean
  trick?: TrickId | null
  trick_named_correctly?: boolean
  suspicious_real?: boolean
  tell?: string | null
  explanation?: string | null
  con_line?: string | null
  diff?: Diff | null
  rarity?: Rarity | null
  /** CONTRACT §8.7: a bonus for a correct call few players made ("Rare catch" +50, "One in a shaker" +100). */
  rarity_bonus?: RarityBonus | null
}

export interface RarityBonus {
  label: string
  points: number
}

export interface Crowd {
  said_doctored_pct: number
  correct_pct: number
  n: number
}
export interface Rarity {
  correct_pct: number
  n: number
}

export interface VerdictResponse {
  score: number
  clue_bonus?: number
  clean_case: boolean
  con_line_clean?: string | null
  results: PostResult[]
  rating: number
  rank: string
  adaptation_message?: string | null
  share_grid?: string
  // v2 (CONTRACT §7.2)
  lean?: number | null
  lean_label?: string | null
  streak?: number | null
  daily_number?: number | null
  share_text?: string | null
}

// ---- Daily (CONTRACT §7.2) ----
export interface DailyResponse {
  case: GameCase
  daily_number: number
  date: string
  theme?: string | null
  already_played: boolean
  result?: VerdictResponse | null
  /** Cards this player already answered (their reveals), for resuming mid-daily. */
  answered?: Record<string, PostResult>
  clues_left?: number
}

export interface DailyArchiveItem {
  date: string
  daily_number: number
  title: string
  theme?: string | null
  case_id: string
}

export interface AnswerResponse {
  result: PostResult
  crowd: Crowd | null
  clues_left?: number
  rarity?: Rarity | null
  rarity_bonus?: RarityBonus | null
}

// ---- Con the Con (CONTRACT §7.3) ----
export type FoolTool = 'crop' | 'axis' | 'window' | 'drop'

/** The Con's level (CONTRACT §8.1): 1 Rookie (no evidence), 2 Street (one check, fast model), 3 Master. */
export type ConLevel = 1 | 2 | 3

export interface LevelRecord {
  fooled: number
  played: number
}

export interface FoolDeckItem {
  id: string
  kind: 'quote' | 'chart' | 'stat' | (string & {})
  post: Post
  /** The made-up account a changed post will show (CONTRACT §8.3): the same in the preview and the verdict. */
  edited_author?: Author | null
  tools: FoolTool[]
  editable: {
    quote_words?: string[]
    chart_series?: ChartPoint[]
    stat?: { full: string; droppable: { id: string; text: string; shown_without: string }[] }
  }
}

export type FoolEdit =
  | { type: 'none' }
  | { type: 'crop'; keep_word_indices: number[] }
  | { type: 'axis'; y_min: number }
  | { type: 'window'; window: [string, string] }
  | { type: 'drop'; drop: string }

export type FoolOutcome = 'caught' | 'fooled_the_con' | 'con_false_alarm' | 'con_trusted'

export interface FoolJudgeResponse {
  edited_post: Post
  changed: boolean
  trick: TrickId | null
  diff: Diff | null
  con: {
    checked: ToolId[]
    verdict: 'doctored' | 'real'
    trick_guess?: TrickId | null
    reasoning: string[]
    confidence?: number | null
    model?: string | null
    cached?: boolean
  }
  outcome: FoolOutcome
  con_line?: string | null
  /** The level that judged this round (CONTRACT §8.1). */
  level?: ConLevel | null
  /** The player's all-time Con the Con record, overall and per level. */
  scoreboard?: { fooled?: number; played?: number; by_level?: Partial<Record<'1' | '2' | '3', LevelRecord>> } | null
}

// ---- Player ----
export interface TrickCounts {
  shown?: number
  caught?: number
  missed?: number
  named?: number
  honest_shown?: number
  false_alarms?: number
}

export interface PerTrick {
  miss_rate: number
  false_alarm_rate: number
  mastery: number
}

export interface HistoryEntry {
  case_id: string
  at?: string
  score?: number
  outcomes?: Record<string, Outcome | string>
}

export interface Profile {
  player_id: string
  created_at?: string
  tricks?: Record<string, TrickCounts>
  recent?: { doctored: boolean; outcome: string; format?: string }[]
  history?: HistoryEntry[]
  daily_played?: string[]
  lean?: number | null
  lean_label?: string | null
  streak?: number | null
  rating: number
  rank: string
  per_trick?: Record<string, PerTrick>
}

// ---- Editor's Desk ----
export interface CaseMeta {
  status?: string
  origin?: string
  daily?: boolean
  difficulty?: string | null
  created_at?: string | null
  tricks?: string[]
  sources?: string[]
  rejection_reason?: string | null
  [k: string]: unknown
}

export interface QueueItem {
  id: string
  number?: number
  /** The day number (No. 1, No. 2…) for an approved daily; null otherwise. */
  daily_number?: number | null
  title?: string
  topic?: string
  meta?: CaseMeta
  // Some servers flatten meta onto the item.
  status?: string
  origin?: string
  difficulty?: string | null
  created_at?: string | null
  tricks?: string[]
  solver?: { pass?: boolean; difficulty?: string } | null
  has_pipeline_log?: boolean
  has_solver_log?: boolean
  [k: string]: unknown
}

export interface AnswerKeyPost {
  doctored: boolean
  trick?: string
  tell?: string
  explanation?: string
  suspicious_real?: boolean
  con_line_fooled?: string
  con_line_caught?: string
  con_line_false_alarm?: string
  diff?: Diff
}

export interface AnswerKey {
  clean_case: boolean
  posts: Record<string, AnswerKeyPost>
  con_line_clean?: string | null
}

export interface EditorCase {
  case: GameCase
  evidence?: Record<string, Partial<Record<ToolId, AnyEvidence>>>
  answer_key: AnswerKey
  meta: CaseMeta
  solver_log?: string | null
}

// ---- Pipeline log (CONTRACT §6) ----
export interface Todo {
  content: string
  status: 'pending' | 'in_progress' | 'completed' | (string & {})
}

export interface PipelineEvent {
  t: number
  type: string
  spoiler?: boolean
  todos?: Todo[]
  name?: string
  task?: string
  agent?: string
  tool?: string
  summary?: string
  path?: string
  pass?: boolean
  tools_used?: string[]
  difficulty?: string
  attempt?: number
  status?: string
  [k: string]: unknown
}
