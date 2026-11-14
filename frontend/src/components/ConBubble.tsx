import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from '../lib/hooks'

/**
 * The Con's speech bubble: dark, purple left border, typewriter font (SPEC §3.1).
 * Text types out (skippable with click / Enter / Space / Escape); screen readers get the full line at once.
 */
export function ConBubble({
  text,
  typewriter = true,
  speed = 28,
  size = 'md',
  className = '',
  onDone,
  label = 'The Con',
}: {
  text: string
  typewriter?: boolean
  speed?: number
  size?: 'sm' | 'md' | 'lg'
  className?: string
  onDone?: () => void
  label?: string
}) {
  const reduced = useReducedMotion()
  const animate = typewriter && !reduced
  const [shown, setShown] = useState(animate ? 0 : text.length)
  const doneRef = useRef(onDone)
  doneRef.current = onDone

  useEffect(() => {
    if (!animate) {
      setShown(text.length)
      doneRef.current?.()
      return
    }
    setShown(0)
    let i = 0
    const id = window.setInterval(() => {
      i += 1
      setShown(i)
      if (i >= text.length) {
        window.clearInterval(id)
        doneRef.current?.()
      }
    }, speed)
    return () => window.clearInterval(id)
  }, [text, animate, speed])

  const typing = shown < text.length
  const skip = () => {
    if (typing) {
      setShown(text.length)
      doneRef.current?.()
    }
  }

  const sizes = { sm: 'text-sm px-3 py-2', md: 'text-base px-4 py-3', lg: 'text-lg md:text-xl px-5 py-4 leading-relaxed' }

  return (
    <div className={`con-bubble relative rounded-r-xl rounded-l-sm shadow-lg ${sizes[size]} ${className}`}>
      <span className="sr-only" aria-live="polite">
        {label}: {text}
      </span>
      <p
        aria-hidden="true"
        onClick={skip}
        className={typing ? 'cursor-pointer' : undefined}
        title={typing ? 'Click to skip' : undefined}
      >
        {text.slice(0, shown)}
        {typing && <span className="caret" />}
        {/* reserve the final height so the bubble doesn't grow while typing */}
        <span className="invisible">{text.slice(shown)}</span>
      </p>
      {typing && (
        <button
          type="button"
          onClick={skip}
          className="absolute right-2 bottom-1 font-sans text-[11px] font-semibold tracking-wide text-[#b9a6f5] uppercase hover:text-white"
        >
          Skip
        </button>
      )}
    </div>
  )
}
