// Brand art for the newsprint redesign. One light theme, so there are no "-dark" logo variants any more:
// the logotype is live Gloock text, the mark is the designer's shaker, and the Con is the designer's
// noir silhouette (Figma "home-the-con"), used as a newspaper photo, an arched portrait or a round avatar.
import conSilhouette from '../assets/figma/con-silhouette.svg'
import halftone from '../assets/figma/halftone.svg'
import { ShakerMark } from './Icon'

/** "Grain of Salt" set in Gloock. `size` is the font size in px. */
export function Logotype({ size, className = '', as: Tag = 'span' }: { size?: number; className?: string; as?: 'span' | 'h1' | 'p' }) {
  return (
    <Tag className={`logotype whitespace-nowrap text-ink ${className}`} style={size ? { fontSize: size } : undefined}>
      Grain of Salt
    </Tag>
  )
}

/** Main logo (Home nameplate). Kept for old call sites: the Gloock logotype. */
export function Logo({ size = 200, className = '' }: { size?: number; className?: string }) {
  return <Logotype size={Math.round(size * 0.5)} className={className} />
}

/** Horizontal lockup for the top bar: the logotype. */
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

const SIL_W = 201.165
const SIL_H = 278.477

/**
 * The Con: a noir silhouette in a doorway arch.
 * - shape="door": the arched portrait (`size` = height).
 * - shape="circle": the round avatar (`size` = diameter).
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
        src={conSilhouette}
        width={Math.round((size * SIL_W) / SIL_H)}
        height={size}
        alt="The Con"
        className={`block select-none ${className}`}
        draggable={false}
      />
    )
  }
  if (shape === 'photo') return <ConPhoto width={size} className={className} />
  // Round avatar: crop the head and shoulders out of the arch.
  const k = size / 168
  return (
    <span
      role="img"
      aria-label="The Con"
      className={`relative inline-block shrink-0 overflow-hidden rounded-full border-2 border-ink bg-[#E6DDCB] ${className}`}
      style={{ width: size, height: size }}
    >
      <img
        src={conSilhouette}
        alt=""
        aria-hidden="true"
        draggable={false}
        className="absolute max-w-none select-none"
        style={{ width: SIL_W * k, height: SIL_H * k, left: -16.5 * k, top: -38 * k }}
      />
    </span>
  )
}

/** "Con as a newspaper photo": paper mount, halftone ground, the arch standing on the bottom edge. */
export function ConPhoto({ width = 360, className = '' }: { width?: number; className?: string }) {
  return (
    <span className={`panel block p-2.5 ${className}`} style={{ width: '100%', maxWidth: width }}>
      <span className="relative block overflow-hidden bg-[#E6DDCB]" style={{ aspectRatio: '536 / 295' }}>
        <img
          src={halftone}
          alt=""
          aria-hidden="true"
          draggable={false}
          className="absolute inset-x-0 bottom-0 w-full select-none"
          style={{ height: '45%' }}
        />
        <img
          src={conSilhouette}
          alt="The Con"
          draggable={false}
          className="absolute bottom-0 left-1/2 h-[88%] w-auto -translate-x-1/2 select-none"
        />
      </span>
    </span>
  )
}
