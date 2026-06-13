import { useEffect, useState } from 'react'
import { Plus, X } from 'lucide-react'
import client from '../api/client'

const PROFILES = ['Student', 'Fresher', 'Working Professional', 'Business Owner', 'Home Maker']
const EDUCATION = ['XII', 'UnderGraduate', 'Graduate', 'Post Graduate', 'PHD']
const SOURCES = [
  { value: 'web_form', label: 'Web form' },
  { value: 'referral', label: 'Referral' },
  { value: 'google_ads', label: 'Google ads' },
  { value: 'facebook_ads', label: 'Facebook ads' },
  { value: 'cold_call', label: 'Cold call' },
]

const cf = (lead, key) => lead?.custom_fields?.[key] ?? ''

export default function LeadFormModal({ lead, stages, canAssign, onClose, onSaved }) {
  const [form, setForm] = useState({
    first_name: lead?.first_name ?? '',
    last_name: lead?.last_name ?? '',
    email: lead?.email ?? '',
    phone: lead?.phone ?? '',
    city: cf(lead, 'city'),
    location: cf(lead, 'location'),
    current_profile: cf(lead, 'current_profile'),
    highest_education: cf(lead, 'highest_education'),
    notes: lead?.notes ?? cf(lead, 'notes'),
    source: lead?.source ?? '',
    stage_id: lead?.stage_id ?? '',
    owner_id: lead?.owner_id ?? '',
    value: lead?.value ?? '',
  })
  const [extraPhones, setExtraPhones] = useState(lead?.custom_fields?.extra_phones ?? [])
  const [whatsapp, setWhatsapp] = useState(cf(lead, 'whatsapp'))
  const [waSameAsMobile, setWaSameAsMobile] = useState(
    !!lead?.phone && lead?.phone === cf(lead, 'whatsapp')
  )
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (canAssign) client.get('users').then((r) => setUsers(r.data.data ?? r.data)).catch(() => {})
  }, [canAssign])

  useEffect(() => {
    if (waSameAsMobile) setWhatsapp(form.phone)
  }, [waSameAsMobile, form.phone])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const addPhone = () => setExtraPhones((p) => [...p, ''])
  const setPhone = (i, val) => setExtraPhones((p) => p.map((v, idx) => (idx === i ? val : v)))
  const removePhone = (i) => setExtraPhones((p) => p.filter((_, idx) => idx !== i))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    const custom_fields = {
      city: form.city,
      location: form.location || undefined,
      current_profile: form.current_profile,
      highest_education: form.highest_education || undefined,
      whatsapp: whatsapp || undefined,
      extra_phones: extraPhones.filter(Boolean).length ? extraPhones.filter(Boolean) : undefined,
      notes: form.notes || undefined,
    }
    // strip undefined keys
    Object.keys(custom_fields).forEach((k) => custom_fields[k] === undefined && delete custom_fields[k])

    const payload = {
      first_name: form.first_name,
      last_name: form.last_name,
      email: form.email || undefined,
      phone: form.phone,
      source: form.source,
      custom_fields,
    }
    if (form.stage_id) payload.stage_id = form.stage_id
    if (form.owner_id) payload.owner_id = form.owner_id
    if (form.value) payload.value = form.value
    Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k])

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

  const inp = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none'
  const label = 'block text-xs font-medium text-slate-500 mb-1'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-5 text-lg font-bold">{lead ? 'Edit Lead' : 'New Lead'}</h2>
        <form onSubmit={submit} className="space-y-4">

          {/* Name row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={label}>First Name <span className="text-red-500">*</span></label>
              <input className={inp} required value={form.first_name} onChange={set('first_name')} placeholder="First name" />
            </div>
            <div>
              <label className={label}>Last Name <span className="text-red-500">*</span></label>
              <input className={inp} required value={form.last_name} onChange={set('last_name')} placeholder="Last name" />
            </div>
          </div>

          {/* Mobile No. (multiple) */}
          <div>
            <label className={label}>Mobile No. <span className="text-red-500">*</span></label>
            <input
              className={inp}
              required
              type="tel"
              value={form.phone}
              onChange={set('phone')}
              placeholder="+91 9876543210"
            />
            {extraPhones.map((ph, i) => (
              <div key={i} className="mt-2 flex gap-2">
                <input
                  className={inp}
                  type="tel"
                  value={ph}
                  onChange={(e) => setPhone(i, e.target.value)}
                  placeholder={`Additional mobile ${i + 2}`}
                />
                <button type="button" onClick={() => removePhone(i)} className="shrink-0 rounded-lg p-2 text-red-400 hover:bg-red-50">
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={addPhone}
              className="mt-2 inline-flex items-center gap-1 text-xs text-indigo-600 hover:underline"
            >
              <Plus className="h-3 w-3" /> Add another number
            </button>
          </div>

          {/* WhatsApp */}
          <div>
            <label className={label}>WhatsApp No. <span className="text-red-500">*</span></label>
            <label className="mb-2 flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={waSameAsMobile}
                onChange={(e) => setWaSameAsMobile(e.target.checked)}
                className="rounded"
              />
              Same as mobile number
            </label>
            {!waSameAsMobile && (
              <input
                className={inp}
                required={!waSameAsMobile}
                type="tel"
                value={whatsapp}
                onChange={(e) => setWhatsapp(e.target.value)}
                placeholder="+91 9876543210"
              />
            )}
            {waSameAsMobile && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
                {form.phone || '—'}
              </div>
            )}
          </div>

          {/* Email */}
          <div>
            <label className={label}>Email Id</label>
            <input className={inp} type="email" value={form.email} onChange={set('email')} placeholder="email@example.com" />
          </div>

          {/* City + Location */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={label}>City <span className="text-red-500">*</span></label>
              <input className={inp} required value={form.city} onChange={set('city')} placeholder="e.g. Mumbai" />
            </div>
            <div>
              <label className={label}>Location</label>
              <input className={inp} value={form.location} onChange={set('location')} placeholder="Area / Locality" />
            </div>
          </div>

          {/* Current Profile */}
          <div>
            <label className={label}>Current Profile <span className="text-red-500">*</span></label>
            <select className={inp} required value={form.current_profile} onChange={set('current_profile')}>
              <option value="">Select profile…</option>
              {PROFILES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>

          {/* Highest Education */}
          <div>
            <label className={label}>Highest Education</label>
            <select className={inp} value={form.highest_education} onChange={set('highest_education')}>
              <option value="">Select education…</option>
              {EDUCATION.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
          </div>

          {/* Notes */}
          <div>
            <label className={label}>Notes</label>
            <textarea className={inp} rows={3} value={form.notes} onChange={set('notes')} placeholder="Any additional notes…" />
          </div>

          {/* Source + Stage */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={label}>Source <span className="text-red-500">*</span></label>
              <select className={inp} required value={form.source} onChange={set('source')}>
                <option value="">Select source…</option>
                {SOURCES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className={label}>Stage <span className="text-red-500">*</span></label>
              <select className={inp} required value={form.stage_id} onChange={set('stage_id')}>
                <option value="">Select stage…</option>
                {stages.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>

          {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50">
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
