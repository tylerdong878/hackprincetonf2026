// The UI's line-icon set (Figma: "Icons, 24px grid, 2px stroke"). Icons, not emoji, in the chrome;
// share text keeps its emoji. Icons the designer drew are inlined from the Figma export (paths unchanged,
// centred on a 24px grid, stroked in currentColor). The rest come from lucide-react, which is the same
// 24px / 2px family.
import type { LucideIcon, LucideProps } from 'lucide-react'
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Calendar,
  ChartLine,
  Check,
  ChevronDown,
  Clock,
  Cog,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  Glasses,
  Hash,
  Link,
  Lock,
  Maximize2,
  Pause,
  Pencil,
  Play,
  RotateCcw,
  Scissors,
  Server,
  Share,
  SkipForward,
  Sparkles,
  Trophy,
  TriangleAlert,
  Volume2,
  VolumeX,
  X,
  Zap,
} from 'lucide-react'
import type { ReactNode } from 'react'
import type { Outcome } from '../lib/types'

export type IconProps = { size?: number; className?: string; strokeWidth?: number; title?: string }

function wrap(C: LucideIcon, name: string) {
  const W = ({ size = 20, className = '', strokeWidth = 2, title }: IconProps & Omit<LucideProps, 'ref'>) => (
    <C
      size={size}
      strokeWidth={strokeWidth}
      className={`inline-block shrink-0 ${className}`}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      role={title ? 'img' : undefined}
    />
  )
  W.displayName = name
  return W
}

export const IconArrow = wrap(ArrowRight, 'IconArrow')
export const IconArrowLeft = wrap(ArrowLeft, 'IconArrowLeft')
export const IconCheck = wrap(Check, 'IconCheck')
export const IconX = wrap(X, 'IconX')
export const IconClose = wrap(X, 'IconClose')
export const IconWarn = wrap(TriangleAlert, 'IconWarn')
export const IconClock = wrap(Clock, 'IconClock')
export const IconChevron = wrap(ChevronDown, 'IconChevron')
export const IconShare = wrap(Share, 'IconShare')
export const IconPlay = wrap(Play, 'IconPlay')
export const IconPause = wrap(Pause, 'IconPause')
export const IconReplay = wrap(RotateCcw, 'IconReplay')
export const IconSkip = wrap(SkipForward, 'IconSkip')
export const IconVerified = wrap(BadgeCheck, 'IconVerified')
export const IconLink = wrap(Link, 'IconLink')
export const IconExternal = wrap(ExternalLink, 'IconExternal')
export const IconHash = wrap(Hash, 'IconHash')
export const IconPen = wrap(Pencil, 'IconPen')
export const IconScissors = wrap(Scissors, 'IconScissors')
export const IconAxis = wrap(ChartLine, 'IconAxis')
export const IconCalendar = wrap(Calendar, 'IconCalendar')
export const IconEye = wrap(Eye, 'IconEye')
export const IconEyeOff = wrap(EyeOff, 'IconEyeOff')
export const IconExpand = wrap(Maximize2, 'IconExpand')
export const IconGear = wrap(Cog, 'IconGear')
export const IconCopy = wrap(Copy, 'IconCopy')
export const IconTrophy = wrap(Trophy, 'IconTrophy')
export const IconServer = wrap(Server, 'IconServer')
export const IconSoundOn = wrap(Volume2, 'IconSoundOn')
export const IconSoundOff = wrap(VolumeX, 'IconSoundOff')
export const IconZap = wrap(Zap, 'IconZap')
export const IconLock = wrap(Lock, 'IconLock')
export const IconSparkles = wrap(Sparkles, 'IconSparkles')
export const IconGlasses = wrap(Glasses, 'IconGlasses')

/** An inlined Figma icon: `w`×`h` is its exported box; it is centred on a 24px (or larger) square. */
function Glyph({
  w,
  h,
  size = 20,
  className = '',
  strokeWidth,
  title,
  children,
}: IconProps & { w: number; h: number; children: ReactNode }) {
  const side = Math.max(24, w, h)
  const x = -(side - w) / 2
  const y = -(side - h) / 2
  return (
    <svg
      viewBox={`${x} ${y} ${side} ${side}`}
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth ?? 2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`inline-block shrink-0 ${className}`}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      role={title ? 'img' : undefined}
    >
      {children}
    </svg>
  )
}

