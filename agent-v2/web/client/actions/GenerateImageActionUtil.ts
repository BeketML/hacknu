import { GenerateImageAction } from '../../shared/schema/AgentActionSchemas'
import { Streaming } from '../../shared/types/Streaming'
import { AgentActionUtil, registerActionUtil } from './AgentActionUtil'

type SingleResponse = {
	job_id: string
	artifact_paths: string[]
	artifact_urls: string[]
}

type DeckResponse = SingleResponse & { scenario?: Record<string, unknown> | null }

function apiBase(): string {
	const raw = import.meta.env.VITE_AGENT_API_BASE
	if (typeof raw === 'string' && raw.trim()) {
		return raw.replace(/\/$/, '')
	}
	return ''
}

function resolveUrl(pathOrUrl: string): string {
	if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) {
		return pathOrUrl
	}
	return `${apiBase()}${pathOrUrl}`
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
	const url = resolveUrl(path)
	const res = await fetch(url, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	})
	const text = await res.text()
	let data: unknown = null
	try {
		data = text ? JSON.parse(text) : null
	} catch {
		data = { raw: text }
	}
	if (!res.ok) {
		let detail: string = text || res.statusText
		if (typeof data === 'object' && data !== null && 'detail' in data) {
			const d = (data as { detail: unknown }).detail
			detail = Array.isArray(d) ? JSON.stringify(d) : String(d)
		}
		throw new Error(`Image API ${res.status}: ${detail}`)
	}
	return data as T
}

export const GenerateImageActionUtil = registerActionUtil(
	class GenerateImageActionUtil extends AgentActionUtil<GenerateImageAction> {
		static override type = 'generateImage' as const

		override getInfo(action: Streaming<GenerateImageAction>) {
			const mode = action.mode ?? 'single'
			return {
				icon: 'pencil' as const,
				description: action.complete
					? `Generated image (${mode})`
					: `Generating image (${mode})…`,
			}
		}

		override async applyAction(action: Streaming<GenerateImageAction>) {
			if (!action.complete) return
			const center = this.editor.getViewportPageBounds().center
			try {
				let res: SingleResponse | DeckResponse
				if (action.mode === 'deck') {
					res = await postJson<DeckResponse>('/api/image-gen/deck', {
						brief: action.text,
						num_slides: action.numSlides ?? 4,
						board_id: action.boardId ?? null,
						skip_research: action.skipResearch ?? false,
						research_depth: 'normal',
						include_scenario: false,
					})
				} else {
					res = await postJson<SingleResponse>('/api/image-gen/single', {
						prompt: action.text,
						board_id: action.boardId ?? null,
					})
				}

				const files: File[] = []
				let i = 0
				for (const u of res.artifact_urls) {
					const r = await fetch(resolveUrl(u))
					if (!r.ok) {
						throw new Error(`Failed to fetch artifact: ${r.status}`)
					}
					const blob = await r.blob()
					const name = `generated-${res.job_id}-${i++}.png`
					files.push(new File([blob], name, { type: blob.type || 'image/png' }))
				}

				if (files.length > 0) {
					await this.editor.putExternalContent({
						type: 'files',
						files,
						point: center,
					})
				}

				this.agent.schedule({
					data: [
						{
							ok: true,
							generateImage: {
								jobId: res.job_id,
								mode: action.mode,
								count: files.length,
								artifactUrls: res.artifact_urls,
							},
						},
					],
				})
			} catch (e) {
				const message = e instanceof Error ? e.message : String(e)
				this.agent.schedule({
					data: [{ ok: false, generateImageError: message }],
				})
			}
		}
	}
)
