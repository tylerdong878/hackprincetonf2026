// Brand art. The logo set (public/logo-main-*, wordmark-*, icon-*) is monochrome on purpose:
// "-dark" files (white lines) go on the dark theme, "-light" files (black lines) on the light theme.
// The theme follows prefers-color-scheme (dark is the default), so <picture> picks the variant.
import { useId } from 'react'

function ThemedImg({
  name,
  width,
  height,
  alt,
  className = '',
  surface = 'theme',
}: {
  name: 'logo-main' | 'wordmark' | 'icon'
  width: number
  height: number
  alt: string
  className?: string
  /** 'theme' follows the page theme; 'light' / 'dark' pin it for a fixed surface (e.g. manila paper). */
  surface?: 'theme' | 'light' | 'dark'
}) {
  const img = (
    <img
      src={`/${name}-${surface === 'light' ? 'light' : 'dark'}.svg`}
      width={width}
      height={height}
      alt={alt}
      className={className}
      draggable={false}
      decoding="async"
    />
  )
  if (surface !== 'theme') return img
  return (
    <picture>
      <source media="(prefers-color-scheme: light)" srcSet={`/${name}-light.svg`} />
      {img}
    </picture>
  )
}

/** Main logo: the shaker character with "grain of salt" on its body (Home / Title). */
export function Logo({ size = 200, className = '' }: { size?: number; className?: string }) {
  return <ThemedImg name="logo-main" width={size} height={size} alt="Grain of Salt" className={className} />
}

/** Horizontal lockup for the top bar. */
export function Wordmark({ height = 34, className = '' }: { height?: number; className?: string }) {
  return <ThemedImg name="wordmark" width={Math.round((height * 1183) / 400)} height={height} alt="Grain of Salt" className={className} />
}

/** The character without the name: small marks, empty states, the loading spinner. */
export function BrandIcon({
  size = 28,
  className = '',
  alt = '',
  surface = 'theme',
}: {
  size?: number
  className?: string
  alt?: string
  surface?: 'theme' | 'light' | 'dark'
}) {
  return <ThemedImg name="icon" width={size} height={size} alt={alt} className={className} surface={surface} />
}

export function Spinner({ size = 28, label = 'Loading' }: { size?: number; label?: string }) {
  return (
    <span role="status" aria-label={label} className="inline-flex">
      <span className="wiggle inline-flex">
        <BrandIcon size={size} />
      </span>
    </span>
  )
}

/** The Con: a salt shaker in a fedora and trench coat. `framed` puts him in a doorway of light. */
export function ConMascot({
  size = 120,
  className = '',
  framed = true,
  shape = 'circle',
}: {
  size?: number
  className?: string
  framed?: boolean
  shape?: 'circle' | 'door'
}) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const clip = `con-clip-${uid}`
  const lamp = `con-lamp-${uid}`
  return (
    <svg viewBox="0 0 512 512" width={size} height={size} className={className} role="img" aria-label="The Con">
      <defs>
        <clipPath id={clip}>
          <rect x="176" y="196" width="160" height="250" rx="50" />
        </clipPath>
        <radialGradient id={lamp} cx="50%" cy="35%" r="70%">
          <stop offset="0%" stopColor="#FFF8E6" />
          <stop offset="60%" stopColor="#EFE4CC" />
          <stop offset="100%" stopColor="#C9B892" />
        </radialGradient>
      </defs>
      {framed &&
        (shape === 'door' ? (
          <path d="M96,512 L96,150 C96,60 170,20 256,20 C342,20 416,60 416,150 L416,512 Z" fill={`url(#${lamp})`} />
        ) : (
          <circle cx="256" cy="256" r="256" fill={`url(#${lamp})`} />
        ))}
      <ellipse cx="256" cy="458" rx="110" ry="14" fill="#12141C" opacity="0.18" />
      <rect x="176" y="196" width="160" height="250" rx="50" fill="#EFE4CC" />
      <rect x="196" y="262" width="12" height="70" rx="6" fill="#FFFFFF" opacity="0.75" />
      <g clipPath={`url(#${clip})`}>
        <path d="M170,350 L232,350 L256,410 L280,350 L342,350 L342,452 L170,452 Z" fill="#B08D57" />
        <path d="M232,350 L256,410 L280,350" fill="none" stroke="#12141C" strokeWidth="6" strokeLinejoin="round" />
        <line x1="256" y1="410" x2="256" y2="452" stroke="#12141C" strokeWidth="5" />
        <circle cx="268" cy="422" r="5" fill="#12141C" />
        <circle cx="268" cy="438" r="5" fill="#12141C" />
      </g>
      <rect x="176" y="196" width="160" height="250" rx="50" fill="none" stroke="#12141C" strokeWidth="10" />
      <ellipse cx="256" cy="228" rx="76" ry="14" fill="#12141C" opacity="0.18" />
      <path d="M212,250 Q229,240 246,250 Q229,257 212,250 Z" fill="#12141C" />
      <path d="M266,250 Q283,240 300,250 Q283,257 266,250 Z" fill="#12141C" />
      <circle cx="290" cy="248" r="3" fill="#8B5CF6" />
      <path d="M210,236 L246,238" fill="none" stroke="#12141C" strokeWidth="7" strokeLinecap="round" />
      <path d="M266,232 Q284,220 302,229" fill="none" stroke="#12141C" strokeWidth="7" strokeLinecap="round" />
      <path d="M226,294 Q258,310 292,286" fill="none" stroke="#12141C" strokeWidth="8" strokeLinecap="round" />
      <path d="M292,286 L299,281" fill="none" stroke="#12141C" strokeWidth="6" strokeLinecap="round" />
      <ellipse cx="256" cy="200" rx="126" ry="24" fill="#12141C" />
      <path d="M178,196 C178,128 206,100 256,100 C306,100 334,128 334,196 Z" fill="#12141C" />
      <path d="M222,110 Q256,126 290,110" fill="none" stroke="#2A2D3A" strokeWidth="6" strokeLinecap="round" />
      <path d="M181,168 L331,168 L333,190 L179,190 Z" fill="#8B5CF6" />
      <g fill="#3A3E4E">
        <circle cx="236" cy="134" r="5" />
        <circle cx="256" cy="128" r="5" />
        <circle cx="276" cy="134" r="5" />
      </g>
    </svg>
  )
}
