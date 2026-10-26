import path from 'node:path'
import ts from 'typescript'

const root = path.resolve('web')
const configPath = path.join(root, 'tsconfig.json')
const config = ts.readConfigFile(configPath, ts.sys.readFile)
if (config.error) throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'))
const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, root)
const files = [
  'app/components/company-projects/gitlab-connections.tsx',
  'app/(commonLayout)/projects/[projectId]/gitlab-connections/page.tsx',
  'service/company-gitlab.ts',
  'app/components/company-projects/team-recovery.tsx',
  'app/components/company-projects/team-inbox.tsx',
  'utils/company-team-work.ts',
  'app/components/company-projects/team-runs.tsx',
  'app/(commonLayout)/projects/[projectId]/team-runs/page.tsx',
  'service/company-stages.ts',
  'app/components/company-projects/team-requests.tsx',
  'app/(commonLayout)/projects/[projectId]/requests/page.tsx',
  'service/company-requests.ts',
  'app/components/company-projects/team-flows.tsx',
  'app/(commonLayout)/projects/[projectId]/team-flows/page.tsx',
  'service/company-flows.ts',
  'app/components/company-projects/team-agents.tsx',
  'app/(commonLayout)/projects/[projectId]/team-agents/page.tsx',
  'service/company-agents.ts',
  'app/components/base/logo/kara-logo.tsx',
  'utils/document-title.ts',
  'app/components/company-projects/index.tsx',
  'app/components/company-projects/access.tsx',
  'app/components/company-projects/forms.tsx',
  'app/components/company-projects/project-page.tsx',
  'app/components/company-projects/setup.tsx',
  'app/components/company-projects/templates.tsx',
  'app/components/company-projects/inbox.tsx',
  'app/(commonLayout)/projects/[projectId]/inbox/page.tsx',
  'service/company-inbox.ts',
  'app/components/company-projects/automations.tsx',
  'app/(commonLayout)/projects/[projectId]/automations/page.tsx',
  'service/company-automations.ts',
  'app/(commonLayout)/projects/[projectId]/templates/page.tsx',
  'app/(commonLayout)/projects/[projectId]/setup/page.tsx',
  'service/company-adoption.ts',
  'app/(commonLayout)/projects/page.tsx',
  'app/(commonLayout)/projects/[projectId]/page.tsx',
  'app/components/main-nav/routes.ts',
  'app/components/main-nav/index.tsx',
  'app/components/main-nav/layout.tsx',
  'app/components/company-projects/navigation.tsx',
  'utils/company-navigation.ts',
  'app/components/company-members/administration.tsx',
  'app/(commonLayout)/administration/users/page.tsx',
  'service/company-projects.ts',
  'app/(commonLayout)/users/page.tsx',
  'app/components/company-members/index.tsx',
  'app/components/company-members/business-roles.tsx',
  'app/components/header/account-setting/members-page/index.tsx',
  'service/use-common.ts',
  'service/access-control/use-workspace-roles.ts',
  'service/access-control/use-member-roles.ts',
  'utils/company-members.ts',
].map(file => path.join(root, file))
const program = ts.createProgram(files, { ...parsed.options, incremental: false, noEmit: true })
const errors = [...parsed.errors, ...program.getOptionsDiagnostics()]
for (const file of files) {
  const source = program.getSourceFile(file)
  if (!source) throw new Error(`Missing project source: ${file}`)
  errors.push(...program.getSyntacticDiagnostics(source), ...program.getSemanticDiagnostics(source))
}
if (errors.length) {
  process.stderr.write(ts.formatDiagnosticsWithColorAndContext(errors, {
    getCanonicalFileName: file => file,
    getCurrentDirectory: ts.sys.getCurrentDirectory,
    getNewLine: () => '\n',
  }))
  process.exit(1)
}
console.log('Company UI types checked: projects, members, navigation and API clients.')
