import ts from 'typescript'
import { readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const translations = JSON.parse(readFileSync(new URL('./literal-translations.json', import.meta.url)))
const technical = new Set(['sandbox', 'backend', 'services/backend', 'docs/architecture.md',
  'python3 -m kara_source_runner run', '~/KaraSourceWorkspaces', '--root /your/private/path',
  '.kara/manifest.json', '~/.config/kara-source-runner/device.json', 'CSV', 'JSON', 'JSONL', 'SVG', 'OAuth', 'PKCS1_OAEP', 'Kara', 'Dify', 'GitHub',
  'Jina Reader', 'WaterCrawl', '🔥 Firecrawl', 'ESC', 'Enter', '.csv', 'ABCD-1234', 'default', 'dify_app',
  'NEXT_PUBLIC_APP_ID=', 'NEXT_PUBLIC_APP_KEY=', 'NEXT_PUBLIC_API_URL=', 'error_message', 'last_run',
  'conversation_var', 'structured_output', 'sys.', 'articles/*', 'blog/*, /about/*'])
let count = 0
let files = 0
const unknown = []
function walk(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory() && !['__tests__', 'test', 'node_modules', '.next'].includes(entry.name)) walk(path)
    if (!entry.isFile() || !path.endsWith('.tsx') || /\.(spec|test|stories)\./.test(path)) continue
    let source = readFileSync(path, 'utf8')
    const ast = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const edits = []
    function visit(node) {
      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        const tag = node.tagName.getText(ast)
        const attributes = node.attributes.properties
        const values = Object.fromEntries(attributes.filter(ts.isJsxAttribute)
          .filter(attr => attr.initializer && ts.isStringLiteral(attr.initializer))
          .map(attr => [attr.name.text, attr.initializer.text]))
        const technicalInput = ['input', 'Input', 'InputGroupInput'].includes(tag)
          && (['email', 'url', 'password'].includes(values.type) || ['email', 'new-password', 'current-password'].includes(values.autoComplete))
        if (!attributes.some(attr => ts.isJsxAttribute(attr) && attr.name.text === 'dir')
          && (['pre', 'code', 'kbd', 'samp', 'ReactFlow'].includes(tag)
            || (tag === 'Handle' && source.includes("'reactflow'")) || technicalInput)) {
          const position = node.tagName.getEnd()
          edits.push({ start: position, end: position, replacement: ' dir="ltr"' })
        }
      }
      if (ts.isJsxSelfClosingElement(node)
        && ((node.tagName.getText(ast) === 'Editor' && source.includes('@monaco-editor/react'))
          || ['NodeSourceHandle', 'NodeTargetHandle'].includes(node.tagName.getText(ast)))) {
        edits.push({ start: node.getStart(ast), end: node.getStart(ast), replacement: '<div dir="ltr" className="contents">' })
        edits.push({ start: node.getEnd(), end: node.getEnd(), replacement: '</div>' })
      }
      let text
      let target
      let isText = false
      if (ts.isJsxText(node)) { text = node.text.trim(); target = node; isText = true }
      else if (path.includes('packages/dify-ui/') && ts.isStringLiteral(node)
        && Object.hasOwn(translations, node.text)) { text = node.text; target = node }
      else if (ts.isJsxAttribute(node) && ['aria-label', 'title', 'placeholder', 'alt', 'label'].includes(node.name.text)
        && node.initializer && ts.isStringLiteral(node.initializer)) { text = node.initializer.text; target = node.initializer }
      if (text && Object.hasOwn(translations, text)) {
        const replacement = isText ? node.text.replace(text, translations[text]) : JSON.stringify(translations[text])
        edits.push({ start: target.getStart(ast), end: target.getEnd(), replacement })
      } else if (text && /[A-Za-z]{3}/.test(text) && !/[\u0600-\u06ff]/.test(text)
        && !technical.has(text) && !/^(https?:\/\/|.*@|[,&]?&nbsp;)/.test(text)) unknown.push(`${path}: ${text}`)
      ts.forEachChild(node, visit)
    }
    visit(ast)
    for (const edit of edits.sort((a, b) => b.start - a.start)) source = source.slice(0, edit.start) + edit.replacement + source.slice(edit.end)
    if (edits.length) { writeFileSync(path, source); count += edits.length; files++ }
  }
}
walk(process.argv[2])
walk(join(process.argv[2], '../packages/dify-ui/src'))
if (unknown.length) throw new Error(`Untranslated JSX text:\n${unknown.join('\n')}`)
console.log(`Persian interface literals: ${count} occurrences in ${files} files; no unapproved English JSX labels.`)