export function IconSource(p: IconProps) {
  return (
    <Glyph w={14.8333} h={20.3333} {...p}>
      <path d="M1 1H9.25L13.8333 5.58333V19.3333H1V1Z" />
      <path d="M9.25 1V5.58333H13.8333" />
      <path d="M3.75 10.1667H11.0833M3.75 13.8333H11.0833M3.75 6.5H6.5" />
    </Glyph>
  )
}

export function IconData(p: IconProps) {
  return (
    <Glyph w={16.6667} h={15.75} {...p}>
      <path d="M1 14.75H15.6667" />
      <path d="M3.75 14.75V6.5" />
      <path d="M8.33334 14.75V1" />
      <path d="M12.9167 14.75V9.25" />
    </Glyph>
  )
}

export function IconAccount(p: IconProps) {
  return (
    <Glyph w={16.6672} h={17.5836} {...p}>
      <path d="M12.0003 4.66667C12.0003 6.69171 10.3587 8.33334 8.33361 8.33334C6.30856 8.33334 4.66694 6.69171 4.66694 4.66667C4.66694 2.64162 6.30856 1 8.33361 1C10.3587 1 12.0003 2.64162 12.0003 4.66667Z" />
      <path d="M1.00027 16.5833C2.37527 12.4583 5.12527 11.0833 8.33361 11.0833C11.5419 11.0833 14.2919 12.4583 15.6669 16.5833" />
    </Glyph>
  )
}

export function IconLens(p: IconProps) {
  return (
    <Glyph w={25.3333} h={25.3333} {...p}>
      <path d="M18.3333 9.66664C18.3333 14.4531 14.4531 18.3333 9.66664 18.3333C4.88019 18.3333 1 14.4531 1 9.66664C1 4.88019 4.88019 1 9.66664 1C14.4531 1 18.3333 4.88019 18.3333 9.66664Z" />
      <path d="M16.3333 16.3333L24.3333 24.3333" />
    </Glyph>
  )
}

export function IconFolder(p: IconProps) {
  return (
    <Glyph w={18.5} h={13.9167} {...p}>
      <path d="M1 1H6.5L8.33334 2.83333H17.5V12.9167H1V1Z" />
    </Glyph>
  )
}

export function IconBook(p: IconProps) {
  return (
    <Glyph w={16.6667} h={16.6667} {...p}>
      <path d="M1 1H7.41667C8.14601 1 8.84549 1.28973 9.36121 1.80546C9.87694 2.32118 10.1667 3.02065 10.1667 3.75V15.6667C10.1667 15.1804 9.97351 14.7141 9.6297 14.3703C9.28588 14.0265 8.81957 13.8333 8.33334 13.8333H1V1Z" />
      <path d="M10.1667 1H15.6667V13.8333H10.1667" />
    </Glyph>
  )
}

export function IconFlame(p: IconProps) {
  return (
    <Glyph w={13.6667} h={17.8333} {...p}>
      <path d="M6.83333 16.8333C10.1667 16.8333 12.6667 14.3333 12.6667 11C12.6667 6.83333 8.5 5.16667 8.5 1C6 2.66667 4.33333 5.16667 4.33333 7.66667C3.5 6.83333 2.66667 6 2.66667 4.33333C1 6 1 8.5 1 11C1 14.3333 3.5 16.8333 6.83333 16.8333Z" />
    </Glyph>
  )
}

/** The Con's mask (Figma icon-mask). */
export function IconMask(p: IconProps) {
  return (
    <Glyph w={34.9999} h={23.3706} {...p}>
      <path d="M1 2.20394C6.49999 0.37061 12 0.37061 17.5 4.03727C23 0.37061 28.4999 0.37061 33.9999 2.20394C33.9999 13.2039 30.3333 22.3706 24.8333 22.3706C21.1666 22.3706 19.3333 18.7039 17.5 16.8706C15.6666 18.7039 13.8333 22.3706 10.1666 22.3706C4.66666 22.3706 1 13.2039 1 2.20394Z" />
      <path d="M8.33332 10.4539L12 12.2873M26.6666 10.4539L23 12.2873" />
    </Glyph>
  )
}

/** "zzz": the Con is asleep. */
export function IconZzz(p: IconProps) {
  return (
    <Glyph w={24} h={24} {...p}>
      <path d="M3 13h6l-6 7h6" />
      <path d="M12 5h5l-5 6h5" />
      <path d="M18 2h3l-3 4h3" />
    </Glyph>
  )
}

