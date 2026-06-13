import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'

export default function Tasks() {
  const { user } = useAuth()
  const [page, setPage] = useState(null)
  const [filter, setFilter] = useState('pending')
  const [users, setUsers] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', description: '', priority: 'medium', due_at: '', assigned_to: user.id })

  const load = (p = 1) =>
    client
      .get('tasks', { params: { page: p, status: filter === 'overdue' ? 'pending' : filter || undefined, overdue: filter === 'overdue' ? 1 : undefined } })
      .then((r) => setPage(r.data))

  useEffect(() => {
    load(1)
  }, [filter])

  useEffect(() => {
    if (user.role !== 'rep') client.get('users').then((r) => setUsers(r.data)).catch(() => {})
  }, [user.role])

  const toggle = async (task) => {
    await client.put(`tasks/${task.id}`, { status: task.status === 'pending' ? 'completed' : 'pending' })
    load(page?.current_page ?? 1)
  }

  const create = async (e) => {
    e.preventDefault()
    await client.post('tasks', { ...form, due_at: form.due_at || null })
    setForm({ title: '', description: '', priority: 'medium', due_at: '', assigned_to: user.id })
    setShowForm(false)
    load(1)
  }

  const overdue = (t) => t.status === 'pending' && t.due_at && new Date(t.due_at) < new Date()

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold">Tasks</h1>
        <button onClick={() => setShowForm((s) => !s)} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
          <Plus className="h-4 w-4" /> New Task
        </button>
      </div>

      {showForm && (
        <form onSubmit={create} className="grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-5">
          <input
            required
            placeholder="Task title *"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            className="col-span-2 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <select value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))} className="rounded-lg border border-slate-300 px-2 py-2 text-sm">
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
          <input type="datetime-local" value={form.due_at} onChange={(e) => setForm((f) => ({ ...f, due_at: e.target.value }))} className="rounded-lg border border-slate-300 px-2 py-2 text-sm" />
          {user.role !== 'rep' ? (
            <select value={form.assigned_to} onChange={(e) => setForm((f) => ({ ...f, assigned_to: Number(e.target.value) }))} className="rounded-lg border border-slate-300 px-2 py-2 text-sm">
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          ) : (
            <button className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white">Create</button>
          )}
          {user.role !== 'rep' && <button className="col-span-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white md:col-span-1">Create</button>}
        </form>
      )}

      <div className="flex gap-2">
        {['pending', 'overdue', 'completed', ''].map((f) => (
          <button
            key={f || 'all'}
            onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1.5 text-sm font-medium ${filter === f ? 'bg-indigo-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}
          >
            {f === '' ? 'All' : f[0].toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {page?.data.map((t) => (
          <div key={t.id} className={`flex items-center gap-3 rounded-xl border bg-white p-3 ${overdue(t) ? 'border-red-200' : 'border-slate-200'}`}>
            <input type="checkbox" checked={t.status === 'completed'} onChange={() => toggle(t)} className="h-5 w-5 accent-indigo-600" />
            <div className="min-w-0 flex-1">
              <div className={`font-medium ${t.status === 'completed' ? 'text-slate-400 line-through' : ''}`}>{t.title}</div>
              <div className="text-xs text-slate-400">
                {t.lead && (
                  <Link to={`/leads/${t.lead.id}`} className="text-indigo-600 hover:underline">
                    {t.lead.first_name} {t.lead.last_name ?? ''}
                  </Link>
                )}
                {t.lead && ' · '}
                {t.assignee?.name}
                {t.due_at && (
                  <span className={overdue(t) ? 'font-semibold text-red-500' : ''}> · due {new Date(t.due_at).toLocaleString()}</span>
                )}
              </div>
            </div>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                t.priority === 'high' ? 'bg-red-100 text-red-700' : t.priority === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
              }`}
            >
              {t.priority}
            </span>
          </div>
        ))}
        {page?.data.length === 0 && <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-400">No tasks.</div>}
      </div>
    </div>
  )
}
