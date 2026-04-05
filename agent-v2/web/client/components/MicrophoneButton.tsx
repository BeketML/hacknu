import { useCallback, useEffect, useRef, useState } from 'react'
import { useAgent } from '../agent/TldrawAgentAppProvider'

// ── Agent definitions ────────────────────────────────────────────────────────
// Each agent has a display name, color accent, wake words (in Russian & Latin),
// and a personality prompt injected into every request they handle.

interface AgentDef {
  code: string          // internal code / display label
  displayName: string
  emoji: string
  color: string         // hsl for accent
  wakeWords: string[]   // lowercase variants the STT engine might produce
  personality: string   // system-level personality injected as context
}

const AGENTS: AgentDef[] = [
  {
    code: 'Beket',
    displayName: 'Провокатор-Трендсеттер',
    emoji: '🔥',
    color: 'hsl(25, 95%, 55%)',
    wakeWords: ['бекет', 'beket', 'бекет,', 'beket,', 'беккет'],
    personality: `[PERSONA: Beket — Провокатор-Трендсеттер]
Ты — Beket, дерзкий и харизматичный агент контента. Ты живёшь в интернете, мыслишь мемами и всегда знаешь, что будет трендовым завтра. Ты ироничен, слегка циничен, но невероятно обаятелен.

Принципы:
- Короткие, хлёсткие предложения. Много сленга и отсылок к поп-культуре.
- Постирония, абсурдный юмор, шитпостинг — это твои инструменты.
- Кликбейт, но изящный. Шок-контент, разрыв шаблона, ощущение эксклюзивности.
- Поляризуй аудиторию — пусть спорят в комментариях.
- Идеален для: молодёжных брендов, уличной одежды, крипто, вирусных кампаний.

Создавай контент именно в этом духе: дерзко, трендово, непредсказуемо.`,
  },
  {
    code: 'Bauyrzhan',
    displayName: 'Эмпатичный Рассказчик',
    emoji: '💛',
    color: 'hsl(45, 90%, 55%)',
    wakeWords: ['бауржан', 'bauyrzhan', 'бауыржан,', 'bauyrzhan,'],
    personality: `[PERSONA: Баука — Эмпатичный Рассказчик]
Ты — Баука, тёплый и мудрый агент контента. Ты видишь за каждым продуктом человеческую историю. Твоя цель — не продать в лоб, а выстроить глубокую эмоциональную связь с читателем.

Принципы:
- Сторителлинг: плавные, обволакивающие тексты с акцентом на ощущения, цвета и запахи.
- Риторические вопросы, обращение к аудитории как к старым друзьям.
- Минимум агрессивных CTA — максимум заботы и тепла.
- Триггеры: безопасность, уют, ностальгия, принадлежность к сообществу.
- Идеален для: лайфстайл-брендов, косметики, эко-продуктов, HR-брендинга.

Создавай контент именно в этом духе: тепло, искренне, с душой.`,
  },
  {
    code: 'Adik',
    displayName: 'Цифровой Прагматик',
    emoji: '📊',
    color: 'hsl(214, 84%, 55%)',
    wakeWords: ['адик', 'adik', 'адик,', 'adik,'],
    personality: `[PERSONA: Адик — Цифровой Прагматик]
Ты — Адик, холодный и структурный агент контента, ориентированный исключительно на ROI и факты. Ты презираешь «воду», абстрактные обещания и лишние эмоции. Для тебя контент — это уравнение, которое должно привести к конверсии.

Принципы:
- Максимально лаконично и экспертно. Статистика, графики, проценты, кейсы.
- Чёткая структура: Проблема → Решение → Выгода → Действие.
- Профессиональная терминология, но без занудства.
- Триггеры: экономия времени/денег, статус эксперта, надёжность, гарантии.
- Идеален для: B2B, SaaS, финтех, сложное оборудование, консалтинг.

Создавай контент именно в этом духе: чётко, структурно, с акцентом на результат.`,
  },
  {
    code: 'Dilnaz',
    displayName: 'Неутомимый Хайпбист',
    emoji: '🚀',
    color: 'hsl(330, 90%, 60%)',
    wakeWords: ['дильназ', 'dilnaz', 'дильназ,', 'dilnaz,'],
    personality: `[PERSONA: Дильназ — Неутомимый Хайпбист]
Ты — Дильназ, энергичный и громкий агент контента. Ты всегда на позитиве и лёгкой панике из-за того, что «акция скоро закончится!». Ты создаёшь вокруг продукта атмосферу грандиозного праздника и искусственный дефицит.

Принципы:
- Высокий темп чтения, обилие эмодзи (🔥🚀⚡), КАПС для выделения главного.
- «Только сейчас», «Взрыв», «Успей», «Осталось 3 штуки».
- Пуши аудиторию к НЕМЕДЛЕННОМУ действию.
- Триггеры: FOMO (страх упущенной выгоды), жадность, соцдоказательство.
- Идеален для: Black Friday, FMCG, анонсов мероприятий, розыгрышей, фастфуда, мобильных игр.

Создавай контент именно в этом духе: громко, энергично, срочно, с огнём!`,
  },
  {
    code: 'Salta',
    displayName: 'Минималист-Эстет',
    emoji: '⬛',
    color: 'hsl(0, 0%, 75%)',
    wakeWords: ['салта', 'salta', 'салта,', 'salta,'],
    personality: `[PERSONA: Салта — Минималист-Эстет]
Ты — Салта, спокойный и премиальный агент контента. Хороший продукт говорит сам за себя. Ты создаёшь вокруг бренда ауру элитарности и недоступности.

Принципы:
- Много «воздуха» в тексте. Одно-два предложения на весь пост.
- Сложные метафоры, идеальная пунктуация. Никаких эмодзи (или максимум ⬛).
- Текст лишь изящно дополняет визуальную составляющую.
- Триггеры: уникальность, высокий статус, перфекционизм.
- Идеален для: люксовых авто, дорогих часов, нишевой парфюмерии, архитектуры, дизайна.

Создавай контент именно в этом духе: тихо, элегантно, безупречно.`,
  },
]

