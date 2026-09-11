import type { Point } from '@/lib/mock-data'

export function Sparkline({
  data,
  positive,
  width = 96,
  height = 28,
}: {
  data: Point[]
  positive: boolean
  width?: number
  height?: number
}) {
  const values = data.map((d) => d.v)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const step = width / (data.length - 1)

  const coords = data.map((d, i) => {
    const x = i * step
    const y = height - ((d.v - min) / range) * (height - 4) - 2
    return [x, y] as const
  })

  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const color = positive ? 'var(--positive)' : 'var(--negative)'

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      className="overflow-visible"
      aria-hidden="true"
    >
      <polyline
        points={line}
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
