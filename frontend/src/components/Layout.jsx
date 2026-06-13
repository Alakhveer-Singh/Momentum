import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import client from '../api/client'
import {
  Bell,
  CheckSquare,
  Filter,
  LayoutDashboard,
  Mail,
  Menu,
  ShieldCheck,
  Target,
  TrendingUp,
  Users as UsersIcon,
  KanbanSquare,
} from 'lucide-react'
import { connectEcho, realtime } from '../echo'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/pipeline', label: 'Pipeline', icon: KanbanSquare },
  { to: '/leads', label: 'Leads', icon: UsersIcon },
  { to: '/tasks', label: 'Tasks', icon: CheckSquare },
  { to: '/templates', label: 'Email Templates', icon: Mail },
  { to: '/reports', label: 'Reports', icon: TrendingUp },
  { to: '/funnel', label: 'Lead Funnel', icon: Filter },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [notifs, setNotifs] = useState([])
  const [unread, setUnread] = useState(0)
  const [showNotifs, setShowNotifs] = useState(false)

  const loadNotifs = () =>
    client.get('notifications').then((res) => {
      setNotifs(res.data.notifications)
      setUnread(res.data.unread_count)
    })

  useEffect(() => {
    loadNotifs()
    const token = localStorage.getItem('token')
    connectEcho(token)

    const offLead = realtime.on('lead.updated', (e) => {
      if (e.action !== 'updated' && 'Notification' in window && Notification.permission === 'granted') {
        new Notification('Quibus LMS', {
          body: `Lead ${e.lead.full_name} ${e.action === 'created' ? 'captured' : e.action} (${e.lead.stage ?? ''})`,
        })
      }
      window.dispatchEvent(new CustomEvent('lead-updated', { detail: e }))
    })

    const offNotif = realtime.on('notification', (msg) => {
      loadNotifs()
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Quibus LMS', { body: msg.payload?.message ?? 'New notification' })
      }
    })

    return () => {
      offLead()
      offNotif()
    }
  }, [user.id])

  const markAllRead = async () => {
    await client.post('notifications/read')
    loadNotifs()
  }

  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
      isActive ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-700 hover:text-white'
    }`

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform bg-slate-900 p-4 transition-transform lg:static lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="mb-8 flex items-center gap-2.5 px-2">
          <Target className="h-7 w-7 text-indigo-400" strokeWidth={2.2} />
          <span className="text-lg font-bold text-white">Quibus LMS</span>
        </div>
        <nav className="space-y-1">
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={linkClass} onClick={() => setOpen(false)}>
              <item.icon className="h-5 w-5" /> {item.label}
            </NavLink>
          ))}
          {user.role === 'admin' && (
            <NavLink to="/users" className={linkClass} onClick={() => setOpen(false)}>
              <ShieldCheck className="h-5 w-5" /> Team & Roles
            </NavLink>
          )}
        </nav>
        <div className="absolute bottom-4 left-4 right-4">
          <div className="rounded-lg bg-slate-800 p-3 text-sm">
            <div className="font-semibold text-white">{user.name}</div>
            <div className="capitalize text-slate-400">{user.role}</div>
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => navigate('/profile')}
                className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-600"
              >
                Profile
              </button>
              <button
                onClick={async () => {
                  await logout()
                  navigate('/login')
                }}
                className="rounded bg-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-600"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />}

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <button className="rounded p-2 hover:bg-slate-100 lg:hidden" onClick={() => setOpen(true)}>
            <Menu className="h-5 w-5" />
          </button>
          <div className="hidden text-sm text-slate-500 lg:block">Lead Management & CRM</div>
          <div className="relative">
            <button
              onClick={() => setShowNotifs((s) => !s)}
              className="relative rounded-full p-2 hover:bg-slate-100"
              title="Notifications"
            >
              <Bell className="h-5 w-5 text-slate-600" />
              {unread > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white">
                  {unread}
                </span>
              )}
            </button>
            {showNotifs && (
              <div className="absolute right-0 mt-2 w-80 rounded-xl border border-slate-200 bg-white shadow-xl">
                <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
                  <span className="text-sm font-semibold">Notifications</span>
                  <button onClick={markAllRead} className="text-xs text-indigo-600 hover:underline">
                    Mark all read
                  </button>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {notifs.length === 0 && <div className="p-4 text-sm text-slate-400">No notifications yet.</div>}
                  {notifs.map((n) => (
                    <div key={n.id} className={`border-b border-slate-50 px-4 py-2 text-sm ${!n.read_at ? 'bg-indigo-50' : ''}`}>
                      <div>{n.data.message}</div>
                      <div className="text-xs text-slate-400">{new Date(n.created_at).toLocaleString()}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </header>
        <main className="flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