// Build flat wake-word → agent map for O(1) lookup
const WAKE_WORD_MAP = new Map<string, AgentDef>()
for (const agentDef of AGENTS) {
  for (const ww of agentDef.wakeWords) {
    WAKE_WORD_MAP.set(ww, agentDef)
  }
}

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

/** Returns the matched {agent, wakeWordIndex} for the given word array, or null */
function detectWakeWord(words: string[]): { agentDef: AgentDef; wakeWordIndex: number } | null {
  for (let i = 0; i < words.length; i++) {
    const word = words[i]
    // Try exact match first, then prefix match (for punctuation variants)
    let matched = WAKE_WORD_MAP.get(word)
    if (!matched) {
      for (const [ww, def] of WAKE_WORD_MAP) {
        if (word.startsWith(ww.replace(/,$/, ''))) {
          matched = def
          break
        }
      }
    }
    if (matched) return { agentDef: matched, wakeWordIndex: i }
  }
  return null
}

export function MicrophoneButton() {
  const agent = useAgent()
  const [micState, setMicState] = useState<MicState>('idle')
  const [currentLine, setCurrentLine] = useState('')
  const [activeAgent, setActiveAgent] = useState<AgentDef | null>(null)
  const [wakeWordDetected, setWakeWordDetected] = useState(false)

  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const isListeningRef = useRef(false)
  const fullTranscriptRef = useRef<string[]>([])

  useEffect(() => {
    if (!getSpeechRecognitionClass()) setMicState('unsupported')
  }, [])

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.abort()
      recognitionRef.current = null
    }
    isListeningRef.current = false
    fullTranscriptRef.current = []
    setCurrentLine('')
    setActiveAgent(null)
    setWakeWordDetected(false)
    setMicState('idle')
  }, [])

  const startListening = useCallback(() => {
    const SpeechRecognitionClass = getSpeechRecognitionClass()
    if (!SpeechRecognitionClass) {
      setMicState('unsupported')
      return
    }

    fullTranscriptRef.current = []

    const recognition = new SpeechRecognitionClass()
    recognition.lang = 'ru-RU'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 3

    let isTriggered = false

    const resetTrigger = () => {
      isTriggered = false
      setWakeWordDetected(false)
      setActiveAgent(null)
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

      const displayLine = finalTranscript.trim() || interimTranscript.trim()
      setCurrentLine(displayLine)

      if (finalTranscript.trim()) {
        fullTranscriptRef.current.push(finalTranscript.trim())
      }

      // ── Wake-word detection (any of the 5 agents) ────────────────────────
      const checkText = (finalTranscript + interimTranscript).toLowerCase().trim()
      const words = checkText.split(/\s+/)
      const match = detectWakeWord(words)

      if (!match) return // no wake word — keep transcribing

      const { agentDef, wakeWordIndex } = match

      // Visual feedback immediately
      setActiveAgent(agentDef)
      setWakeWordDetected(true)
      setMicState('triggered')

      // Wait for final result (prevents firing on every interim partial)
      if (finalTranscript.trim().length === 0) return

      isTriggered = true

      const commandWords = words.slice(wakeWordIndex + 1)
      const command = commandWords.join(' ').trim()

      // Nothing after the wake word — don't fire
      if (!command) {
        isTriggered = false
        setWakeWordDetected(false)
        setActiveAgent(null)
        setMicState('listening')
        return
      }

      // Build conversation context (prior sentences + pre-wake words in current sentence)
      const priorSentences = fullTranscriptRef.current.slice(0, -1)
      const preWakeWords = words.slice(0, wakeWordIndex).join(' ').trim()
      const contextParts: string[] = [...priorSentences]
      if (preWakeWords) contextParts.push(preWakeWords)

      const transcriptContext =
        contextParts.length > 0
          ? `[Контекст разговора]\n${contextParts.join('\n')}\n\n`
          : ''

      // Inject chosen agent's personality + context + command
      const agentMessage =
        `${agentDef.personality}\n\n` +
        (transcriptContext ? `${transcriptContext}[Команда] ${command}` : command)

      agent.interrupt({
        input: {
          agentMessages: [agentMessage],
          bounds: agent.editor.getViewportPageBounds(),
          source: 'user',
          contextItems: agent.context.getItems(),
        },
      })

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
      if (isListeningRef.current) {
        try { recognition.start() } catch { /* already starting */ }
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

  useEffect(() => {
    return () => { if (recognitionRef.current) recognitionRef.current.abort() }
  }, [])

  const isActive = micState === 'listening' || micState === 'triggered'

  let title = 'Включить голосовые команды (скажи имя агента: Адик, Beket, Баука, Дильназ, Салта)'
  if (micState === 'listening') {
    const names = AGENTS.map(a => a.code).join(', ')
    title = `Слушаю… Скажи [${names}] + команда. Нажми чтобы остановить.`
  }
  if (micState === 'triggered') title = `Агент ${activeAgent?.displayName ?? ''} — выполняю команду…`
  if (micState === 'error') title = 'Нет доступа к микрофону. Нажми для повторной попытки.'
  if (micState === 'unsupported') title = 'Голосовое управление не поддерживается.'

  const accentColor = activeAgent?.color ?? (micState === 'listening' ? 'hsl(214, 84%, 55%)' : undefined)

  return (
    <div className="mic-button-wrapper" title={title}>
      <button
        id="mic-button"
        className={`mic-button mic-button--${micState}`}
        style={accentColor ? ({
          '--mic-accent': accentColor,
        } as React.CSSProperties) : undefined}
        onClick={handleToggle}
        disabled={micState === 'unsupported'}
        aria-label={isActive ? 'Остановить прослушивание' : 'Начать голосовое управление'}
        aria-pressed={isActive}
      >
        {isActive && (
          <>
            <span className="mic-pulse-ring mic-pulse-ring--1" />
            <span className="mic-pulse-ring mic-pulse-ring--2" />
          </>
        )}
        <span className="mic-icon">
          {micState === 'unsupported' ? <MicOffIcon /> :
            micState === 'error' ? <MicErrorIcon /> :
              isActive ? <MicActiveIcon triggered={micState === 'triggered'} /> :
                <MicIcon />}
        </span>
      </button>

      {/* Agent chip — shows which agent is active */}
      {isActive && activeAgent && (
        <div
          className="mic-agent-chip"
          style={{ borderColor: activeAgent.color, color: activeAgent.color }}
        >
          <span>{activeAgent.emoji}</span>
          <span>{activeAgent.code}</span>
        </div>
      )}

      {/* Transcript bubble */}
      {isActive && (
        <div
          className={`mic-transcript ${wakeWordDetected ? 'mic-transcript--triggered' : ''}`}
          style={wakeWordDetected && activeAgent ? { borderColor: activeAgent.color } : undefined}
        >
          {currentLine ? (
            <span className="mic-transcript-text">{currentLine}</span>
          ) : (
            <span className="mic-transcript-placeholder">
              {micState === 'triggered' ? `${activeAgent?.emoji ?? ''}  Выполняю…` : 'Слушаю…'}
            </span>
          )}
        </div>
      )}

      {/* Status dot */}
      {isActive && <span className={`mic-status-dot mic-status-dot--${micState}`}
        style={activeAgent ? { background: activeAgent.color, animation: 'none' } : undefined}
      />}
    </div>
  )
}

function MicIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z" fill="currentColor" />
      <path d="M19 10V12C19 15.87 15.87 19 12 19C8.13 19 5 15.87 5 12V10H3V12C3 16.72 6.54 20.65 11 21.84V23H9V25H15V23H13V21.84C17.46 20.65 21 16.72 21 12V10H19Z" fill="currentColor" />
    </svg>
  )
}

function MicActiveIcon({ triggered }: { triggered: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z" fill={triggered ? 'var(--mic-accent, #22d3ee)' : 'currentColor'} />
      <path d="M19 10V12C19 15.87 15.87 19 12 19C8.13 19 5 15.87 5 12V10H3V12C3 16.72 6.54 20.65 11 21.84V23H9V25H15V23H13V21.84C17.46 20.65 21 16.72 21 12V10H19Z" fill={triggered ? 'var(--mic-accent, #22d3ee)' : 'currentColor'} />
    </svg>
  )
}

function MicOffIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M19 11C19 12.19 18.66 13.3 18.1 14.28L16.87 13.05C17.14 12.43 17.3 11.74 17.3 11H19ZM15 11.16L9 5.18V4C9 2.34 10.34 1 12 1C13.66 1 15 2.34 15 4L15 11.16ZM4.27 3L3 4.27L9.01 10.28C9 10.51 9 10.75 9 11V13C9 14.66 10.34 16 12 16C12.22 16 12.44 15.97 12.65 15.92L14.31 17.58C13.6 17.85 12.82 18 12 18C8.13 18 5 14.87 5 11H3C3 15.72 6.54 19.65 11 20.84V23H9V25H15V23H13V20.84C14.07 20.57 15.07 20.09 15.95 19.45L19.73 23.23L21 21.96L4.27 3Z" fill="currentColor" opacity="0.5" />
    </svg>
  )
}

function MicErrorIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 1C10.34 1 9 2.34 9 4V12C9 13.66 10.34 15 12 15C13.66 15 15 13.66 15 12V4C15 2.34 13.66 1 12 1Z" fill="#ef4444" />
      <path d="M19 10V12C19 15.87 15.87 19 12 19C8.13 19 5 15.87 5 12V10H3V12C3 16.72 6.54 20.65 11 21.84V23H9V25H15V23H13V21.84C17.46 20.65 21 16.72 21 12V10H19Z" fill="#ef4444" />
    </svg>
  )
}
