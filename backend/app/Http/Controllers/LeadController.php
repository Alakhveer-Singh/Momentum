<?php

namespace App\Http\Controllers;

use App\Events\LeadUpdated;
use App\Models\Activity;
use App\Models\Lead;
use App\Models\PipelineStage;
use App\Services\LeadScoringService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class LeadController extends Controller
{
    public function __construct(private LeadScoringService $scoring)
    {
    }

    public function index(Request $request): JsonResponse
    {
        $query = Lead::with(['stage', 'owner'])
            ->withCount(['activities', 'tasks']);

        // Reps see only their own leads
        if ($request->user()->role === 'rep') {
            $query->where('owner_id', $request->user()->id);
        }

        if ($search = $request->query('search')) {
            $query->where(function ($q) use ($search) {
                $q->where('first_name', 'like', "%{$search}%")
                    ->orWhere('last_name', 'like', "%{$search}%")
                    ->orWhere('email', 'like', "%{$search}%")
                    ->orWhere('company', 'like', "%{$search}%");
            });
        }

        if ($stage = $request->query('stage_id')) {
            $query->where('stage_id', $stage);
        }
        if ($source = $request->query('source')) {
            $query->where('source', $source);
        }
        if ($owner = $request->query('owner_id')) {
            $query->where('owner_id', $owner);
        }

        $sort = in_array($request->query('sort'), ['created_at', 'score', 'value', 'last_activity_at'])
            ? $request->query('sort') : 'created_at';
        $query->orderBy($sort, $request->query('direction') === 'asc' ? 'asc' : 'desc');

        if ($request->boolean('all')) {
            return response()->json(['data' => $query->get()]);
        }

        return response()->json($query->paginate($request->integer('per_page', 25)));
    }

    public function store(Request $request): JsonResponse
    {
        $data = $this->validatePayload($request);
        $data['stage_id'] = $data['stage_id'] ?? PipelineStage::where('slug', 'new')->value('id');
        $data['owner_id'] = $data['owner_id'] ?? $request->user()->id;

        $lead = Lead::create($data);

        Activity::create([
            'lead_id' => $lead->id,
            'user_id' => $request->user()->id,
            'type' => 'system',
            'subject' => 'Lead created manually',
        ]);

        $lead->update(['last_activity_at' => now()]);
        $this->scoring->recalculate($lead);

        $lead->load(['stage', 'owner']);
        LeadUpdated::dispatch($lead, 'created');

        return response()->json($lead, 201);
    }

    public function show(Request $request, Lead $lead): JsonResponse
    {
        $this->authorizeAccess($request, $lead);

        return response()->json(
            $lead->load(['stage', 'owner', 'activities.user', 'tasks.assignee'])
        );
    }

    public function update(Request $request, Lead $lead): JsonResponse
    {
        $this->authorizeAccess($request, $lead);

        $data = $this->validatePayload($request, updating: true);

        $oldStageId = $lead->stage_id;
        $lead->update($data);

        // Log stage transitions as activities
        if (isset($data['stage_id']) && (int) $data['stage_id'] !== (int) $oldStageId) {
            $newStage = PipelineStage::find($data['stage_id']);
            $oldStage = PipelineStage::find($oldStageId);

            Activity::create([
                'lead_id' => $lead->id,
                'user_id' => $request->user()->id,
                'type' => 'stage_change',
                'subject' => "Stage changed: {$oldStage->name} → {$newStage->name}",
                'metadata' => ['from' => $oldStage->id, 'to' => $newStage->id],
            ]);

            $lead->update([
                'last_activity_at' => now(),
                'converted_at' => $newStage->is_won ? now() : null,
            ]);
        }

        $this->scoring->recalculate($lead);

        $lead->refresh()->load(['stage', 'owner']);
        LeadUpdated::dispatch($lead, 'updated');

        return response()->json($lead);
    }

    public function destroy(Request $request, Lead $lead): JsonResponse
    {
        if (! $request->user()->isManager()) {
            return response()->json(['message' => 'Forbidden.'], 403);
        }

        $lead->delete();
        LeadUpdated::dispatch($lead, 'deleted');

        return response()->json(['message' => 'Lead deleted.']);
    }

    public function bulkImport(Request $request): JsonResponse
    {
        $request->validate([
            'leads' => ['required', 'array', 'min:1', 'max:1000'],
            'leads.*.first_name' => ['required', 'string', 'max:255'],
            'leads.*.email' => ['nullable', 'email'],
        ]);

        $defaultStage = PipelineStage::where('slug', 'new')->value('id');
        $created = 0;

        foreach ($request->input('leads') as $row) {
            $lead = Lead::create([
                'first_name' => $row['first_name'],
                'last_name' => $row['last_name'] ?? null,
                'email' => $row['email'] ?? null,
                'phone' => $row['phone'] ?? null,
                'company' => $row['company'] ?? null,
                'job_title' => $row['job_title'] ?? null,
                'source' => $row['source'] ?? 'import',
                'value' => $row['value'] ?? 0,
                'stage_id' => $defaultStage,
                'owner_id' => $row['owner_id'] ?? $request->user()->id,
            ]);

            Activity::create([
                'lead_id' => $lead->id,
                'user_id' => $request->user()->id,
                'type' => 'system',
                'subject' => 'Lead imported (bulk)',
            ]);

            $this->scoring->recalculate($lead);
            $created++;
        }

        return response()->json(['message' => "{$created} leads imported.", 'count' => $created], 201);
    }

    private function validatePayload(Request $request, bool $updating = false): array
    {
        $required = $updating ? 'sometimes' : 'required';

        return $request->validate([
            'first_name' => [$required, 'string', 'max:255'],
            'last_name' => ['nullable', 'string', 'max:255'],
            'email' => ['nullable', 'email', 'max:255'],
            'phone' => ['nullable', 'string', 'max:30'],
            'company' => ['nullable', 'string', 'max:255'],
            'job_title' => ['nullable', 'string', 'max:255'],
            'source' => ['nullable', 'string', 'max:50'],
            'stage_id' => ['nullable', 'integer', 'exists:pipeline_stages,id'],
            'owner_id' => ['nullable', 'integer', 'exists:users,id'],
            'value' => ['nullable', 'numeric', 'min:0'],
            'notes' => ['nullable', 'string'],
            'custom_fields' => ['nullable', 'array'],
            'lost_reason' => ['nullable', 'string', 'max:255'],
        ]);
    }

    private function authorizeAccess(Request $request, Lead $lead): void
    {
        if ($request->user()->role === 'rep' && $lead->owner_id !== $request->user()->id) {
            abort(403, 'You can only access your own leads.');
        }
    }
}
