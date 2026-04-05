import { useCallback, useEffect, useRef, useState } from 'react'
import { TLPage, TLPageId } from 'tldraw'
import { TldrawAgentApp } from '../agent/TldrawAgentApp'

const API_BASE = '/api/context/temporary'

interface ContextFile {
  name: string
  size: number
  mime: string
  is_image: boolean
  modified: number
}

interface ContextSidebarProps {
  sidebarOpen: boolean
  onSidebarOpenChange: (open: boolean) => void
  /** The TldrawAgentApp — null while the editor is still mounting. */
  app: TldrawAgentApp | null
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Encode a tldraw page ID safely for use in URL path segments. */
function encodePageId(id: string) {
  return encodeURIComponent(id)
}

export function ContextSidebar({ sidebarOpen: open, onSidebarOpenChange: setOpen, app }: ContextSidebarProps) {
  // Live list of tldraw pages (synced from editor store)
  const [pages, setPages] = useState<TLPage[]>([])
  const [activePageId, setActivePageId] = useState<string | null>(null)

  const [files, setFiles] = useState<ContextFile[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── sync pages & active page from editor ────────────────────────────────
  useEffect(() => {
    if (!app) return
    const editor = app.editor

    const sync = () => {
      setPages(editor.getPages())
      setActivePageId(editor.getCurrentPageId())
    }

    sync() // initial

    // Listen for any store changes (page create/rename/delete/switch)
    const unsub = editor.store.listen(() => sync(), { scope: 'all' })
    return unsub
  }, [app])

  // ── fetch files for active page ──────────────────────────────────────────
  const fetchFiles = useCallback(async (pageId: string) => {
    try {
      const res = await fetch(`${API_BASE}/boards/${encodePageId(pageId)}/files`)
      if (!res.ok) { setFiles([]); return }
      const data = await res.json()
      setFiles(data.files ?? [])
    } catch {
      setFiles([])
    }
  }, [])

  // ── ensure backend folder exists for this page, then load files ───────────
  useEffect(() => {
    if (!activePageId) { setFiles([]); return }
    // Create the folder if it doesn't exist yet, then load files.
    fetch(`${API_BASE}/boards`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ board_id: activePageId }),
    })
      .catch(() => { })
      .finally(() => fetchFiles(activePageId))
  }, [activePageId, fetchFiles])

  // ── navigate tldraw to a page ────────────────────────────────────────────
  const goToPage = useCallback((pageId: string) => {
    app?.editor.setCurrentPage(pageId as TLPageId)
  }, [app])

  // ── upload ────────────────────────────────────────────────────────────────
  const uploadFile = useCallback(
    async (file: File) => {
      if (!activePageId) return
      setUploading(true)
      const fd = new FormData()
      fd.append('file', file)
      try {
        const res = await fetch(
          `${API_BASE}/boards/${encodePageId(activePageId)}/files`,
          { method: 'POST', body: fd }
        )
        if (res.ok) await fetchFiles(activePageId)
        else {
          const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
          alert(err.detail ?? 'Upload failed')
        }
      } catch {
        alert('Upload failed')
      } finally {
        setUploading(false)
      }
    },
    [activePageId, fetchFiles]
  )

  // ── delete file ───────────────────────────────────────────────────────────
  const deleteFile = useCallback(
    async (name: string) => {
      if (!activePageId) return
      setLoading(true)
      try {
        await fetch(
          `${API_BASE}/boards/${encodePageId(activePageId)}/files/${encodeURIComponent(name)}`,
          { method: 'DELETE' }
        )
        await fetchFiles(activePageId)
      } finally {
        setLoading(false)
      }
    },
    [activePageId, fetchFiles]
  )

  // ── clear all files in page folder ───────────────────────────────────────
  const clearFiles = useCallback(async () => {
    if (!activePageId || !confirm('Clear all files for this page?')) return
    setLoading(true)
    try {
      await fetch(
        `${API_BASE}/boards/${encodePageId(activePageId)}/files`,
        { method: 'DELETE' }
      )
      await fetchFiles(activePageId)
    } finally {
      setLoading(false)
    }
  }, [activePageId, fetchFiles])

  // ── drag & drop ───────────────────────────────────────────────────────────
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      if (!activePageId) return
      Array.from(e.dataTransfer.files).forEach(uploadFile)
    },
    [activePageId, uploadFile]
  )

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      Array.from(e.target.files ?? []).forEach(uploadFile)
      e.target.value = ''
    },
    [uploadFile]
  )

  const activePage = pages.find((p) => p.id === activePageId)

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <>
      {/* Collapsed toggle */}
      {!open && (
        <button
          className="context-sidebar-toggle"
          onClick={() => setOpen(true)}
          title="Open context sidebar"
          id="context-sidebar-open-btn"
        >
          <span className="context-sidebar-toggle-icon">📎</span>
          <span className="context-sidebar-toggle-label">Context</span>
        </button>
      )}

      {open && (
        <div
          className={`context-sidebar${dragOver ? ' context-sidebar--drag' : ''}`}
          onDragOver={(e) => { e.preventDefault(); if (activePageId) setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          id="context-sidebar"
        >
          {/* Header */}
          <div className="context-sidebar-header">
            <div className="context-sidebar-title">
              <span className="context-sidebar-icon">📎</span>
              <span>Context</span>
            </div>
            <button
              className="context-sidebar-close-btn"
              onClick={() => setOpen(false)}
              title="Collapse sidebar"
              id="context-sidebar-close-btn"
            >
              ✕
            </button>
          </div>

          {/* Page tabs — mirrors the tldraw pages */}
          <div className="context-page-tabs" id="context-page-tabs">
            <div className="context-page-tab-list">
              {pages.map((page) => (
                <button
                  key={page.id}
                  className={`context-page-tab${activePageId === page.id ? ' context-page-tab--active' : ''}`}
                  onClick={() => goToPage(page.id)}
                  id={`context-tab-${page.id}`}
                  title={`Switch to ${page.name}`}
                >
                  <span className="context-page-tab-label">{page.name}</span>
                </button>
              ))}
            </div>
          </div>

          {activePageId && activePage ? (
            <>
              {/* Page actions row */}
              <div className="context-page-actions">
                <span className="context-page-active-label">{activePage.name}</span>
                {files.length > 0 && (
                  <button
                    className="context-sidebar-clear-btn"
                    onClick={clearFiles}
                    disabled={loading}
                    id="context-clear-all-btn"
                  >
                    Clear files
                  </button>
                )}
              </div>

              {/* Drop zone */}
              <div
                className="context-sidebar-dropzone"
                onClick={() => fileInputRef.current?.click()}
                id="context-sidebar-dropzone"
              >
                {uploading ? (
                  <span className="context-sidebar-dropzone-uploading">Uploading…</span>
                ) : (
                  <>
                    <span className="context-sidebar-dropzone-icon">⬆</span>
                    <span className="context-sidebar-dropzone-text">
                      Drop files here or <u>browse</u>
                    </span>
                    <span className="context-sidebar-dropzone-hint">
                      Images (PNG, JPG, WebP) · Text (TXT, MD, PDF)
                    </span>
                  </>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".png,.jpg,.jpeg,.webp,.gif,.bmp,.txt,.md,.pdf"
                style={{ display: 'none' }}
                onChange={onFileChange}
                id="context-sidebar-file-input"
              />

              {/* File list */}
              <div className="context-sidebar-files" id="context-sidebar-files">
                {files.length === 0 ? (
                  <div className="context-sidebar-empty">
                    No files for <em>{activePage.name}</em>
                  </div>
                ) : (
                  files.map((f) => (
                    <div className="context-sidebar-file" key={f.name} id={`context-file-${f.name}`}>
                      {f.is_image ? (
                        <img
                          className="context-sidebar-file-thumb"
                          src={`${API_BASE}/boards/${encodePageId(activePageId)}/files/${encodeURIComponent(f.name)}`}
                          alt={f.name}
                          loading="lazy"
                        />
                      ) : (
                        <div className="context-sidebar-file-icon">
                          {f.name.endsWith('.pdf') ? '📄' : '📝'}
                        </div>
                      )}
                      <div className="context-sidebar-file-info">
                        <span className="context-sidebar-file-name" title={f.name}>
                          {f.name}
                        </span>
                        <span className="context-sidebar-file-size">{formatBytes(f.size)}</span>
                      </div>
                      <button
                        className="context-sidebar-file-delete"
                        onClick={() => deleteFile(f.name)}
                        disabled={loading}
                        title={`Remove ${f.name}`}
                        id={`context-file-delete-${f.name}`}
                      >
                        ×
                      </button>
                    </div>
                  ))
                )}
              </div>
            </>
          ) : (
            <div className="context-sidebar-empty" style={{ padding: '24px 16px', textAlign: 'center' }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>📂</div>
              <div>{app ? 'Loading pages…' : 'Waiting for editor…'}</div>
            </div>
          )}

          {/* Drag overlay */}
          {dragOver && (
            <div className="context-sidebar-drag-overlay">Drop to upload</div>
          )}
        </div>
      )}
    </>
  )
}
