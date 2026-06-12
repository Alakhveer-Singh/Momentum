import { useEffect, useState } from 'react'
import client from '../api/client'

const empty = { name: '', subject: '', body: '' }

export default function Templates() {
  const [templates, setTemplates] = useState([])
  const [editing, setEditing] = useState(null) // null | 'new' | template
  const [form, setForm] = useState(empty)
  const [bulk, setBulk] = useState(null) // template selected for bulk send
  const [leads, setLeads] = useState([])
  const [selected, setSelected] = useState([])

  const load = () => client.get('email-templates').then((r) => setTemplates(r.data))
  useEffect(() => {
    load()
  }, [])

  const save = async (e) => {
    e.preventDefault()
    if (editing === 'new') await client.post('email-templates', form)
    else await client.put(`email-templates/${editing.id}`, form)
    setEditing(null)
    setForm(empty)
    load()
  }

  const remove = async (t) => {
    if (!confirm(`Delete template "${t.name}"?`)) return
    await client.delete(`email-templates/${t.id}`)
    load()
  }

  const openBulk = async (t) => {
    setBulk(t)
    setSelected([])
    const r = await client.get('leads', { params: { all: 1 } })
    setLeads(r.data.data.filter((l) => l.email))
  }

  const sendBulk = async () => {
    const res = await client.post('emails/send', { template_id: bulk.id, lead_ids: selected })
    alert(res.data.message)
    setBulk(null)
  }

  const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Email Templates</h1>
        <button
          onClick={() => {
            setEditing('new')
            setForm(empty)
          }}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          + New Template
        </button>
      </div>

      <p className="text-sm text-slate-500">
        Placeholders: <code className="rounded bg-slate-200 px-1">{'{{first_name}}'}</code>{' '}
        <code className="rounded bg-slate-200 px-1">{'{{last_name}}'}</code>{' '}
        <code className="rounded bg-slate-200 px-1">{'{{full_name}}'}</code>{' '}
        <code className="rounded bg-slate-200 px-1">{'{{company}}'}</code>{' '}
        <code className="rounded bg-slate-200 px-1">{'{{email}}'}</code>
      </p>

      {editing && (
        <form onSubmit={save} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          <input className={input} required placeholder="Template name *" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          <input className={input} required placeholder="Email subject *" value={form.subject} onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))} />
          <textarea className={input} required rows={6} placeholder="Email body *" value={form.body} onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))} />
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setEditing(null)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Cancel</button>
            <button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">Save</button>
          </div>
        </form>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {templates.map((t) => (
          <div key={t.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-semibold">{t.name}</div>
                <div className="text-sm text-slate-500">{t.subject}</div>
              </div>
              <div className="flex gap-1 text-sm">
                <button onClick={() => openBulk(t)} className="rounded px-2 py-1 text-indigo-600 hover:bg-indigo-50" title="Bulk send">📤</button>
                <button
                  onClick={() => {
                    setEditing(t)
                    setForm({ name: t.name, subject: t.subject, body: t.body })
                  }}
                  className="rounded px-2 py-1 hover:bg-slate-100"
                >
                  ✏️
                </button>
                <button onClick={() => remove(t)} className="rounded px-2 py-1 text-red-500 hover:bg-red-50">🗑</button>
              </div>
            </div>
            <pre className="mt-3 max-h-32 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-600">{t.body}</pre>
          </div>
        ))}
      </div>

      {bulk && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setBulk(null)}>
          <div className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-2xl bg-white p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-1 text-lg font-bold">Bulk send: {bulk.name}</h2>
            <p className="mb-3 text-sm text-slate-500">Select recipients ({selected.length} chosen)</p>
            <label className="mb-2 flex items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                checked={selected.length === leads.length && leads.length > 0}
                onChange={(e) => setSelected(e.target.checked ? leads.map((l) => l.id) : [])}
                className="accent-indigo-600"
              />
              Select all
            </label>
            <div className="max-h-64 space-y-1 overflow-y-auto">
              {leads.map((l) => (
                <label key={l.id} className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-slate-50">
                  <input
                    type="checkbox"
                    checked={selected.includes(l.id)}
                    onChange={(e) => setSelected((s) => (e.target.checked ? [...s, l.id] : s.filter((x) => x !== l.id)))}
                    className="accent-indigo-600"
                  />
                  {l.full_name} <span className="text-xs text-slate-400">{l.email}</span>
                </label>
              ))}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setBulk(null)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Cancel</button>
              <button onClick={sendBulk} disabled={selected.length === 0} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
                Send to {selected.length}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
