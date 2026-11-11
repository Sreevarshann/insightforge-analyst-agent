/** Original InsightForge mark: an anvil-like base with a rising data spark. */
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="30" height="30" rx="9" fill="currentColor" opacity="0.08" />
      <path d="M7 22.5h18l-2.5 3.5h-13L7 22.5Z" fill="var(--muted)" />
      <path d="M8 19.5 13 14l4 3 7-8.5" stroke="var(--lime)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="24" cy="8.5" r="2.4" fill="var(--coral)" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="flex items-center gap-2 font-semibold tracking-tight">
      <LogoMark />
      <span>
        Insight<span className="text-lime">Forge</span>
      </span>
    </span>
  );
}
