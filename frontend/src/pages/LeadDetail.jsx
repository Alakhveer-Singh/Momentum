import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'
import LeadFormModal from '../components/LeadFormModal.jsx'

const inr = (n) => '₹' + Number(n).toLocaleString('en-IN')
const icons = { call: '📞', email: '✉️', meeting: '🤝', note: '📝', stage_change: '🔁', task: '✅', system: '⚙️' }

export default function LeadDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [lead, setLead] = useState(null)
  const [stages, setStages] = useState([])
  const [templates, setTemplates] = useState([])
  const [editing, setEditing] = useState(false)
  const [activity, setActivity] = useState({ type: 'call', subject: '', description: '' })
  const [templateId, setTemplateId] = useState('')

  const load = () => client.get(`leads/${id}`).then((r) => setLead(r.data)).catch(() => navigate('/leads'))

  useEffect(() => {
    load()
    client.get('stages').then((r) => setStages(r.data))
    client.get('email-templates').then((r) => setTemplates(r.data))
  }, [id])

  if (!lead) return <div className="text-slate-500">Loading lead…</div>

  const changeStage = async (stageId) => {
    await client.put(`leads/${id}`, { stage_id: stageId })
    load()
  }

  const logActivity = async (e) => {
    e.preventDefault()
    if (!activity.subject) return
    await client.post('activities', { ...activity, lead_id: lead.id })
    setActivity({ type: 'call', subject: '', description: '' })
    load()
  }

  const sendTemplate = async () => {
    if (!templateId) return
    const res = await client.post('emails/send', { template_id: Number(templateId), lead_ids: [lead.id] })
    alert(res.data.message)
    setTemplateId('')
    load()
  }

  const deleteLead = async () => {
    if (!confirm(`Delete lead ${lead.full_name}? This cannot be undone.`)) return
    await client.delete(`leads/${id}`)
    navigate('/leads')
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/leads" className="text-sm text-indigo-600 hover:underline">← Back to leads</Link>
          <h1 className="text-2xl font-bold">{lead.full_name}</h1>
          <div className="text-slate-500">
            {lead.job_title} {lead.job_title && lead.company && '·'} {lead.company}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setEditing(true)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50">
            ✏️ Edit
          </button>
          {user.role !== 'rep' && (
            <button onClick={deleteLead} className="rounded-lg border border-red-200 bg-white px-3 py-2 text-sm text-red-600 hover:bg-red-50">
              🗑 Delete
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Profile card */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="font-semibold">Details</span>
              <span
                className={`rounded-full px-2.5 py-1 text-sm font-bold ${
                  lead.score >= 60 ? 'bg-emerald-100 text-emerald-700' : lead.score >= 30 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
                }`}
              >
                ★ {lead.score}/100
              </span>
            </div>
            <dl className="space-y-2 text-sm">
              {[
                ['Email', lead.email],
                ['Phone', lead.phone],
                ['Source', lead.source?.replace('_', ' ')],
                ['Owner', lead.owner?.name],
                ['Deal value', inr(lead.value)],
                ['Created', new Date(lead.created_at).toLocaleDateString()],
                ['Last activity', lead.last_activity_at ? new Date(lead.last_activity_at).toLocaleString() : '—'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <dt className="text-slate-400">{k}</dt>
                  <dd className="text-right font-medium capitalize">{v || '—'}</dd>
                </div>
              ))}
              {lead.custom_fields &&
                Object.entries(lead.custom_fields).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2">
                    <dt className="capitalize text-slate-400">{k.replace('_', ' ')}</dt>
                    <dd className="text-right font-medium">{String(v) === 'true' ? 'Yes' : String(v) === 'false' ? 'No' : String(v)}</dd>
                  </div>
                ))}
            </dl>
            {lead.notes && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">{lead.notes}</p>}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 font-semibold">Stage</div>
            <div className="flex flex-wrap gap-1.5">
              {stages.map((s) => (
                <button
                  key={s.id}
                  onClick={() => changeStage(s.id)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                    lead.stage_id === s.id ? 'text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                  }`}
                  style={lead.stage_id === s.id ? { background: s.color } : {}}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 font-semibold">Send Email Template</div>
            <div className="flex gap-2">
              <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="flex-1 rounded-lg border border-slate-300 px-2 py-1.5 text-sm">
                <option value="">Choose template…</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              <button onClick={sendTemplate} disabled={!templateId || !lead.email} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-40">
                Send
              </button>
            </div>
            {!lead.email && <div className="mt-1 text-xs text-amber-600">Lead has no email address.</div>}
          </div>

          {lead.tasks?.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="mb-2 font-semibold">Tasks</div>
              <ul className="space-y-1 text-sm">
                {lead.tasks.map((t) => (
                  <li key={t.id} className="flex justify-between">
                    <span className={t.status === 'completed' ? 'text-slate-400 line-through' : ''}>{t.title}</span>
                    <span className="text-xs text-slate-400">{t.due_at ? new Date(t.due_at).toLocaleDateString() : ''}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Timeline */}
        <div className="lg:col-span-2">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-3 font-semibold">Log Activity</h2>
            <form onSubmit={logActivity} className="mb-5 flex flex-wrap gap-2">
              <select
                value={activity.type}
                onChange={(e) => setActivity((a) => ({ ...a, type: e.target.value }))}
                className="rounded-lg border border-slate-300 px-2 py-2 text-sm"
              >
                <option value="call">📞 Call</option>
                <option value="email">✉️ Email</option>
                <option value="meeting">🤝 Meeting</option>
                <option value="note">📝 Note</option>
              </select>
              <input
                placeholder="Subject *"
                value={activity.subject}
                onChange={(e) => setActivity((a) => ({ ...a, subject: e.target.value }))}
                className="min-w-40 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                placeholder="Details (optional)"
                value={activity.description}
                onChange={(e) => setActivity((a) => ({ ...a, description: e.target.value }))}
                className="min-w-40 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">Log</button>
            </form>

            <h2 className="mb-3 font-semibold">Activity Timeline</h2>
            <ol className="relative space-y-4 border-l border-slate-200 pl-5">
              {lead.activities.map((a) => (
                <li key={a.id} className="relative">
                  <span className="absolute -left-[27px] top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-white text-xs">
                    {icons[a.type] ?? '•'}
                  </span>
                  <div className="text-sm font-medium">{a.subject}</div>
                  {a.description && <div className="text-sm text-slate-500">{a.description}</div>}
                  <div className="text-xs text-slate-400">
                    {a.user?.name ?? 'System'} · {new Date(a.occurred_at).toLocaleString()}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>

      {editing && (
        <LeadFormModal
          lead={lead}
          stages={stages}
          canAssign={user.role !== 'rep'}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false)
            load()
          }}
        />
      )}
    </div>
  )
}
