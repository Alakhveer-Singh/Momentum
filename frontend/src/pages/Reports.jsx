import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'

const inr = (n) => '₹' + Number(n).toLocaleString('en-IN')

function Bar({ pct, color = 'bg-indigo-500' }) {
  return (
    <div className="h-2 w-full rounded-full bg-slate-100">
      <div className={`h-2 rounded-full ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  )
}

export default function Reports() {
  const { user } = useAuth()
  const isManager = user.role !== 'rep'
  const [pipeline, setPipeline] = useState([])
  const [sources, setSources] = useState([])
  const [team, setTeam] = useState([])
  const [trend, setTrend] = useState([])

  useEffect(() => {
    client.get('reports/pipeline').then((r) => setPipeline(r.data))
    client.get('reports/trend').then((r) => setTrend(r.data))
    if (isManager) {
      client.get('reports/sources').then((r) => setSources(r.data))
      client.get('reports/team').then((r) => setTeam(r.data))
    }
  }, [isManager])

  const exportPdf = async () => {
    const res = await client.get('exports/pipeline.pdf', { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'pipeline-report.pdf'
    a.click()
    URL.revokeObjectURL(url)
  }

  const maxStage = Math.max(...pipeline.map((s) => s.leads_count), 1)
  const maxTrend = Math.max(...trend.map((t) => t.leads), 1)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Reports & Analytics</h1>
        <button onClick={exportPdf} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50">
          <Download className="h-4 w-4" /> Pipeline PDF
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-4 font-semibold">Pipeline by Stage</h2>
          <div className="space-y-3">
            {pipeline.map((s) => (
              <div key={s.id}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="font-medium">{s.name}</span>
                  <span className="text-slate-500">
                    {s.leads_count} leads · {inr(s.total_value)}
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100">
                  <div className="h-2 rounded-full" style={{ width: `${(s.leads_count / maxStage) * 100}%`, background: s.color }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-4 font-semibold">Lead Volume (6 months)</h2>
          <div className="flex h-48 items-end gap-2">
            {trend.map((t) => (
              <div key={t.month} className="flex flex-1 flex-col items-center gap-1">
                <div className="flex w-full flex-1 items-end justify-center gap-1">
                  <div className="w-1/3 rounded-t bg-indigo-500" style={{ height: `${(t.leads / maxTrend) * 100}%` }} title={`${t.leads} leads`} />
                  <div className="w-1/3 rounded-t bg-emerald-500" style={{ height: `${(t.won / maxTrend) * 100}%` }} title={`${t.won} won`} />
                </div>
                <span className="text-xs text-slate-400">{t.month.slice(5)}</span>
              </div>
            ))}
            {trend.length === 0 && <div className="text-sm text-slate-400">No data yet.</div>}
          </div>
          <div className="mt-2 flex gap-4 text-xs text-slate-500">
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-indigo-500" />New leads</span>
            <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500" />Won</span>
          </div>
        </div>

        {isManager && (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-4 font-semibold">Lead Source ROI</h2>
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-slate-400">
                <tr>
                  <th className="pb-2">Source</th>
                  <th className="pb-2 text-right">Leads</th>
                  <th className="pb-2 text-right">Won</th>
                  <th className="pb-2 text-right">Conv.</th>
                  <th className="pb-2 text-right">Won Value</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.source} className="border-t border-slate-100">
                    <td className="py-2 capitalize">{s.source.replace('_', ' ')}</td>
                    <td className="py-2 text-right">{s.total}</td>
                    <td className="py-2 text-right">{s.won}</td>
                    <td className="py-2 text-right">{s.conversion_rate}%</td>
                    <td className="py-2 text-right">{inr(s.won_value ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {isManager && (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-4 font-semibold">Team Performance</h2>
            <div className="space-y-4">
              {team.map((m) => (
                <div key={m.id}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="font-medium">
                      {m.name} <span className="text-xs capitalize text-slate-400">({m.role})</span>
                    </span>
                    <span className="text-slate-500">
                      {m.won_leads}/{m.total_leads} won · {inr(m.won_value)} · {m.activities_30d} activities/30d
                    </span>
                  </div>
                  <Bar pct={m.total_leads ? (m.won_leads / m.total_leads) * 100 : 0} color="bg-emerald-500" />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
