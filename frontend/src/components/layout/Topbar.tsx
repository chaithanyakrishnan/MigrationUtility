// components/layout/Topbar.tsx
interface TopbarProps { title: string; subtitle: string }
export default function Topbar({ title, subtitle }: TopbarProps) {
  return (
    <div className="topbar">
      <div style={{ flex: 1 }}>
        <div className="topbar-title">{title}</div>
        <div className="topbar-sub">{subtitle}</div>
      </div>
    </div>
  )
}
