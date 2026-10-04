import type { InputType } from '../types'

export function InputTypeBadges({ types }: { types: InputType[] }) {
  return (
    <span className="type-badges">
      {types.map((t) => (
        <span className={`type-badge type-badge--${t}`} key={t}>
          {t === 'image' ? 'screenshot' : t}
        </span>
      ))}
    </span>
  )
}

export function formatCategory(category: string | null): string {
  if (!category) return 'Not categorised'
  return category
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
