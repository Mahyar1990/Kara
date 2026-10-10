import path from 'node:path'
import ts from 'typescript'

const root = path.resolve('web')
const configPath = path.join(root, 'tsconfig.json')
const config = ts.readConfigFile(configPath, ts.sys.readFile)
if (config.error) throw new Error(ts.flattenDiagnosticMessageText(config.error.messageText, '\n'))
const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, root)
const files = [
  'app/components/company-projects/index.tsx',
  'app/components/company-projects/access.tsx',
  'app/components/company-projects/forms.tsx',
  'app/components/company-projects/project-page.tsx',
  'app/components/company-projects/setup.tsx',
  'app/components/company-projects/templates.tsx',
  'app/components/company-projects/inbox.tsx',
  'app/(commonLayout)/projects/[projectId]/inbox/page.tsx',
  'service/company-inbox.ts',
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
