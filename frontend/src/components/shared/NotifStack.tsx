// components/shared/NotifStack.tsx
import { useStore } from '@/store'

export default function NotifStack() {
  const notifications = useStore(s => s.notifications)
  const dismiss       = useStore(s => s.dismissNotif)

  if (!notifications.length) return null

  return (
    <div className="notif-stack">
      {notifications.map(n => (
        <div
          key={n.id}
          className={`notif ${n.type}`}
          onClick={() => dismiss(n.id)}
        >
          {n.message}
        </div>
      ))}
    </div>
  )
}
