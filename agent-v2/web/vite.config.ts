import react from '@vitejs/plugin-react-swc'
import { fileURLToPath } from 'url'
import { defineConfig } from 'vite'
import { zodLocalePlugin } from './scripts/vite-zod-locale-plugin.js'

/**
 * Deploy strategy B: Vite SPA only; LLM is handled by Python FastAPI (`agent-v2/backend`).
 *
 * Acceptance checklist:
 * - `uvicorn app.main:app --port 8000` (from backend/) then `npm run dev` — board + /stream via proxy → Python.
 * - `npm run build` — static `dist/` for nginx / static hosting.
 * - `npm run export-response-schemas` — refreshes `../backend/app/data/schemas/` (no worker).
 *
 * Env: `VITE_AGENT_API` — proxy target for `/stream` and `/api` in dev (default http://127.0.0.1:8000).
 * Client: `VITE_STREAM_URL` — optional absolute URL for POST /stream when static and API differ (see TldrawAgent).
 * Client: `VITE_AGENT_API_BASE` — optional origin for `/api/image-gen/*` when SPA and API differ (see GenerateImageActionUtil).
 */
export default defineConfig(() => {
	return {
		root: '.',
		publicDir: 'public',
		server: {
			host: '0.0.0.0',
			proxy: {
				'/stream': {
					target: process.env.VITE_AGENT_API ?? 'http://127.0.0.1:8000',
					changeOrigin: true,
				},
				'/api': {
					target: process.env.VITE_AGENT_API ?? 'http://127.0.0.1:8000',
					changeOrigin: true,
				},
			},
		},
		build: {
			chunkSizeWarningLimit: 3000,
		},
		plugins: [
			zodLocalePlugin(fileURLToPath(new URL('./scripts/zod-locales-shim.js', import.meta.url))),
			react(),
		],
	}
})
