import { useEffect, useState } from 'react'

function parse(): string[] {
  const raw = window.location.hash.replace(/^#\/?/, '')
  return raw
    .split('?')[0]
    .split('/')
    .filter(Boolean)
    .map((s) => {
      try {
        return decodeURIComponent(s)
      } catch {
        return s
      }
    })
}

export function useRoute(): string[] {
  const [route, setRoute] = useState(parse)
  useEffect(() => {
    const onHash = () => {
      setRoute(parse())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return route
}

export function navigate(path: string) {
  const target = href(path)
  if (window.location.hash === target) window.dispatchEvent(new HashChangeEvent('hashchange'))
  else window.location.hash = target
}

export function href(path: string) {
  if (path.startsWith('#')) return path
  return `#${path.startsWith('/') ? path : `/${path}`}`
}
