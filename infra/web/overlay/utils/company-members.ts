// Display labels only: IDs and permission keys sent to Dify stay unchanged.
const builtinRoles: Record<string, { name: string; description: string }> = {
  owner: { name: 'مالک فضای کاری', description: 'کنترل کامل فضای کاری و اعضای آن' },
  admin: { name: 'مدیر', description: 'مدیریت اعضا و تنظیمات، ساخت و ویرایش برنامه‌ها' },
  editor: { name: 'توسعه‌دهنده', description: 'ساخت و ویرایش برنامه‌ها؛ بدون مدیریت اعضا' },
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
