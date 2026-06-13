import { useEffect, useRef, useState } from 'react'
import { GripVertical, Pencil, Plus, X, Check } from 'lucide-react'
import client from '../api/client'

const SECTION_LABELS = {
  entry: { label: 'Top', desc: 'First stage all new leads enter' },
  won: { label: 'Bottom', desc: 'Leads that converted successfully' },
  lost: { label: 'Complete', desc: 'Terminal stages — closed without converting' },
}

function FixedStage({ stage }) {
  return (
    <div className="flex items-center gap-3 border-b border-slate-100 py-3 pl-2 text-sm text-slate-700">
      <span className="h-4 w-4" /> {/* spacer for drag handle column */}
      <span
        className="inline-block h-2.5 w-2.5 rounded-full"
        style={{ background: stage.color }}
      />
      {stage.name}
    </div>
  )
}

function EditableStage({ stage, onSave, onDelete, dragHandlers }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(stage.name)
  const inputRef = useRef(null)

  const commit = async () => {
    if (!name.trim() || name.trim() === stage.name) {
      setName(stage.name)
      setEditing(false)
      return
    }
    await onSave(stage.id, name.trim())
    setEditing(false)
  }

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  return (
    <div
      className="flex items-center gap-3 border-b border-slate-100 py-3 text-sm"
      {...dragHandlers}
    >
      <GripVertical className="h-4 w-4 shrink-0 cursor-grab text-slate-300" />
      <span
        className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
        style={{ background: stage.color }}
      />
      {editing ? (
        <input
          ref={inputRef}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { setName(stage.name); setEditing(false) } }}
          className="flex-1 rounded border border-indigo-400 px-2 py-0.5 text-sm focus:outline-none"
        />
      ) : (
        <span className="flex-1 text-indigo-600">{stage.name}</span>
      )}
      <div className="flex items-center gap-1">
        {editing ? (
          <button onClick={commit} className="rounded p-1 text-emerald-600 hover:bg-emerald-50">
            <Check className="h-3.5 w-3.5" />
          </button>
        ) : (
          <button onClick={() => setEditing(true)} className="rounded p-1 text-slate-400 hover:bg-slate-100">
            <Pencil className="h-3.5 w-3.5" />
          </button>
        )}
        <button onClick={() => onDelete(stage)} className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-500">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

