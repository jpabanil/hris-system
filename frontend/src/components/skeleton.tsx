export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2.5" aria-hidden="true" aria-busy="true">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="h-9 animate-pulse rounded-xl bg-soft" style={{ animationDelay: `${index * 80}ms` }} />
      ))}
    </div>
  )
}
