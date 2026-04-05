import { useCallback, useMemo, useRef, useState } from 'react'
import {
	DefaultSizeStyle,
	ErrorBoundary,
	TLComponents,
	Tldraw,
	TldrawOverlays,
	TldrawUiToastsProvider,
	TLUiOverrides,
} from 'tldraw'
import { useSyncDemo } from '@tldraw/sync'
import { TldrawAgentApp } from './agent/TldrawAgentApp'
import {
	TldrawAgentAppContextProvider,
	TldrawAgentAppProvider,
} from './agent/TldrawAgentAppProvider'
import { ChatPanel } from './components/ChatPanel'
import { ChatPanelFallback } from './components/ChatPanelFallback'
import { ContextSidebar } from './components/ContextSidebar'
import { CustomHelperButtons } from './components/CustomHelperButtons'
import { AgentViewportBoundsHighlights } from './components/highlights/AgentViewportBoundsHighlights'
import { AllContextHighlights } from './components/highlights/ContextHighlights'
import { TargetAreaTool } from './tools/TargetAreaTool'
import { TargetShapeTool } from './tools/TargetShapeTool'

// Customize tldraw's styles to play to the agent's strengths
DefaultSizeStyle.setDefaultValue('s')

// Custom tools for picking context items
const tools = [TargetShapeTool, TargetAreaTool]
const overrides: TLUiOverrides = {
	tools: (editor, tools) => {
		return {
			...tools,
			'target-area': {
				id: 'target-area',
				label: 'Pick Area',
				kbd: 'c',
				icon: 'tool-frame',
				onSelect() {
					editor.setCurrentTool('target-area')
				},
			},
			'target-shape': {
				id: 'target-shape',
				label: 'Pick Shape',
				kbd: 's',
				icon: 'tool-frame',
				onSelect() {
					editor.setCurrentTool('target-shape')
				},
			},
		}
	},
}

// --- Collaboration helpers ---

const DEFAULT_ROOM_ID = 'hacknu-agent-v2-default'

function readInitialRoomId(): string {
	const q = new URLSearchParams(window.location.search).get('room')?.trim()
	return q && q.length > 0 ? q : DEFAULT_ROOM_ID
}

// --- CollaborationRoomBar component ---

function CollaborationRoomBar({
	roomId,
	onRoomChange,
}: {
	roomId: string
	onRoomChange: (id: string) => void
}) {
	const [inputValue, setInputValue] = useState(roomId)

	const applyRoomId = useCallback(
		(id: string) => {
			const trimmed = id.trim() || DEFAULT_ROOM_ID
			const url = new URL(window.location.href)
			url.searchParams.set('room', trimmed)
			window.history.replaceState({}, '', url.toString())
			onRoomChange(trimmed)
			setInputValue(trimmed)
		},
		[onRoomChange]
	)

	return (
		<div className="collab-room-bar">
			<span className="collab-room-bar__label">Room:</span>
			<input
				className="collab-room-bar__input"
				value={inputValue}
				onChange={(e) => setInputValue(e.target.value)}
				onKeyDown={(e) => {
					if (e.key === 'Enter') applyRoomId(inputValue)
				}}
				placeholder="Enter room ID..."
				spellCheck={false}
			/>
			<button
				className="collab-room-bar__btn"
				onClick={() => applyRoomId(inputValue)}
			>
				Join
			</button>
		</div>
	)
}

// --- Main App component ---

function App() {
	const [roomId, setRoomId] = useState<string>(readInitialRoomId)
	const [app, setApp] = useState<TldrawAgentApp | null>(null)
	const [sidebarOpen, setSidebarOpen] = useState(true)

	// useSyncDemo connects to tldraw's demo sync server.
	// NOTE: demo server data is public and cleared after ~1 day.
	// For production, replace with useSync({ uri: 'wss://...' }).
	const syncStatus = useSyncDemo({ roomId })

	const handleUnmount = useCallback(() => {
		setApp(null)
	}, [])

	// Custom components to visualize what the agent is doing
	// These use TldrawAgentAppContextProvider to access the app/agent
	const components: TLComponents = useMemo(() => {
		return {
			HelperButtons: () =>
				app && (
					<TldrawAgentAppContextProvider app={app}>
						<CustomHelperButtons />
					</TldrawAgentAppContextProvider>
				),
			Overlays: () => (
				<>
					<TldrawOverlays />
					{app && (
						<TldrawAgentAppContextProvider app={app}>
							<AgentViewportBoundsHighlights />
							<AllContextHighlights />
						</TldrawAgentAppContextProvider>
					)}
				</>
			),
		}
	}, [app])

	// Show loading / error states while sync is connecting
	if (syncStatus.status === 'loading') {
		return (
			<div className="collab-connecting">
				<div className="collab-connecting__inner">
					<div className="collab-connecting__spinner" />
					<p>Connecting to room <strong>{roomId}</strong>…</p>
				</div>
			</div>
		)
	}

	if (syncStatus.status === 'error') {
		return (
			<div className="collab-connecting collab-connecting--error">
				<div className="collab-connecting__inner">
					<p>Failed to connect to room <strong>{roomId}</strong></p>
					<p className="collab-connecting__detail">{(syncStatus as any).error?.message ?? 'Unknown error'}</p>
					<button onClick={() => window.location.reload()}>Retry</button>
				</div>
			</div>
		)
	}

	return (
		<TldrawUiToastsProvider>
			<div
				className="tldraw-agent-container"
				style={sidebarOpen ? undefined : { gridTemplateColumns: '0px 1fr 350px' }}
			>
				<ContextSidebar sidebarOpen={sidebarOpen} onSidebarOpenChange={setSidebarOpen} app={app} />
				<div className="tldraw-canvas tldraw-canvas--with-room-bar">
					<CollaborationRoomBar roomId={roomId} onRoomChange={setRoomId} />
					<div className="tldraw-canvas__inner">
						<Tldraw
							store={syncStatus.store}
							tools={tools}
							overrides={overrides}
							components={components}
						>
							<TldrawAgentAppProvider
								collaborationRoomId={roomId}
								onMount={setApp}
								onUnmount={handleUnmount}
							/>
						</Tldraw>
					</div>
				</div>
				<ErrorBoundary fallback={ChatPanelFallback}>
					{app && (
						<TldrawAgentAppContextProvider app={app}>
							<ChatPanel />
						</TldrawAgentAppContextProvider>
					)}
				</ErrorBoundary>
			</div>
		</TldrawUiToastsProvider>
	)
}

export default App
