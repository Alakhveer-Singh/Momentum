import { useEffect, useState } from 'react'
import client from '../api/client'

export default function LeadFormModal({ lead, stages, canAssign, onClose, onSaved }) {
  const [form, setForm] = useState({
    first_name: lead?.first_name ?? '',
    last_name: lead?.last_name ?? '',
    email: lead?.email ?? '',
    phone: lead?.phone ?? '',
    company: lead?.company ?? '',
    job_title: lead?.job_title ?? '',
    source: lead?.source ?? 'manual',
    stage_id: lead?.stage_id ?? '',
    owner_id: lead?.owner_id ?? '',
    value: lead?.value ?? '',
    notes: lead?.notes ?? '',
  })
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (canAssign) {
      client.get('users').then((r) => setUsers(r.data)).catch(() => {})
    }
  }, [canAssign])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    const payload = Object.fromEntries(Object.entries(form).filter(([, v]) => v !== ''))
    try {
      if (lead) await client.put(`leads/${lead.id}`, payload)
      else await client.post('leads', payload)
      onSaved()
    } catch (err) {
      setError(err.response?.data?.message || 'Save failed.')
    } finally {
      setBusy(false)
    }
  }

  const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-4 text-lg font-bold">{lead ? 'Edit Lead' : 'New Lead'}</h2>
        <form onSubmit={submit} className="grid grid-cols-2 gap-3">
          <input className={input} placeholder="First name *" required value={form.first_name} onChange={set('first_name')} />
          <input className={input} placeholder="Last name" value={form.last_name} onChange={set('last_name')} />
          <input className={input} type="email" placeholder="Email" value={form.email} onChange={set('email')} />
          <input className={input} placeholder="Phone" value={form.phone} onChange={set('phone')} />
          <input className={input} placeholder="Company" value={form.company} onChange={set('company')} />
          <input className={input} placeholder="Job title" value={form.job_title} onChange={set('job_title')} />
          <select className={input} value={form.source} onChange={set('source')}>
            {['manual', 'web_form', 'referral', 'google_ads', 'facebook_ads', 'cold_call', 'linkedin'].map((s) => (
              <option key={s} value={s}>{s.replace('_', ' ')}</option>
            ))}
          </select>
          <select className={input} value={form.stage_id} onChange={set('stage_id')}>
            <option value="">Stage: New</option>
            {stages.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          {canAssign && (
            <select className={input} value={form.owner_id} onChange={set('owner_id')}>
              <option value="">Assign to me</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          )}
          <input className={input} type="number" min="0" placeholder="Deal value (₹)" value={form.value} onChange={set('value')} />
          <textarea className={`${input} col-span-2`} rows={3} placeholder="Notes" value={form.notes} onChange={set('notes')} />
          {error && <div className="col-span-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
          <div className="col-span-2 flex justify-end gap-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">
              Cancel
            </button>
            <button disabled={busy} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
              {busy ? 'Saving…' : 'Save Lead'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
