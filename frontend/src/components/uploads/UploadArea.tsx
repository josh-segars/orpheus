import { useId, useRef, useState, type ChangeEvent, type DragEvent } from 'react'

interface UploadAreaProps {
  /** Label rendered above the drop zone (e.g. "Upload your data archive"). */
  label: string
  /** Primary CTA inside the drop zone (e.g. "Drop your file here or browse"). */
  primary: string
  /** Secondary instruction below primary. */
  secondary: string
  /** Tag in the bottom-right (e.g. "ZIP file" / "XLSX file"). */
  fileTypeLabel: string
  /** HTML accept attribute for the underlying input (e.g. ".zip,application/zip"). */
  accept: string
  /** Currently selected file, or null if none. */
  file: File | null
  /** Called when the user picks or drops a file (or clears it). */
  onFileChange: (file: File | null) => void
}

/**
 * Drop zone + file picker. Mirrors the prototype's `.upload-section` markup
 * exactly (same classes), with a controlled file input layered on top. The
 * native input is visually hidden — clicks anywhere on the drop zone
 * forward to it via a ref, and drag/drop is handled directly.
 *
 * State machine: empty → picked → (replaceable). The component never owns
 * the File — it's lifted into the LinkedInUploadContext by the page.
 */
export function UploadArea({
  label,
  primary,
  secondary,
  fileTypeLabel,
  accept,
  file,
  onFileChange,
}: UploadAreaProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const inputId = useId()
  const [isDragging, setIsDragging] = useState(false)

  const handleClick = () => {
    inputRef.current?.click()
  }

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const next = e.target.files?.[0] ?? null
    onFileChange(next)
    // Reset the input value so picking the same file twice still fires
    // onChange — useful if the user replaces the same path after editing.
    e.target.value = ''
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }
  const handleDragLeave = () => setIsDragging(false)
  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const dropped = e.dataTransfer.files?.[0]
    if (dropped) onFileChange(dropped)
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onFileChange(null)
  }

  return (
    <div className="upload-section">
      <label htmlFor={inputId} className="upload-label">
        {label}
      </label>
      <div
        className={
          isDragging ? 'upload-area upload-area-dragging' : 'upload-area'
        }
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            handleClick()
          }
        }}
      >
        <input
          id={inputId}
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          style={{ position: 'absolute', width: 0, height: 0, opacity: 0 }}
        />

        <div className="upload-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </div>
        {file ? (
          <>
            <p className="upload-primary">{file.name}</p>
            <p className="upload-secondary">
              {formatBytes(file.size)} &middot;{' '}
              <button
                type="button"
                className="upload-clear"
                onClick={handleClear}
              >
                Replace
              </button>
            </p>
          </>
        ) : (
          <>
            <p className="upload-primary">{primary}</p>
            <p className="upload-secondary">{secondary}</p>
          </>
        )}
        <p className="upload-file-type">{fileTypeLabel}</p>
      </div>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