export default function FunnelSettings() {
  const [stages, setStages] = useState([])
  const [newName, setNewName] = useState('')
  const [adding, setAdding] = useState(false)
  const [dragId, setDragId] = useState(null)
  const [dragOverId, setDragOverId] = useState(null)

  const load = () => client.get('stages').then((r) => setStages(r.data))
  useEffect(() => { load() }, [])

  const byType = (type) => stages.filter((s) => s.stage_type === type)
  const middle = stages.filter((s) => s.stage_type === 'middle')

  const saveRename = async (id, name) => {
    await client.patch(`stages/${id}`, { name })
    setStages((ss) => ss.map((s) => (s.id === id ? { ...s, name } : s)))
  }

  const deleteStage = async (stage) => {
    if (!window.confirm(`Delete "${stage.name}"? Leads in this stage will move to the entry stage.`)) return
    await client.delete(`stages/${stage.id}/delete`)
    setStages((ss) => ss.filter((s) => s.id !== stage.id))
  }

  const addStage = async () => {
    if (!newName.trim()) return
    const r = await client.post('stages/create', { name: newName.trim() })
    setStages((ss) => [...ss, r.data])
    setNewName('')
    setAdding(false)
  }

  // drag-drop reorder (middle stages only)
  const drop = async (targetId) => {
    if (!dragId || dragId === targetId) return setDragId(null)
    const reordered = [...middle]
    const fromIdx = reordered.findIndex((s) => s.id === dragId)
    const toIdx = reordered.findIndex((s) => s.id === targetId)
    const [moved] = reordered.splice(fromIdx, 1)
    reordered.splice(toIdx, 0, moved)
    setStages((ss) => {
      const nonMiddle = ss.filter((s) => s.stage_type !== 'middle')
      return [...nonMiddle, ...reordered].sort((a, b) => {
        const order = { entry: 0, middle: 1, won: 2, lost: 3 }
        return order[a.stage_type] - order[b.stage_type] || a.position - b.position
      })
    })
    setDragId(null)
    setDragOverId(null)
    await client.post('stages/reorder', { ids: reordered.map((s) => s.id) })
  }

  const renderSection = (type, stages_in_type) => {
    const info = SECTION_LABELS[type]
    return (
      <div key={type} className="mb-6">
        <div className="mb-2 flex items-center gap-2">
          <div className="flex flex-col gap-0.5">
            <span className="h-1 w-5 rounded bg-slate-400" />
            <span className="h-1 w-5 rounded bg-slate-400" />
            <span className="h-1 w-3 rounded bg-slate-400" />
          </div>
          <span className="text-sm font-semibold text-slate-600">{info.label}</span>
        </div>
        {stages_in_type.map((s) => (
          <FixedStage key={s.id} stage={s} />
        ))}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-xl space-y-2">
      <div className="mb-6">
        <h1 className="text-xl font-bold">Lead funnel</h1>
        <p className="mt-1 text-sm text-slate-500">
          Customize the lead funnel by creating, deleting, rearranging or renaming stages.
        </p>
      </div>

      {/* Top / Entry */}
      <div className="mb-2 flex items-center gap-2">
        <div className="flex flex-col gap-0.5">
          <span className="h-1 w-5 rounded bg-slate-400" />
          <span className="h-1 w-5 rounded bg-slate-400" />
          <span className="h-1 w-3 rounded bg-slate-400" />
        </div>
        <span className="text-sm font-semibold text-slate-600">Top</span>
      </div>
      {byType('entry').map((s) => <FixedStage key={s.id} stage={s} />)}

      {/* Middle (editable) */}
      <div className="my-6">
        <div className="mb-2 flex items-center gap-2">
          <div className="flex flex-col gap-0.5">
            <span className="h-1 w-5 rounded bg-slate-400" />
            <span className="h-1 w-5 rounded bg-slate-400" />
            <span className="h-1 w-3 rounded bg-slate-400" />
          </div>
          <span className="text-sm font-semibold text-slate-600">Middle</span>
        </div>

        {middle.map((stage) => (
          <div
            key={stage.id}
            className={`transition-opacity ${dragId === stage.id ? 'opacity-40' : ''} ${dragOverId === stage.id ? 'border-t-2 border-indigo-400' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOverId(stage.id) }}
            onDrop={() => drop(stage.id)}
          >
            <EditableStage
              stage={stage}
              onSave={saveRename}
              onDelete={deleteStage}
              dragHandlers={{
                draggable: true,
                onDragStart: () => setDragId(stage.id),
                onDragEnd: () => { setDragId(null); setDragOverId(null) },
              }}
            />
          </div>
        ))}

        {/* Add stage row */}
        {adding ? (
          <div className="flex items-center gap-2 border-b border-slate-100 py-3 pl-7">
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') addStage(); if (e.key === 'Escape') { setAdding(false); setNewName('') } }}
              placeholder="Stage name…"
              className="flex-1 rounded border border-indigo-400 px-2 py-1 text-sm focus:outline-none"
            />
            <button onClick={addStage} className="rounded p-1 text-emerald-600 hover:bg-emerald-50">
              <Check className="h-4 w-4" />
            </button>
            <button onClick={() => { setAdding(false); setNewName('') }} className="rounded p-1 text-slate-400 hover:bg-slate-100">
              <X className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-indigo-600 hover:bg-indigo-50"
          >
            <Plus className="h-4 w-4" /> Add stage
          </button>
        )}
      </div>

      {/* Bottom / Won */}
      {renderSection('won', byType('won'))}

      {/* Complete / Lost */}
      {renderSection('lost', byType('lost'))}
    </div>
  )
}
