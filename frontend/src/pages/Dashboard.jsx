import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import client from '../api/client'

const inr = (n) => '₹' + Number(n).toLocaleString('en-IN')

function Stat({ label, value, accent = 'text-slate-900' }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${accent}`}>{value}</div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [tasks, setTasks] = useState([])
  const [activities, setActivities] = useState([])

  const load = () => {
    client.get('reports/dashboard').then((r) => setStats(r.data))
    client.get('tasks', { params: { status: 'pending', per_page: 5 } }).then((r) => setTasks(r.data.data))
    client.get('activities', { params: { per_page: 8 } }).then((r) => setActivities(r.data.data))
  }

  useEffect(() => {
    load()
    window.addEventListener('lead-updated', load)
    return () => window.removeEventListener('lead-updated', load)
  }, [])

  if (!stats) return <div className="text-slate-500">Loading dashboard…</div>

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Open Leads" value={stats.open_leads} />
        <Stat label="Pipeline Value" value={inr(stats.pipeline_value)} accent="text-indigo-600" />
        <Stat label="Conversion Rate" value={stats.conversion_rate + '%'} accent="text-emerald-600" />
        <Stat label="Won Value" value={inr(stats.won_value)} accent="text-emerald-600" />
        <Stat label="New This Week" value={stats.new_this_week} />
        <Stat label="Avg Lead Score" value={stats.avg_score} />
        <Stat label="Pending Tasks" value={stats.pending_tasks} />
        <Stat label="Overdue Tasks" value={stats.overdue_tasks} accent={stats.overdue_tasks > 0 ? 'text-red-600' : 'text-slate-900'} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">Upcoming Tasks</h2>
            <Link to="/tasks" className="text-sm text-indigo-600 hover:underline">View all</Link>
          </div>
          {tasks.length === 0 && <div className="text-sm text-slate-400">No pending tasks.</div>}
          <ul className="space-y-2">
            {tasks.map((t) => (
              <li key={t.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <div>
                  <div className="font-medium">{t.title}</div>
                  <div className="text-xs text-slate-400">
                    {t.lead ? `${t.lead.first_name} ${t.lead.last_name ?? ''} · ` : ''}
                    {t.due_at ? new Date(t.due_at).toLocaleDateString() : 'No due date'}
                  </div>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    t.priority === 'high' ? 'bg-red-100 text-red-700' : t.priority === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-200 text-slate-600'
                  }`}
                >
                  {t.priority}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 font-semibold">Recent Activity</h2>
          <ul className="space-y-2">
            {activities.map((a) => (
              <li key={a.id} className="flex items-start gap-2 text-sm">
                <span>
                  {{ call: '📞', email: '✉️', meeting: '🤝', note: '📝', stage_change: '🔁', system: '⚙️' }[a.type] ?? '•'}
                </span>
                <div>
                  <div>
                    {a.subject}
                    {a.lead && (
                      <Link to={`/leads/${a.lead.id}`} className="ml-1 text-indigo-600 hover:underline">
                        — {a.lead.first_name} {a.lead.last_name ?? ''}
                      </Link>
                    )}
                  </div>
                  <div className="text-xs text-slate-400">
                    {a.user?.name} · {new Date(a.occurred_at).toLocaleString()}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
