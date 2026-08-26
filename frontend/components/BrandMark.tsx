type BrandMarkProps = {
  className?: string;
};

export default function BrandMark({ className = "" }: BrandMarkProps) {
  const classes = ["brand-mark", className].filter(Boolean).join(" ");

  return (
    <span className={classes} aria-hidden="true">
      <svg viewBox="0 0 64 64" focusable="false">
        <rect className="brand-mark-surface" x="2" y="2" width="60" height="60" rx="15" />
        <path className="brand-mark-wave" d="M13 33h7l4-14 8 27 7-23 5 10h7" />
      </svg>
    </span>
  );
}
