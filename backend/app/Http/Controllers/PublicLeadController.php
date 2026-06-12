<?php

namespace App\Http\Controllers;

use App\Events\LeadUpdated;
use App\Models\Activity;
use App\Models\Lead;
use App\Models\PipelineStage;
use App\Services\LeadScoringService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/**
 * Public, unauthenticated lead-intake endpoint for embedding web forms.
 * Rate-limited via the 'throttle:public-intake' limiter.
 */
class PublicLeadController extends Controller
{
    public function store(Request $request, LeadScoringService $scoring): JsonResponse
    {
        $data = $request->validate([
            'first_name' => ['required', 'string', 'max:255'],
            'last_name' => ['nullable', 'string', 'max:255'],
            'email' => ['required', 'email', 'max:255'],
            'phone' => ['nullable', 'string', 'max:30'],
            'company' => ['nullable', 'string', 'max:255'],
            'message' => ['nullable', 'string', 'max:2000'],
        ]);

        $lead = Lead::create([
            'first_name' => $data['first_name'],
            'last_name' => $data['last_name'] ?? null,
            'email' => $data['email'],
            'phone' => $data['phone'] ?? null,
            'company' => $data['company'] ?? null,
            'notes' => $data['message'] ?? null,
            'source' => 'web_form',
            'stage_id' => PipelineStage::where('slug', 'new')->value('id'),
            'last_activity_at' => now(),
        ]);

        Activity::create([
            'lead_id' => $lead->id,
            'type' => 'system',
            'subject' => 'Lead captured via web form',
            'metadata' => ['ip' => $request->ip()],
        ]);

        $scoring->recalculate($lead);
        LeadUpdated::dispatch($lead->fresh(['stage', 'owner']), 'created');

        return response()->json(['message' => 'Thank you! We will be in touch shortly.'], 201);
    }
}
