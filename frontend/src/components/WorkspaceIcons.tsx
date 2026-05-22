type IconProps = { className?: string };

export function IconMenu({ className }: IconProps) {
  return (
    <svg className={className} width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function IconSendUp({ className }: IconProps) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 19V6m0 0l-5 5m5-5 5 5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconStopSquare({ className }: IconProps) {
  return (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

export function IconEqualizer({ className }: IconProps) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="4" y="10" width="3" height="10" rx="1" fill="currentColor" className="eq-bar eq-bar-1" />
      <rect x="10.5" y="6" width="3" height="14" rx="1" fill="currentColor" className="eq-bar eq-bar-2" />
      <rect x="17" y="3" width="3" height="17" rx="1" fill="currentColor" className="eq-bar eq-bar-3" />
    </svg>
  );
}

export function IconTextCursor({ className }: IconProps) {
  return (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M9 5v14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path
        d="M13 9h5M13 12h4M13 15h5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.7"
      />
      <rect className="cursor-blink" x="7" y="8" width="2" height="10" fill="currentColor" />
    </svg>
  );
}

export function IconChevron({ className, open }: IconProps & { open?: boolean }) {
  return (
    <svg
      className={className}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
      style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.55s ease" }}
    >
      <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