/** "Caught" = a salt crystal (Figma grid-caught). Filled faces, ink edges. */
export function SaltCrystal({ size = 20, className = '', title }: IconProps) {
  return (
    <svg
      viewBox="74.5 16.5 28 28"
      width={size}
      height={size}
      className={`inline-block shrink-0 ${className}`}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      role={title ? 'img' : undefined}
    >
      <g stroke="currentColor" strokeWidth="1.56" strokeLinecap="round" strokeLinejoin="round">
        <path d="M85.9053 18.2927L98.319 22.6714L88.6298 31.1103L76.2161 26.7316L85.9053 18.2927Z" fill="#FFFFFF" />
        <path d="M76.2161 26.7316L88.6298 31.1103L91.0948 42.7073L78.6811 38.3285L76.2161 26.7316Z" fill="#E9E2D3" />
        <path d="M98.319 22.6714L88.6298 31.1103L91.0948 42.7073L100.784 34.2684L98.319 22.6714Z" fill="#CFC6B4" />
      </g>
    </svg>
  )
}

/** The salt-shaker mark (Figma "Shaker icon, from your logo"). */
export function ShakerMark({ size = 28, className = '', title }: IconProps) {
  return (
    <svg
      viewBox="0 0 39.3369 35.221"
      width={size}
      height={Math.round((size * 35.221) / 39.3369)}
      fill="none"
      className={`inline-block shrink-0 ${className}`}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      role={title ? 'img' : undefined}
    >
      <path d="M34.5222 22.2086C33.2641 26.3384 29.6178 31.1029 27.4936 32.1201C26.3708 32.6577 25.0254 31.95 25.0254 31.95C24.3257 31.6557 23.8499 31.4836 23.6648 31.3993C23.6648 31.3993 11.6423 25.7836 1.17775 17.7206C0.963967 17.5558 0.632761 17.2952 0.375462 16.8264C-1.1068 14.1267 2.12464 9.29645 4.40903 6.33652C8.26608 1.3388 11.9741 -0.488104 13.1745 0.108953C13.9543 0.496811 15.4999 1.6923 17.7066 3.74978C22.491 8.21091 28.7723 14.4359 34.3993 20.0168C34.6685 20.284 34.7789 21.3656 34.5222 22.2086Z" fill="#141414" />
      <path d="M12.8949 1.25359C11.6357 0.286392 8.26822 2.60606 4.59044 7.24737C1.38038 11.2982 0.0608973 15.2838 1.31991 16.2509C2.83347 17.4134 6.05727 14.7045 9.15006 10.7497C12.518 6.44295 14.154 2.22064 12.8949 1.25359Z" fill="#FBF7EE" />
      <path d="M30.7458 34.9181C31.9079 35.7461 34.6768 34.8366 36.8587 32.6806C39.3708 30.1983 39.6035 26.6329 39.1506 25.4619C39.0609 25.2301 38.6534 23.6638 37.1336 23.5273C36.7591 23.4937 36.3304 23.6732 35.9863 23.4763C35.6498 23.2838 35.139 22.2162 35.1185 22.4384C35.0797 22.8587 34.1544 25.4801 32.5724 27.8745C30.829 30.5134 28.6764 32.2987 28.0908 32.6052C28.0229 32.6408 28.1372 32.6134 29.2926 32.7342C29.5015 32.7561 29.6751 33.1804 29.7739 33.5904C29.9513 34.327 30.3607 34.6436 30.7458 34.9181Z" fill="#141414" />
      <path d="M25.8831 30.5488C25.8835 30.5485 26.9101 30.246 28.5843 28.8144C30.543 27.1396 33.2489 22.91 33.502 21.0001C33.5375 20.7331 33.2704 20.5956 33.0736 20.4066C27.9774 15.5129 27.8108 14.988 27.4086 15.1192C26.392 15.4507 25.585 16.8088 24.0383 17.7293C19.9507 20.1618 14.8357 21.4075 11.9436 21.8143C11.6534 21.8551 10.8492 21.9683 10.7566 22.3538C10.6928 22.6195 10.9938 22.9029 11.0981 23.0013" fill="#FBF7EE" />
      <path d="M33.2308 33.2934C33.4816 33.097 33.6012 32.8308 33.4979 32.6989C33.3946 32.5669 33.1075 32.6192 32.8567 32.8156C32.6058 33.0121 32.4862 33.2782 32.5895 33.4102C32.6928 33.5421 32.9799 33.4898 33.2308 33.2934Z" fill="#FBF7EE" />
      <path d="M35.0379 33.0756C35.2888 32.8792 35.4084 32.613 35.3051 32.4811C35.2017 32.3492 34.9147 32.4015 34.6638 32.5979C34.413 32.7943 34.2934 33.0605 34.3967 33.1924C34.5 33.3244 34.7871 33.2721 35.0379 33.0756Z" fill="#FBF7EE" />
      <path d="M35.7045 31.498C35.9553 31.3016 36.0749 31.0354 35.9716 30.9034C35.8683 30.7715 35.5812 30.8238 35.3304 31.0202C35.0795 31.2166 34.9599 31.4828 35.0632 31.6148C35.1665 31.7467 35.4536 31.6944 35.7045 31.498Z" fill="#FBF7EE" />
    </svg>
  )
}

