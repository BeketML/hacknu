import { useCallback, useEffect, useRef, useState } from 'react'
import { useValue } from 'tldraw'
import { useAgent } from '../agent/TldrawAgentAppProvider'

// ─── Hook ───────────────────────────────────────────────────────────────────

/**
 * Watches for user-driven canvas changes (shapes added / updated / deleted).
 * After a quiet period it grabs a viewport screenshot and sends the prompt
 * to the existing agent — no new agent created.
 *
 * This is intentionally NOT exported so the file only exports React components,
 * keeping Vite Fast Refresh happy.
 */
function useAutoSuggest(enabled: boolean) {
  const agent = useAgent()
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!enabled) return

    // Listen to store changes; filter out agent-driven changes
    const cleanup = agent.editor.store.listen(
      (_diff) => {
        // Skip changes that are caused by the agent itself
        if (agent.getIsActingOnEditor()) return

        // Debounce: wait 2.5 s of silence before prompting
        if (debounceRef.current) clearTimeout(debounceRef.current)
        debounceRef.current = setTimeout(async () => {
          // Don't interrupt if agent is already generating
          if (agent.requests.isGenerating()) return

          // Capture viewport as a screenshot using tldraw's built-in getSvgString
          // then convert to a data URL so we can pass it as context image.
          // We piggy-back on the viewport bounds for context.
          const bounds = agent.editor.getViewportPageBounds()

          agent.interrupt({
            input: {
              agentMessages: ['What would you suggest here? If i have some mistakes correct them, if there are gaps or certainly missing parts, add them. Dont think too much, do actions'],
              bounds,
              source: 'user',
              contextItems: agent.context.getItems(),
            },
          })
        }, 2500)
      },
      // Only listen to changes that originate from the local user
      { source: 'user', scope: 'document' }
    )

    return () => {
      cleanup()
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [enabled, agent])
}

// ─── Toggle Component ────────────────────────────────────────────────────────

interface AutoSuggestToggleProps {
  enabled: boolean
  onToggle: () => void
}

export function AutoSuggestToggle({ enabled, onToggle }: AutoSuggestToggleProps) {
  const agent = useAgent()
  const isGenerating = useValue('isGenerating', () => agent.requests.isGenerating(), [agent])

  return (
    <button
      id="auto-suggest-toggle"
      className={`auto-suggest-toggle ${enabled ? 'auto-suggest-toggle--on' : ''}`}
      onClick={onToggle}
      title={
        enabled
          ? 'Auto-Suggest is ON — agent watches your canvas and suggests changes'
          : 'Auto-Suggest is OFF — click to enable'
      }
      aria-pressed={enabled}
    >
      {/* Spark icon */}
      <svg
        className="auto-suggest-icon"
        width="11"
        height="11"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M13 2L4.09 12.97H11L10 22L20.5 9.97H14L13 2Z"
          fill="currentColor"
        />
      </svg>

      <span className="auto-suggest-label">Auto-Suggest</span>

      {/* The actual toggle track + thumb */}
      <span className={`auto-suggest-track ${enabled ? 'auto-suggest-track--on' : ''}`}>
        <span
          className={`auto-suggest-thumb ${enabled ? 'auto-suggest-thumb--on' : ''}`}
        />
      </span>

      {/* Pulse dot when active + generating */}
      {enabled && isGenerating && <span className="auto-suggest-pulse" />}
    </button>
  )
}

// ─── Container ───────────────────────────────────────────────────────────────

/**
 * Drop-in: renders the toggle and wires up the auto-suggest behaviour.
 * Import this in ChatPanel.
 */
export function AutoSuggestContainer() {
  const [enabled, setEnabled] = useState(false)

  const handleToggle = useCallback(() => setEnabled((v) => !v), [])

  // Start/stop watching the canvas
  useAutoSuggest(enabled)

  return <AutoSuggestToggle enabled={enabled} onToggle={handleToggle} />
}
