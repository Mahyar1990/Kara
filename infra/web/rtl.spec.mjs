import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import postcss from 'postcss'
import rtl, { directionSelector } from './rtl-postcss.cjs'

test('direction follows local LTR islands and does not raise utility specificity', () => {
  assert.equal(directionSelector('[dir="rtl"]', '.field'), '.field:where(:dir(rtl))')
  assert.equal(directionSelector('[dir="ltr"]', '.field'), '.field:where(:dir(ltr))')
})

test('pseudo-elements remain valid selectors', () => {
  assert.equal(directionSelector('[dir="rtl"]', '.item:hover::before'), '.item:hover:where(:dir(rtl))::before')
})

test('asymmetric spacing and offsets mirror; symmetric spacing is preserved', async () => {
  const { root } = await postcss([rtl()]).process('.pl{padding-left:8px}.px{padding-left:16px;padding-right:16px}.anchor{left:0}', { from: undefined })
  const rules = Object.fromEntries(root.nodes.filter(n => n.type === 'rule').map(n => [n.selector, Object.fromEntries(n.nodes.filter(d => d.type === 'decl').map(d => [d.prop, d.value]))]))
  assert.deepEqual(rules['.pl:where(:dir(rtl))'], { 'padding-right': '8px' })
  assert.deepEqual(rules['.pl:where(:dir(ltr))'], { 'padding-left': '8px' })
  assert.deepEqual(rules['.px'], { 'padding-left': '16px', 'padding-right': '16px' })
  assert.deepEqual(rules['.anchor:where(:dir(rtl))'], { right: '0' })
})

test('code and URLs are not altered by the stylesheet transformer', async () => {
  const result = await postcss([rtl()]).process('.code{font-family:monospace;background:url("/right-arrow.svg")}', { from: undefined })
  assert.ok(result.css.includes('/right-arrow.svg'))
  assert.ok(result.css.includes('font-family:monospace'))
})

test('Tailwind 4 horizontal translations follow mirrored positioning', async () => {
  const result = await postcss([rtl()]).process('.center{left:50%;--tw-translate-x:-50%;translate:var(--tw-translate-x) -50%}', { from: undefined })
  const directional = result.root.nodes.find(n => n.selector === '.center:where(:dir(rtl))')
  assert.ok(directional.nodes.some(d => d.prop === 'right' && d.value === '50%'))
  assert.ok(directional.nodes.some(d => d.prop === '--tw-translate-x' && d.value === 'calc(-50% * -1)'))
  assert.ok(result.css.includes('translate:var(--tw-translate-x) -50%'))
})

test('explicit Persian and technical directions are not flipped a second time', async () => {
  const sheet = readFileSync(new URL('./persian.css', import.meta.url), 'utf8')
  const result = await postcss([rtl()]).process(sheet, { from: undefined })
  const html = result.root.nodes.find(n => n.selector === "html[lang='fa-IR']")
  assert.ok(html.nodes.some(d => d.prop === 'direction' && d.value === 'rtl'))
  assert.ok(result.css.includes('direction: ltr'))
})
