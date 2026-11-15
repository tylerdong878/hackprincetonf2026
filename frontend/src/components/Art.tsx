// Brand art for the v2 newsprint design (Figma). The logotype is the designer's blackletter
// "Grain of Salt" image, and the Con is the shattering detective silhouette (Figma "대지 1"),
// used full-length, as a newspaper photo or cropped to a round avatar.
import detective from '../assets/figma/detective-shatter.webp'
import halftone from '../assets/figma/halftone.svg'
import logoBlack from '../assets/figma/logo-blackletter.webp'
import logoWhite from '../assets/figma/masthead-torn.webp'
import { ShakerMark } from './Icon'

const LOGO_RATIO = 1920 / 432

/**
 * "Grain of Salt" in blackletter. `size` is the cap height-ish: the image is drawn `size * 1.25` tall.
 * `tone="split"` is the Home masthead: white type that inverts against whatever is behind it, so it
 * reads white on the black paper and black on the newsprint.
 */
export function Logotype({
  size = 34,
  className = '',
  tone = 'ink',
  as: Tag = 'span',
}: {
  size?: number
  className?: string
  tone?: 'ink' | 'split'
  as?: 'span' | 'h1' | 'p'
}) {
  const h = Math.round(size * 1.25)
  return (
    <Tag className={`inline-block leading-none ${className}`}>
      <img
        src={tone === 'split' ? logoWhite : logoBlack}
        alt="Grain of Salt"
        draggable={false}
        className="block h-auto max-w-full select-none"
        style={{ width: Math.round(h * LOGO_RATIO), mixBlendMode: tone === 'split' ? 'difference' : undefined }}
      />
    </Tag>
  )
}

/** Main logo. Kept for old call sites. */
export function Logo({ size = 200, className = '' }: { size?: number; className?: string }) {
  return <Logotype size={Math.round(size * 0.5)} className={className} />
}

/** Horizontal lockup for the top bar. */
export function Wordmark({ height = 34, className = '' }: { height?: number; className?: string }) {
  return <Logotype size={Math.round(height * 0.82)} className={className} />
}

/** The shaker mark: small marks, empty states, the loading spinner. */
export function BrandIcon({ size = 28, className = '', alt = '' }: { size?: number; className?: string; alt?: string; surface?: string }) {
  return <ShakerMark size={size} className={className} title={alt || undefined} />
}

export function Spinner({ size = 28, label = 'Loading' }: { size?: number; label?: string }) {
  return (
    <span role="status" aria-label={label} className="inline-flex">
      <span className="wiggle inline-flex">
        <ShakerMark size={size} />
      </span>
    </span>
  )
}

const DET_W = 725
const DET_H = 1024

/**
 * The Con: the shattering detective.
 * - shape="door": the full figure (`size` = height).
 * - shape="circle": the round avatar, hat and shoulders (`size` = diameter).
 * - shape="photo": the newspaper photo (halftone frame, `size` = frame width).
 */
export function ConMascot({
  size = 120,
  className = '',
  shape = 'circle',
}: {
  size?: number
  className?: string
  framed?: boolean
  shape?: 'circle' | 'door' | 'photo'
}) {
  if (shape === 'door') {
    return (
      <img
        src={detective}
        width={Math.round((size * DET_W) / DET_H)}
        height={size}
        alt="The Con"
        className={`block select-none ${className}`}
        draggable={false}
      />
    )
  }
  if (shape === 'photo') return <ConPhoto width={size} className={className} />
  // Round avatar: the hat, head and shoulders (the top-right 300px of the 725x1024 figure).
  const k = size / 300
  return (
    <span
      role="img"
      aria-label="The Con"
      className={`relative inline-block shrink-0 overflow-hidden rounded-full border-2 border-ink bg-[#dcdcdc] ${className}`}
      style={{ width: size, height: size }}
    >
      <img
        src={detective}
        alt=""
        aria-hidden="true"
        draggable={false}
        className="absolute max-w-none select-none"
        style={{ width: DET_W * k, height: DET_H * k, left: -425 * k, top: -2 * k }}
      />
    </span>
  )
}

/** "Con as a newspaper photo": paper mount, halftone ground, the detective walking out of frame. */
export function ConPhoto({ width = 360, className = '' }: { width?: number; className?: string }) {
  return (
    <span className={`panel block p-2.5 ${className}`} style={{ width: '100%', maxWidth: width }}>
      <span className="relative block overflow-hidden bg-[#e2e2e2]" style={{ aspectRatio: '536 / 295' }}>
        <img
          src={halftone}
          alt=""
          aria-hidden="true"
          draggable={false}
          className="absolute inset-x-0 bottom-0 w-full opacity-60 grayscale select-none"
          style={{ height: '45%' }}
        />
        <img
          src={detective}
          alt="The Con"
          draggable={false}
          className="absolute -bottom-[22%] left-1/2 h-[125%] w-auto -translate-x-1/2 select-none"
        />
      </span>
    </span>
  )
}

export { detective as detectiveSrc, halftone as halftoneSrc }
