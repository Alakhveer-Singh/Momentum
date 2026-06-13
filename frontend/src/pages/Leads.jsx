import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, Download, MoreHorizontal, Plus, Search, Upload } from 'lucide-react'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'
import LeadFormModal from '../components/LeadFormModal.jsx'

const inr = (n) => '₹' + Number(n).toLocaleString('en-IN')

function StageTabBar({ stages, stageCounts, unreadCount, activeTab, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const OVERFLOW_AT = 5

  const stageItems = stages.map((s) => ({
    id: String(s.id),
    label: s.name,
    count: stageCounts[s.id] ?? 0,
  }))

  const overflow = !expanded && stageItems.length > OVERFLOW_AT
  const visibleStages = overflow ? stageItems.slice(0, OVERFLOW_AT) : stageItems

  const tabCls = (id) =>
    `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
      activeTab === id
        ? 'bg-white shadow-sm ring-1 ring-inset ring-indigo-400 text-indigo-600'
        : 'text-slate-600 hover:bg-white hover:text-slate-900'
    }`

  return (
    <div className="flex items-center gap-0 overflow-x-auto rounded-xl bg-slate-100 p-1 scrollbar-none">
      <button onClick={() => onSelect('')} className={tabCls('')}>
        All
      </button>

      <div className="mx-2 h-5 w-px shrink-0 bg-slate-300" />

      <button onClick={() => onSelect('unread')} className={tabCls('unread')}>
        Unread
        {unreadCount > 0 && (
          <span className="ml-1.5 text-xs font-normal text-slate-400">{unreadCount}</span>
        )}
      </button>

      {visibleStages.map((stage) => (
        <div key={stage.id} className="flex shrink-0 items-center">
          <ChevronRight className="mx-0.5 h-3 w-3 shrink-0 text-slate-400" />
          <button onClick={() => onSelect(stage.id)} className={tabCls(stage.id)}>
            {stage.label}
            <span className="ml-1.5 text-xs font-normal text-slate-400">{stage.count}</span>
          </button>
        </div>
      ))}

      {stageItems.length > OVERFLOW_AT && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="ml-1 shrink-0 rounded-lg p-1.5 text-slate-400 transition hover:bg-white hover:text-slate-600"
          title={expanded ? 'Show fewer' : 'Show all stages'}
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}

export default function Leads() {
  const { user } = useAuth()
  const [page, setPage] = useState(null)
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState('')
  const [source, setSource] = useState('')
  const [stages, setStages] = useState([])
  const [stageCounts, setStageCounts] = useState({})
  const [unreadCount, setUnreadCount] = useState(0)
  const [showForm, setShowForm] = useState(false)
  const [importing, setImporting] = useState(false)
  const fileRef = useRef(null)

  const load = (p = 1) => {
    const params = { page: p, search: search || undefined, source: source || undefined }
    if (activeTab === 'unread') {
      params.unread = '1'
    } else if (activeTab !== '') {
      params.stage_id = activeTab
    }
    client.get('leads', { params }).then((r) => setPage(r.data))
  }

  const refreshCounts = () => {
    client.get('reports/pipeline').then((r) => {
      const counts = {}
      r.data.forEach((s) => { counts[s.id] = s.leads_count })
      setStageCounts(counts)
    })
    client.get('leads', { params: { unread: '1', per_page: 1 } }).then((r) => {
      setUnreadCount(r.data.total ?? 0)
    })
  }

  useEffect(() => {
    client.get('stages').then((r) => setStages(r.data))
    refreshCounts()
  }, [])

  useEffect(() => {
    const t = setTimeout(() => load(1), 300)
    return () => clearTimeout(t)
  }, [search, activeTab, source])

  const exportCsv = async () => {
    const res = await client.get('exports/leads.csv', { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'leads.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const importCsv = async (file) => {
    setImporting(true)
    try {
      const text = await file.text()
      const [header, ...rows] = text.trim().split(/\r?\n/)
      const cols = header.split(',').map((c) => c.trim().toLowerCase().replace(/\s+/g, '_'))
      const leads = rows.map((row) => {
        const vals = row.split(',')
        return Object.fromEntries(cols.map((c, i) => [c, vals[i]?.trim()]).filter(([, v]) => v))
      })
      const res = await client.post('leads-import', { leads })
      alert(res.data.message)
      load(1)
      refreshCounts()
    } catch (err) {
      alert(err.response?.data?.message || 'Import failed. Expected CSV with first_name,last_name,email,phone,company columns.')
    } finally {
      setImporting(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold">Leads</h1>
        <div className="flex flex-wrap gap-2">
          <button onClick={exportCsv} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50">
            <Download className="h-4 w-4" /> Export CSV
          </button>
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50">
            <Upload className="h-4 w-4" /> {importing ? 'Importing…' : 'Import CSV'}
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files[0] && importCsv(e.target.files[0])} />
          </label>
          <button onClick={() => setShowForm(true)} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
            <Plus className="h-4 w-4" /> New Lead
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            placeholder="Search name, email, company…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64 rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm focus:border-indigo-500 focus:outline-none"
          />
        </div>
        <select value={source} onChange={(e) => setSource(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          <option value="">All sources</option>
          {['web_form', 'referral', 'google_ads', 'facebook_ads', 'cold_call', 'linkedin', 'manual', 'import'].map((s) => (
            <option key={s} value={s}>{s.replace('_', ' ')}</option>
          ))}
        </select>
      </div>

      <StageTabBar
        stages={stages}
        stageCounts={stageCounts}
        unreadCount={unreadCount}
        activeTab={activeTab}
        onSelect={setActiveTab}
      />

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Company</th>
              <th className="hidden px-4 py-3 md:table-cell">Source</th>
              <th className="px-4 py-3">Stage</th>
              <th className="hidden px-4 py-3 md:table-cell">Owner</th>
              <th className="px-4 py-3 text-right">Score</th>
              <th className="px-4 py-3 text-right">Value</th>
            </tr>
          </thead>
          <tbody>
            {page?.data.map((lead) => (
              <tr key={lead.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link to={`/leads/${lead.id}`} className="font-medium text-indigo-600 hover:underline">
                    {lead.full_name}
                  </Link>
                  <div className="text-xs text-slate-400">{lead.email}</div>
                </td>
                <td className="px-4 py-3">{lead.company}</td>
                <td className="hidden px-4 py-3 capitalize md:table-cell">{lead.source?.replace('_', ' ')}</td>
                <td className="px-4 py-3">
                  <span className="rounded-full px-2 py-0.5 text-xs font-medium text-white" style={{ background: lead.stage?.color }}>
                    {lead.stage?.name}
                  </span>
                </td>
                <td className="hidden px-4 py-3 md:table-cell">{lead.owner?.name}</td>
                <td className="px-4 py-3 text-right font-semibold">{lead.score}</td>
                <td className="px-4 py-3 text-right">{inr(lead.value)}</td>
              </tr>
            ))}
            {page?.data.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">No leads found.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {page && page.last_page > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">
            {page.from}–{page.to} of {page.total}
          </span>
          <div className="flex gap-2">
            <button disabled={page.current_page === 1} onClick={() => load(page.current_page - 1)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">
              Previous
            </button>
            <button disabled={page.current_page === page.last_page} onClick={() => load(page.current_page + 1)} className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">
              Next
            </button>
          </div>
        </div>
      )}

      {showForm && (
        <LeadFormModal
          stages={stages}
          canAssign={user.role !== 'rep'}
          onClose={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false)
            load(1)
            refreshCounts()
          }}
        />
      )}
    </div>
  )
}
