import { cloudflare } from '@cloudflare/vite-plugin'
import react from '@vitejs/plugin-react-swc'
import { fileURLToPath } from 'url'
import { defineConfig } from 'vite'
import { zodLocalePlugin } from './scripts/vite-zod-locale-plugin.js'

// https://vitejs.dev/config/
export default defineConfig(() => {
	return {
		server: {
			proxy: {
				'/stream': {
					target: process.env.VITE_AGENT_API ?? 'http://127.0.0.1:8000',
					changeOrigin: true,
				},
			},
		},
		build: {
			// tldraw + React produce a multi-MB client chunk; 500 kB default is too strict here.
			chunkSizeWarningLimit: 3000,
		},
		plugins: [
			zodLocalePlugin(fileURLToPath(new URL('./scripts/zod-locales-shim.js', import.meta.url))),
			cloudflare(),
			react(),
		],
	}
})
