import { readFileSync, writeFileSync } from 'node:fs'

const spec = JSON.parse(readFileSync(new URL('../openapi.json', import.meta.url), 'utf8'))
const paths = Object.keys(spec.paths ?? {}).sort()

function pattern(path) {
  const relative = path.replace(/^\/api\/v1/, '') || '/'
  const typed = relative.replace(/\{[^}]+\}/g, '${string}')
  return typed.includes('${') ? `\`${typed}\`` : `'${typed}'`
}

const names = paths.map(pattern)
const body = `/* Generated from openapi.json. Run: node scripts/generate-api-types.mjs */
export type ApiPath =
${names.map((name) => `  | ${name}`).join('\n')}
`
writeFileSync(new URL('../src/api/schema.d.ts', import.meta.url), body)
console.log(`wrote src/api/schema.d.ts (${names.length} paths)`)
