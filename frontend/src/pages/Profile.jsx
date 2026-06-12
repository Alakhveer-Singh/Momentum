import { useState } from 'react'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'

export default function Profile() {
  const { user, setUser } = useAuth()
  const [form, setForm] = useState({ name: user.name, phone: user.phone ?? '', current_password: '', password: '', password_confirmation: '' })
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setMsg('')
    setError('')
    const payload = { name: form.name, phone: form.phone || null }
    if (form.password) {
      payload.password = form.password
      payload.password_confirmation = form.password_confirmation
      payload.current_password = form.current_password
    }
    try {
      const res = await client.put('auth/profile', payload)
      setUser(res.data)
      setMsg('Profile updated.')
      setForm((f) => ({ ...f, current_password: '', password: '', password_confirmation: '' }))
    } catch (err) {
      setError(err.response?.data?.message || 'Update failed.')
    }
  }

  const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none'

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-xl font-bold">My Profile</h1>
      <form onSubmit={submit} className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
        <div>
          <label className="mb-1 block text-sm font-medium">Name</label>
          <input className={input} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Email</label>
          <input className={`${input} bg-slate-50`} value={user.email} disabled />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Phone</label>
          <input className={input} value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
        </div>
        <hr className="border-slate-100" />
        <div className="text-sm font-semibold">Change password</div>
        <input className={input} type="password" placeholder="Current password" value={form.current_password} onChange={(e) => setForm((f) => ({ ...f, current_password: e.target.value }))} />
        <input className={input} type="password" placeholder="New password (min 8)" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
        <input className={input} type="password" placeholder="Confirm new password" value={form.password_confirmation} onChange={(e) => setForm((f) => ({ ...f, password_confirmation: e.target.value }))} />
        {msg && <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</div>}
        {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
        <button className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">Save changes</button>
      </form>
    </div>
  )
}
