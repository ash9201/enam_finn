import type { ButtonHTMLAttributes } from 'react'
import './evidence-button.css'

export type EvidenceCitation = { document_label: string; pdf_page: number }

export default function EvidenceButton({
  citation,
  children = 'View evidence',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { citation?: EvidenceCitation }) {
  return (
    <button
      type="button"
      aria-haspopup="dialog"
      title="Open evidence panel"
      {...props}
      className={`citation-button evidence-button ${className}`}
    >
      <svg
        width="15"
        height="15"
        viewBox="0 0 20 20"
        fill="none"
        aria-hidden="true"
        focusable="false"
      >
        <rect x="2.5" y="3" width="15" height="14" rx="2" stroke="currentColor" strokeWidth="1.4" />
        <path
          d="M12 3v14M5.5 7h3M5.5 10h3"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
      </svg>
      <span>
        {children}
        {citation && (
          <>
            {' '}
            · {citation.document_label} · p. {citation.pdf_page}
          </>
        )}
      </span>
    </button>
  )
}
