import { useCallback, useEffect, useRef, useState } from 'react'

export function useMediaQuery(query: string): boolean {
  const get = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(query).matches : false)
  const [matches, setMatches] = useState(get)
  useEffect(() => {
    if (!window.matchMedia) return
    const mql = window.matchMedia(query)
    const on = () => setMatches(mql.matches)
    on()
    mql.addEventListener('change', on)
    return () => mql.removeEventListener('change', on)
  }, [query])
  return matches
}

export const useReducedMotion = () => useMediaQuery('(prefers-reduced-motion: reduce)')
export const useIsMobile = () => useMediaQuery('(max-width: 767px)')

export type AsyncState<T> =
  | { status: 'loading'; data?: undefined; error?: undefined }
  | { status: 'ok'; data: T; error?: undefined }
  | { status: 'error'; data?: undefined; error: unknown }

/** Runs an async loader on mount / when deps change, with reload() for retry buttons. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' })
  const [nonce, setNonce] = useState(0)
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  useEffect(() => {
    let alive = true
    setState({ status: 'loading' })
    loaderRef
      .current()
      .then((data) => {
        if (alive) setState({ status: 'ok', data })
      })
      .catch((error: unknown) => {
        if (alive) setState({ status: 'error', error })
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { ...state, reload }
}

/** Tweens a number from `from` to `to` over `duration` ms (ease-out) whenever `playKey` changes to a truthy value. */
export function useTween(from: number, to: number, playKey: number, duration = 800, reduced = false): number {
  const [value, setValue] = useState(from)
  useEffect(() => {
    if (!playKey) {
      setValue(from)
      return
    }
    if (reduced || from === to) {
      setValue(to)
      return
    }
    let raf = 0
    const start = performance.now()
    setValue(from)
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      setValue(from + (to - from) * eased)
      if (p < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [from, to, playKey, duration, reduced])
  return value
}

/** The live height of an element (e.g. a fixed bottom bar), so content can pad itself clear of it. */
export function useElementHeight<T extends HTMLElement>(): [(el: T | null) => void, number] {
  const [height, setHeight] = useState(0)
  const obs = useRef<ResizeObserver | null>(null)
  const ref = useCallback((el: T | null) => {
    obs.current?.disconnect()
    obs.current = null
    if (!el) {
      setHeight(0)
      return
    }
    const measure = () => setHeight(Math.ceil(el.getBoundingClientRect().height))
    measure()
    if (typeof ResizeObserver !== 'undefined') {
      obs.current = new ResizeObserver(measure)
      obs.current.observe(el)
    }
  }, [])
  useEffect(() => () => obs.current?.disconnect(), [])
  return [ref, height]
}

/** Copies text to the clipboard, falling back to a hidden textarea. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* fall through */
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}
