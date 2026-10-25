import type { MainNavItem } from '@/app/components/main-nav/types'

type ProjectIdentity = { id: string }

export function isCompanyStartPath(pathname: string) {
  return pathname === '/' || pathname === '/explore/apps'
}

// A remembered Dify workspace must not expose project tools on the product screens.
export function companyNavigationScope(pathname: string, project: ProjectIdentity | null) {
  if (isCompanyStartPath(pathname) || pathname === '/projects'
    || pathname === '/administration' || pathname.startsWith('/administration/')) return 'product'
  if (pathname.startsWith('/projects/')) {
    const id = pathname.split('/')[2]
    return project?.id === id ? 'project' : 'product'
  }
  return project ? 'project' : 'choose'
}

const item = (href: string, label: string, icon: string, active: MainNavItem['active']): MainNavItem => ({
  href, label, active, icon, activeIcon: icon,
})

export function productNavigation(isOwner: boolean): MainNavItem[] {
  return [
    item('/projects', 'پروژه‌ها', 'i-ri-folder-line', path => path === '/projects' || path.startsWith('/projects/')),
    ...(isOwner ? [item('/administration/users', 'مدیریت کاربران محصول', 'i-ri-team-line', path => path.startsWith('/administration/'))] : []),
  ]
}

export function projectNavigation(projectId: string, nativeItems: MainNavItem[]): MainNavItem[] {
  const base = `/projects/${projectId}`
  const native = (href: string) => nativeItems.filter(entry => entry.href === href)
    .map(entry => href === '/apps' ? { ...entry, label: 'برنامه‌ها و فرایندها' } : entry)
  const group = (entries: MainNavItem[]) => entries.map((entry, index) => index === 0 ? { ...entry, separatorBefore: true } : entry)
  return [
    item(base, 'نمای کلی پروژه', 'i-ri-folder-line', path => path === base),
    ...group([
      item(`${base}/requests`, 'درخواست‌های پروژه', 'i-ri-file-list-3-line', path => path === `${base}/requests`),
      ...native('/apps'),
      item(`${base}/team-agents`, 'ایجنت‌های تیم', 'i-ri-team-line', path => path === `${base}/team-agents`),
      item(`${base}/team-flows`, 'فلوهای تیم', 'i-ri-route-line', path => path === `${base}/team-flows`),
    ]),
    ...group([
      item(`${base}/team-runs`, 'اجرای تیمی', 'i-ri-play-circle-line', path => path === `${base}/team-runs`),
      item(`${base}/inbox`, 'کارتابل و اقدام‌های من', 'i-ri-inbox-line', path => path === `${base}/inbox`),
    ]),
    ...group([
      ...native('/datasets'),
      ...native('/skills'),
      item(`${base}/templates`, 'قالب‌های آماده', 'i-ri-file-copy-line', path => path === `${base}/templates`),
      item(`${base}/automations`, 'اتوماسیون‌ها', 'i-ri-timer-line', path => path === `${base}/automations`),
    ]),
    ...group([
      item('/users', 'اعضای پروژه', 'i-ri-team-line', path => path === '/users'),
      item(`${base}/setup`, 'راهنمای پروژه', 'i-ri-question-line', path => path === `${base}/setup`),
    ]),
    item(`${base}/jira-connections`, 'اتصال به جیرا', 'i-ri-links-line', path => path === `${base}/jira-connections`),
    ...nativeItems.filter(entry => !['/', '/projects', '/users', '/apps', '/datasets', '/skills'].includes(entry.href)),
  ]
}
