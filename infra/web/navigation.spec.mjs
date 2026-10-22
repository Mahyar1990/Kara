import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import ts from 'typescript'

const source = await readFile('web/utils/company-navigation.ts', 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText
const { companyNavigationScope, isCompanyStartPath, productNavigation, projectNavigation } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('remembered workspace does not expose project menus on product screens', () => {
  for (const path of ['/', '/explore/apps', '/projects', '/administration/users']) {
    assert.equal(companyNavigationScope(path, { id: 'team-a' }), 'product')
    assert.equal(companyNavigationScope(path, null), 'product')
  }
  assert.equal(isCompanyStartPath('/'), true)
  assert.equal(isCompanyStartPath('/apps'), false)
})

test('different project details require entry before their tools are shown', () => {
  for (const suffix of ['', '/templates', '/inbox', '/setup', '/automations', '/team-agents', '/team-flows', '/requests', '/team-runs']) {
    assert.equal(companyNavigationScope(`/projects/team-b${suffix}`, { id: 'team-a' }), 'product')
    assert.equal(companyNavigationScope(`/projects/team-b${suffix}`, null), 'product')
    assert.equal(companyNavigationScope(`/projects/team-b${suffix}`, { id: 'team-b' }), 'project')
  }
})

test('native deep links require an active project, including hidden detail sidebars', () => {
  for (const path of ['/app/a/workflow', '/agents/a/configure', '/datasets/a/documents', '/skills/a', '/users', '/integrations/model-provider']) {
    assert.equal(companyNavigationScope(path, null), 'choose')
    assert.equal(companyNavigationScope(path, { id: 'team-a' }), 'project')
  }
})

test('global navigation exposes only project selection and owner administration', () => {
  assert.deepEqual(productNavigation(false).map(item => item.href), ['/projects'])
  assert.deepEqual(productNavigation(true).map(item => item.href), ['/projects', '/administration/users'])
})

test('project links stay in the selected team and preserve native feature filtering', () => {
  const native = ['/', '/projects', '/users', '/apps', '/datasets'].map(href => ({ href, label: href, icon: '', activeIcon: '', active: () => false }))
  const navigation = projectNavigation('team-b', native)
  const hrefs = navigation.map(item => item.href)
  assert.equal(hrefs.includes('/projects'), false)
  assert.equal(hrefs.includes('/agents'), false)
  assert.equal(hrefs.includes('/skills'), false)
  for (const suffix of ['', '/templates', '/inbox', '/setup', '/automations', '/team-agents', '/team-flows', '/requests', '/team-runs']) assert.ok(hrefs.includes(`/projects/team-b${suffix}`))
  assert.equal(hrefs.filter(href => href === '/users').length, 1)
  assert.equal(navigation.find(item => item.href === '/apps').label, 'برنامه‌ها و فرایندها')
  assert.equal(navigation[0].active('/projects/team-b'), true)
  assert.equal(navigation[0].active('/projects/team-b/inbox'), false)
  assert.equal(native[3].label, '/apps')
})
