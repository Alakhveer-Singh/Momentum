import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Star, User } from 'lucide-react'
import client from '../api/client'

const inr = (n) => '₹' + Number(n).toLocaleString('en-IN')

export default function Pipeline() {
  const [stages, setStages] = useState([])
  const [leads, setLeads] = useState([])
  const [dragId, setDragId] = useState(null)

  const load = () => {
    client.get('stages').then((r) => setStages(r.data))
    client.get('leads', { params: { all: 1 } }).then((r) => setLeads(r.data.data))
  }

  useEffect(() => {
    load()
    window.addEventListener('lead-updated', load)
    return () => window.removeEventListener('lead-updated', load)
  }, [])

  const drop = async (stageId) => {
    if (!dragId) return
    const lead = leads.find((l) => l.id === dragId)
    if (!lead || lead.stage_id === stageId) return setDragId(null)

    // optimistic update
    setLeads((ls) => ls.map((l) => (l.id === dragId ? { ...l, stage_id: stageId } : l)))
    setDragId(null)
    try {
      await client.put(`leads/${dragId}`, { stage_id: stageId })
    } catch {
      load() // revert on failure
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">Pipeline</h1>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {stages.map((stage) => {
          const stageLeads = leads.filter((l) => l.stage_id === stage.id)
          return (
            <div
              key={stage.id}
              className="w-72 flex-shrink-0 rounded-xl bg-slate-200/60 p-3"
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => drop(stage.id)}
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full" style={{ background: stage.color }} />
                  <span className="font-semibold">{stage.name}</span>
                  <span className="text-sm text-slate-500">({stageLeads.length})</span>
                </div>
                <span className="text-xs text-slate-500">{inr(stageLeads.reduce((s, l) => s + Number(l.value), 0))}</span>
              </div>
              <div className="space-y-2">
                {stageLeads.map((lead) => (
                  <div
                    key={lead.id}
                    draggable
                    onDragStart={() => setDragId(lead.id)}
                    className={`cursor-grab rounded-lg border border-slate-200 bg-white p-3 shadow-sm transition hover:shadow ${
                      dragId === lead.id ? 'opacity-50' : ''
                    }`}
                  >
                    <Link to={`/leads/${lead.id}`} className="font-medium text-slate-800 hover:text-indigo-600">
                      {lead.full_name}
                    </Link>
                    <div className="text-xs text-slate-500">{lead.company}</div>
                    <div className="mt-2 flex items-center justify-between text-xs">
                      <span className="font-semibold text-indigo-600">{inr(lead.value)}</span>
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ${
                          lead.score >= 60 ? 'bg-emerald-100 text-emerald-700' : lead.score >= 30 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
                        }`}
                        title="Lead score"
                      >
                        <Star className="h-3 w-3 fill-current" /> {lead.score}
                      </span>
                    </div>
                    {lead.owner && (
                      <div className="mt-1 flex items-center gap-1 text-xs text-slate-400">
                        <User className="h-3 w-3" /> {lead.owner.name}
                      </div>
                    )}
                  </div>
                ))}
                {stageLeads.length === 0 && (
                  <div className="rounded-lg border border-dashed border-slate-300 p-3 text-center text-xs text-slate-400">
                    Drop leads here
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
