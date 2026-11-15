import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react'
import { IconClose } from './Icon'

/** Mobile bottom sheet: 60% height, drag the handle up to expand, down to close (SPEC §3.6). */
export function BottomSheet({
  open,
  onClose,
  label,
  children,
}: {
  open: boolean
  onClose: () => void
  label: string
  children: ReactNode
}) {
  const [expanded, setExpanded] = useState(false)
  const [dragY, setDragY] = useState(0)
  const start = useRef<number | null>(null)
  const panel = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  useEffect(() => {
    if (!open) {
      setExpanded(false)
      setDragY(0)
      return
    }
    panel.current?.focus({ preventScroll: true })
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeRef.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  if (!open) return null

  const onDown = (e: ReactPointerEvent) => {
    start.current = e.clientY
    ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  }
  const onMove = (e: ReactPointerEvent) => {
    if (start.current == null) return
    setDragY(e.clientY - start.current)
  }
  const onUp = () => {
    if (start.current == null) return
    const dy = dragY
    start.current = null
    setDragY(0)
    if (dy < -50) setExpanded(true)
    else if (dy > 80) {
      if (expanded) setExpanded(false)
      else onClose()
    } else if (Math.abs(dy) < 6) setExpanded((x) => !x)
  }

  return (
    <div className="fixed inset-0 z-40 md:hidden">
      <button type="button" aria-label="Close the evidence kit" className="absolute inset-0 bg-ink/45 fade-in" onClick={onClose} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        className="sheet-up absolute inset-x-0 bottom-0 flex flex-col border-t-[3px] border-press bg-sheet focus-visible:outline-none"
        style={{
          height: expanded ? '92vh' : '60vh',
          transform: dragY ? `translateY(${Math.max(dragY, expanded ? 0 : -window.innerHeight * 0.3)}px)` : undefined,
          transition: start.current == null ? 'height 220ms ease-out, transform 220ms ease-out' : 'none',
        }}
      >
        <div
          className="flex shrink-0 touch-none flex-col items-center gap-1 pt-2 pb-1"
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
        >
          <span className="h-1.5 w-12 bg-[#a8a8a8]" aria-hidden="true" />
          <span className="sr-only">Drag to resize</span>
        </div>
        <div className="flex shrink-0 justify-end gap-1 px-3">
          <button
            type="button"
            className="caps px-2.5 py-1 text-[12.5px] font-semibold text-ink hover:underline"
            onClick={() => setExpanded((x) => !x)}
          >
            {expanded ? 'Shrink' : 'Expand'}
          </button>
          <button type="button" className="caps inline-flex items-center gap-1 px-2.5 py-1 text-[12.5px] font-semibold text-ink hover:underline" onClick={onClose}>
            Close <IconClose size={15} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6 thin-scroll">{children}</div>
      </div>
    </div>
  )
}
