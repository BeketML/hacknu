import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { AGENT_MODE_DEFINITIONS } from '../client/modes/AgentModeDefinitions.ts'
import { buildResponseSchema } from '../shared/schema/buildResponseSchema.ts'

const __dirname = dirname(fileURLToPath(import.meta.url))
const outDir = join(__dirname, '..', '..', 'backend', 'app', 'data', 'schemas')
mkdirSync(outDir, { recursive: true })

for (const mode of AGENT_MODE_DEFINITIONS) {
	if (!('active' in mode) || !mode.active) continue
	const schema = buildResponseSchema(mode.actions, mode.type)
	writeFileSync(join(outDir, `${mode.type}.json`), JSON.stringify(schema, null, 2) + '\n', 'utf8')
}

console.log('Wrote response schemas to', outDir)