/** A clue token: a lens in a paper coin; spent = a slashed muted ring (Figma clue-token / clue-token-spent). */
export function ClueToken({ spent = false, size = 22, className = '' }: { spent?: boolean; size?: number; className?: string }) {
  if (spent) {
    return (
      <svg viewBox="0 0 23.4 23.4" width={size} height={size} fill="none" className={`inline-block shrink-0 ${className}`} aria-hidden="true">
        <path opacity="0.6" d="M22.7 11.7C22.7 17.7751 17.7751 22.7 11.7 22.7C5.62487 22.7 0.7 17.7751 0.7 11.7C0.7 5.62487 5.62487 0.7 11.7 0.7C17.7751 0.7 22.7 5.62487 22.7 11.7Z" strokeWidth="1.4" stroke="#5A544B" />
        <path opacity="0.6" d="M5.09996 18.2999L18.3 5.0999" strokeWidth="1.4" stroke="#5A544B" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" className={`inline-block shrink-0 ${className}`} aria-hidden="true">
      <path d="M12 23C18.0751 23 23 18.0751 23 12C23 5.92487 18.0751 1 12 1C5.92487 1 1 5.92487 1 12C1 18.0751 5.92487 23 12 23Z" fill="#FBF7EE" strokeWidth="2" stroke="#141414" />
      <path d="M14.5575 10.8832C14.5575 12.9235 12.9035 14.5774 10.8633 14.5774C8.82307 14.5774 7.16913 12.9235 7.16913 10.8832C7.16913 8.84301 8.82307 7.18908 10.8633 7.18908C12.9035 7.18908 14.5575 8.84301 14.5575 10.8832Z" strokeWidth="2.2" stroke="#141414" />
      <path d="M13.705 13.7249L17.115 17.1349" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" stroke="#141414" />
    </svg>
  )
}

/** The outcome glyph alone: Fooled ✕, False alarm ⚠, Trusted ✓, Caught = salt crystal. */
export function OutcomeGlyph({ outcome, size = 18, className = '' }: { outcome: Outcome | string; size?: number; className?: string }) {
  if (outcome === 'caught') return <SaltCrystal size={size} className={className} />
  if (outcome === 'fooled') return <IconX size={size} strokeWidth={2.6} className={className} />
  if (outcome === 'false_alarm') return <IconWarn size={size} strokeWidth={2.4} className={className} />
  if (outcome === 'trusted') return <IconCheck size={size} strokeWidth={2.6} className={className} />
  return <span className={`inline-block h-1.5 w-1.5 bg-current ${className}`} aria-hidden="true" />
}

const SQUARE: Record<string, { bg: string; fg: string }> = {
  trusted: { bg: '#141414', fg: '#FBF7EE' },
  caught: { bg: '#FBF7EE', fg: '#141414' },
  fooled: { bg: '#C8231B', fg: '#FFFFFF' },
  false_alarm: { bg: '#B9822A', fg: '#141414' },
}

/** The outcome grid square (Figma "Grid squares"): filled square, 1.5px ink edge, glyph centred. */
export function OutcomeSquare({
  outcome,
  size = 32,
  className = '',
  title,
}: {
  outcome: Outcome | string | null | undefined
  size?: number
  className?: string
  title?: string
}) {
  const c = outcome ? SQUARE[outcome] : undefined
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center border-[1.5px] ${c ? 'border-ink' : 'border-dashed border-line-soft'} ${className}`}
      style={{ width: size, height: size, background: c?.bg ?? 'transparent', color: c?.fg }}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {outcome && c && <OutcomeGlyph outcome={outcome} size={Math.round(size * 0.58)} />}
    </span>
  )
}
