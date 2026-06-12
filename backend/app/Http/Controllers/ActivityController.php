<?php

namespace App\Http\Controllers;

use App\Events\LeadUpdated;
use App\Models\Activity;
use App\Models\Lead;
use App\Services\LeadScoringService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class ActivityController extends Controller
{
    public function __construct(private LeadScoringService $scoring)
    {
    }

    public function index(Request $request): JsonResponse
    {
        $query = Activity::with(['lead:id,first_name,last_name,company', 'user:id,name']);

        if ($request->user()->role === 'rep') {
            $query->whereHas('lead', fn ($q) => $q->where('owner_id', $request->user()->id));
        }

        if ($leadId = $request->query('lead_id')) {
            $query->where('lead_id', $leadId);
        }
        if ($type = $request->query('type')) {
            $query->where('type', $type);
        }

        return response()->json(
            $query->latest('occurred_at')->paginate($request->integer('per_page', 25))
        );
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'lead_id' => ['required', 'integer', 'exists:leads,id'],
            'type' => ['required', 'in:call,email,meeting,note'],
            'subject' => ['required', 'string', 'max:255'],
            'description' => ['nullable', 'string'],
            'occurred_at' => ['nullable', 'date'],
        ]);

        $lead = Lead::findOrFail($data['lead_id']);

        if ($request->user()->role === 'rep' && $lead->owner_id !== $request->user()->id) {
            return response()->json(['message' => 'Forbidden.'], 403);
        }

        $activity = Activity::create($data + ['user_id' => $request->user()->id]);

        $lead->update(['last_activity_at' => $activity->occurred_at ?? now()]);
        $this->scoring->recalculate($lead);

        LeadUpdated::dispatch($lead->fresh(['stage', 'owner']), 'activity');

        return response()->json($activity->load('user:id,name'), 201);
    }

    public function destroy(Request $request, Activity $activity): JsonResponse
    {
        if (! $request->user()->isManager() && $activity->user_id !== $request->user()->id) {
            return response()->json(['message' => 'Forbidden.'], 403);
        }

        $activity->delete();

        return response()->json(['message' => 'Activity deleted.']);
    }
}
