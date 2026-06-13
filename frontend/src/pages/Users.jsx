import { useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import client from '../api/client'

const empty = { name: '', email: '', password: '', role: 'rep', phone: '' }

export default function Users() {
  const [users, setUsers] = useState([])
  const [editing, setEditing] = useState(null) // null | 'new' | user
  const [form, setForm] = useState(empty)
  const [error, setError] = useState('')

  const load = () => client.get('users').then((r) => setUsers(r.data))
  useEffect(() => {
    load()
  }, [])

  const save = async (e) => {
    e.preventDefault()
    setError('')
    const payload = Object.fromEntries(Object.entries(form).filter(([, v]) => v !== ''))
    try {
      if (editing === 'new') await client.post('users', payload)
      else await client.put(`users/${editing.id}`, payload)
      setEditing(null)
      setForm(empty)
      load()
    } catch (err) {
      setError(err.response?.data?.message || 'Save failed.')
    }
  }

  const toggleActive = async (u) => {
    try {
      await client.put(`users/${u.id}`, { is_active: !u.is_active })
      load()
    } catch (err) {
      alert(err.response?.data?.message || 'Update failed.')
    }
  }

  const remove = async (u) => {
    if (!confirm(`Delete user ${u.name}? Their leads will be unassigned.`)) return
    try {
      await client.delete(`users/${u.id}`)
      load()
    } catch (err) {
      alert(err.response?.data?.message || 'Delete failed.')
    }
  }

  const input = 'rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Team & Roles</h1>
        <button
          onClick={() => {
            setEditing('new')
            setForm(empty)
          }}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" /> Add User
        </button>
      </div>

      {editing && (
        <form onSubmit={save} className="flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-4">
          <input className={input} required placeholder="Name *" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          <input className={input} required={editing === 'new'} type="email" placeholder="Email *" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
          <input
            className={input}
            required={editing === 'new'}
            type="password"
            placeholder={editing === 'new' ? 'Password * (min 8)' : 'New password (optional)'}
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
          />
          <select className={input} value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
            <option value="rep">Sales Rep</option>
            <option value="manager">Manager</option>
            <option value="admin">Admin</option>
          </select>
          <input className={input} placeholder="Phone" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
          <button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">Save</button>
          <button type="button" onClick={() => setEditing(null)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Cancel</button>
          {error && <div className="w-full rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
        </form>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Role</th>
              <th className="hidden px-4 py-3 md:table-cell">Leads</th>
              <th className="hidden px-4 py-3 md:table-cell">Tasks</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-slate-100">
                <td className="px-4 py-3">
                  <div className="font-medium">{u.name}</div>
                  <div className="text-xs text-slate-400">{u.email}</div>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
                      u.role === 'admin' ? 'bg-purple-100 text-purple-700' : u.role === 'manager' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {u.role}
                  </span>
                </td>
                <td className="hidden px-4 py-3 md:table-cell">{u.leads_count}</td>
                <td className="hidden px-4 py-3 md:table-cell">{u.tasks_count}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => toggleActive(u)}
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${u.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}
                  >
                    {u.is_active ? 'Active' : 'Inactive'}
                  </button>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => {
                      setEditing(u)
                      setForm({ name: u.name, email: u.email, password: '', role: u.role, phone: u.phone ?? '' })
                    }}
                    className="rounded p-1.5 text-slate-500 hover:bg-slate-100"
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button onClick={() => remove(u)} className="rounded p-1.5 text-red-500 hover:bg-red-50" title="Delete">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
