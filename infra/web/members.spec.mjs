import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import ts from 'typescript'

const source = await readFile('web/utils/company-members.ts', 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText
const { localizeWorkspaceRole, filterWorkspaceMembers } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('Persian display labels retain role identity and permission keys', () => {
  const original = { id: 'editor', name: 'editor', permission_keys: ['app.create_and_management'] }
  const displayed = localizeWorkspaceRole(original)
  assert.equal(displayed.name, 'توسعه‌دهنده')
  assert.equal(displayed.id, original.id)
  assert.deepEqual(displayed.permission_keys, original.permission_keys)
  assert.equal(original.name, 'editor')
})

test('custom role with a built-in name is not renamed', () => {
  const custom = { id: 'da7a3c47-279c-45c5-a453-916628e81783', name: 'admin', description: 'Custom permissions' }
  assert.equal(localizeWorkspaceRole(custom), custom)
  assert.equal(localizeWorkspaceRole({ id: 'toString', name: 'Custom' }).name, 'Custom')
})

test('member search combines name, email and status without changing membership', () => {
  const members = [
    { id: 'a', name: 'همکار توسعه', email: 'Developer@example.test', status: 'active' },
    { id: 'b', name: 'همکار پشتیبانی', email: 'Support@example.test', status: 'pending' },
  ]
  assert.deepEqual(filterWorkspaceMembers(members, '  DEVELOPER@  ', 'all').map(member => member.id), ['a'])
  assert.deepEqual(filterWorkspaceMembers(members, 'پشتیبانی', 'pending').map(member => member.id), ['b'])
  assert.equal(filterWorkspaceMembers(members, 'پشتیبانی', 'active').length, 0)
  assert.equal(filterWorkspaceMembers(members, '', 'all').length, 2)
  assert.equal(members.length, 2)
})
