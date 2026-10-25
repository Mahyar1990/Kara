import PersonalModelConnections from '@/app/components/company-projects/model-connections'

export const metadata = { title: 'اتصال به مدل هوش مصنوعی' }

export default function PersonalModelConnectionsPage() {
  return <main className="h-full overflow-y-auto bg-background-body"><PersonalModelConnections /></main>
}
