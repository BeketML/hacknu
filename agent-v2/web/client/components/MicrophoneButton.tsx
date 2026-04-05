import { useCallback, useEffect, useRef, useState } from 'react'
import { useAgent } from '../agent/TldrawAgentAppProvider'

// Wake words that trigger the agent (case insensitive, supports Russian/Kazakh variants)
const WAKE_WORDS = ['адик', 'adik', 'адик,', 'adik,']

// The browser's SpeechRecognition API types
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList
  resultIndex: number
}
interface SpeechRecognitionErrorEvent extends Event {
  error: string
}
interface SpeechRecognition extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start(): void
  stop(): void
  abort(): void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
}
declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition
    webkitSpeechRecognition: new () => SpeechRecognition
  }
}

type MicState = 'idle' | 'listening' | 'triggered' | 'error' | 'unsupported'

function getSpeechRecognitionClass(): (new () => SpeechRecognition) | null {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

export function MicrophoneButton() {
  const agent = useAgent()
  const [micState, setMicState] = useState<MicState>('idle')
  // Current line being spoken (interim + latest final)
  const [currentLine, setCurrentLine] = useState('')
  // Whether wake word was just detected (for visual flash)
  const [wakeWordDetected, setWakeWordDetected] = useState(false)

  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const isListeningRef = useRef(false)

  // Accumulates ALL finalized sentences since mic was activated
  const fullTranscriptRef = useRef<string[]>([])

  // Check if browser supports Web Speech API
  useEffect(() => {
    if (!getSpeechRecognitionClass()) {
      setMicState('unsupported')
    }
  }, [])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.abort()
      recognitionRef.current = null
    }
    isListeningRef.current = false
    fullTranscriptRef.current = []
    setCurrentLine('')
    setWakeWordDetected(false)
    setMicState('idle')
  }, [])

  const startListening = useCallback(() => {
    const SpeechRecognitionClass = getSpeechRecognitionClass()
    if (!SpeechRecognitionClass) {
      setMicState('unsupported')
      return
    }

    // Reset accumulated transcript for this session
    fullTranscriptRef.current = []

    const recognition = new SpeechRecognitionClass()
    recognition.lang = 'ru-RU'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 3

    // ONE-SHOT lock: prevents re-triggering while a trigger is in-flight
    let isTriggered = false

    const resetTrigger = () => {
      isTriggered = false
      setWakeWordDetected(false)
      setMicState('listening')
      setCurrentLine('')
    }

    recognition.onstart = () => {
      setMicState('listening')
      isListeningRef.current = true
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      if (isTriggered) return

      let interimTranscript = ''
      let finalTranscript = ''

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        const text = result[0].transcript
        if (result.isFinal) {
          finalTranscript += text + ' '
        } else {
          interimTranscript += text
        }
      }

      // Show current interim line in the transcript bubble
      const displayLine = finalTranscript.trim() || interimTranscript.trim()
      setCurrentLine(displayLine)

      // Commit finalized text into the running buffer
      if (finalTranscript.trim()) {
        fullTranscriptRef.current.push(finalTranscript.trim())
      }

      // ── Wake-word detection ──────────────────────────────────────────────
      const checkText = (finalTranscript + interimTranscript).toLowerCase().trim()
      const words = checkText.split(/\s+/)
      const wakeWordIndex = words.findIndex((word) =>
        WAKE_WORDS.some((ww) => word.startsWith(ww))
      )

      if (wakeWordIndex === -1) return // no wake word — keep transcribing

      // Show triggered visual immediately
      setWakeWordDetected(true)
      setMicState('triggered')

      // Only dispatch once we have a FINAL result (complete sentence)
      // This prevents firing on every interim partial word update
      if (finalTranscript.trim().length === 0) return

      // Lock so no further callbacks fire another request
      isTriggered = true

      // Command = everything after the wake word in this sentence
      const commandWords = words.slice(wakeWordIndex + 1)
      const command = commandWords.join(' ').trim()

      // If nothing was said after "Адик", don't fire — reset and keep listening
      if (!command) {
        isTriggered = false
        setWakeWordDetected(false)
        setMicState('listening')
        return
      }

      // Build full context from two sources:
      // 1. All finalized sentences from BEFORE the trigger sentence
      // 2. Words spoken in the SAME sentence BEFORE the wake word
      //    (handles the case where user speaks everything in one breath:
      //     "обсуждали постер Адик создай" → "обсуждали постер" is pre-wake context)
      const priorSentences = fullTranscriptRef.current.slice(0, -1) // exclude trigger sentence
      const preWakeWords = words.slice(0, wakeWordIndex).join(' ').trim()

      const contextParts: string[] = [...priorSentences]
      if (preWakeWords) contextParts.push(preWakeWords)

      const transcriptContext =
        contextParts.length > 0
          ? `[Контекст разговора]\n${contextParts.join('\n')}\n\n`
          : ''

      // Send command directly as prompt, with conversation context prepended if any
      const agentMessage = transcriptContext
        ? `${transcriptContext}[Команда] ${command}`
        : command

      agent.interrupt({
        input: {
          agentMessages: [agentMessage],
          bounds: agent.editor.getViewportPageBounds(),
          source: 'user',
          contextItems: agent.context.getItems(),
        },
      })

      // Reset after cooldown so user can speak another command
      setTimeout(resetTrigger, 1500)
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === 'not-allowed') {
        setMicState('error')
        isListeningRef.current = false
      } else if (event.error !== 'no-speech') {
        console.warn('Speech recognition error:', event.error)
      }
    }

    recognition.onend = () => {
      // Auto-restart to keep continuous listening alive
      if (isListeningRef.current) {
        try {
          recognition.start()
        } catch {
          // Already starting
        }
      }
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch (e) {
      console.error('Failed to start recognition:', e)
      setMicState('error')
    }
  }, [agent])

  const handleToggle = useCallback(() => {
    if (micState === 'unsupported') return
    if (micState === 'idle' || micState === 'error') {
      startListening()
    } else {
      stopListening()
    }
  }, [micState, startListening, stopListening])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort()
      }
    }
  }, [])

  const isActive = micState === 'listening' || micState === 'triggered'

  let title = 'Click to enable voice commands (say "Адик" to trigger)'
  if (micState === 'listening') title = 'Listening… say "Адик [command]" to trigger agent. Click to stop.'
  if (micState === 'triggered') title = 'Wake word detected! Triggering agent…'
  if (micState === 'error') title = 'Microphone access denied. Click to retry.'
  if (micState === 'unsupported') title = 'Voice recognition not supported in this browser'

  // Show last N lines of accumulated transcript in the bubble
  const transcriptPreview = [
    ...fullTranscriptRef.current.slice(-3),
    ...(currentLine && !fullTranscriptRef.current.at(-1)?.startsWith(currentLine.slice(0, 5))
      ? [currentLine]
      : []),
  ]
    .join(' ')
    .trim()

  return (
    <div className="mic-button-wrapper" title={title}>
      <button
        id="mic-button"
        className={`mic-button mic-button--${micState}`}
        onClick={handleToggle}
        disabled={micState === 'unsupported'}
        aria-label={isActive ? 'Stop listening' : 'Start voice recognition'}
        aria-pressed={isActive}
      >
        {/* Pulse rings */}
        {isActive && (
          <>
            <span className="mic-pulse-ring mic-pulse-ring--1" />
            <span className="mic-pulse-ring mic-pulse-ring--2" />
          </>
        )}

        {/* Icon */}
        <span className="mic-icon">
          {micState === 'unsupported' ? (
            <MicOffIcon />
          ) : micState === 'error' ? (
            <MicErrorIcon />
          ) : isActive ? (
            <MicActiveIcon triggered={micState === 'triggered'} />
          ) : (
            <MicIcon />
          )}
        </span>
      </button>

      {/* Floating transcript bubble — shows rolling real-time transcription */}
      {isActive && (
        <div className={`mic-transcript ${wakeWordDetected ? 'mic-transcript--triggered' : ''}`}>
          {transcriptPreview ? (
            <span className="mic-transcript-text">{transcriptPreview}</span>
          ) : (
            <span className="mic-transcript-placeholder">Слушаю…</span>
          )}
        </div>
      )}

      {/* Status indicator dot */}
      {isActive && <span className={`mic-status-dot mic-status-dot--${micState}`} />}
    </div>
  )
}

function MicIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z"
        fill="currentColor"
      />
      <path
        d="M19 10V12C19 15.87 15.87 19 12 19C8.13 19 5 15.87 5 12V10H3V12C3 16.72 6.54 20.65 11 21.84V23H9V25H15V23H13V21.84C17.46 20.65 21 16.72 21 12V10H19Z"
        fill="currentColor"
      />
    </svg>
  )
}

function MicActiveIcon({ triggered }: { triggered: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z"
        fill={triggered ? '#22d3ee' : 'currentColor'}
      />
      <path
        d="M19 10V12C19 15.87 15.87 19 12 19C8.13 19 5 15.87 5 12V10H3V12C3 16.72 6.54 20.65 11 21.84V23H9V25H15V23H13V21.84C17.46 20.65 21 16.72 21 12V10H19Z"
        fill={triggered ? '#22d3ee' : 'currentColor'}
      />
    </svg>
  )
}

function MicOffIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M19 11C19 12.19 18.66 13.3 18.1 14.28L16.87 13.05C17.14 12.43 17.3 11.74 17.3 11H19ZM15 11.16L9 5.18V4C9 2.34 10.34 1 12 1C13.66 1 15 2.34 15 4L15 11.16ZM4.27 3L3 4.27L9.01 10.28C9 10.51 9 10.75 9 11V13C9 14.66 10.34 16 12 16C12.22 16 12.44 15.97 12.65 15.92L14.31 17.58C13.6 17.85 12.82 18 12 18C8.13 18 5 14.87 5 11H3C3 15.72 6.54 19.65 11 20.84V23H9V25H15V23H13V20.84C14.07 20.57 15.07 20.09 15.95 19.45L19.73 23.23L21 21.96L4.27 3Z"
        fill="currentColor"
        opacity="0.5"
      />
    </svg>
  )
}

function MicErrorIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z"
        fill="#ef4444"
      />
      <path
        d="M19 10V12C19 15.87 15.87 19 12 19C8.13 19 5 15.87 5 12V10H3V12C3 16.72 6.54 20.65 11 21.84V23H9V25H15V23H13V21.84C17.46 20.65 21 16.72 21 12V10H19Z"
        fill="#ef4444"
      />
    </svg>
  )
}
