// Display labels only: IDs and permission keys sent to Dify stay unchanged.
const builtinRoles: Record<string, { name: string; description: string }> = {
  owner: { name: 'مالک', description: 'مدیریت پروژه و اعضای آن؛ ساخت پروژه و تعیین مالک فقط با ادمین کل Kara' },
  admin: { name: 'مدیر فنی', description: 'مدیریت تنظیمات و محتوای پروژه؛ مدیریت اعضا با مالک پروژه' },
  editor: { name: 'توسعه‌دهنده', description: 'ساخت برنامه، ایجنت، دانش و اسکیل در پروژه؛ بدون مدیریت اعضا' },
  normal: { name: 'کاربر', description: 'استفاده از برنامه‌ها؛ بدون ساخت یا ویرایش آن‌ها' },
  dataset_operator: { name: 'مدیر دانش', description: 'مدیریت پایگاه‌های دانش' },
}

export function localizeWorkspaceRole<T extends { id: string; name: string }>(role: T): T {
  return Object.hasOwn(builtinRoles, role.id) ? { ...role, ...builtinRoles[role.id] } : role
}

export type MemberStatusFilter = 'all' | 'active' | 'pending'

export function filterWorkspaceMembers<T extends { name: string; email: string; status: string }>(
  members: T[], search: string, status: MemberStatusFilter,
): T[] {
  const keyword = search.trim().toLocaleLowerCase('fa-IR')
  return members.filter(member =>
    (status === 'all' || member.status === status)
    && (!keyword || `${member.name} ${member.email}`.toLocaleLowerCase('fa-IR').includes(keyword)),
  )
}
