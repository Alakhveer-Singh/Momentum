<?php

namespace App\Http\Controllers;

use App\Events\LeadUpdated;
use App\Models\Activity;
use App\Models\EmailTemplate;
use App\Models\Lead;
use App\Services\LeadScoringService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Mail;

class EmailTemplateController extends Controller
{
    public function __construct(private LeadScoringService $scoring)
    {
    }

    public function index(): JsonResponse
    {
        return response()->json(EmailTemplate::with('creator:id,name')->latest()->get());
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'subject' => ['required', 'string', 'max:255'],
            'body' => ['required', 'string'],
        ]);

        $template = EmailTemplate::create($data + ['created_by' => $request->user()->id]);

        return response()->json($template, 201);
    }

    public function update(Request $request, EmailTemplate $emailTemplate): JsonResponse
    {
        $data = $request->validate([
            'name' => ['sometimes', 'string', 'max:255'],
            'subject' => ['sometimes', 'string', 'max:255'],
            'body' => ['sometimes', 'string'],
        ]);

        $emailTemplate->update($data);

        return response()->json($emailTemplate);
    }

    public function destroy(EmailTemplate $emailTemplate): JsonResponse
    {
        $emailTemplate->delete();

        return response()->json(['message' => 'Template deleted.']);
    }

    /**
     * Render + "send" a template to one or many leads. Uses the configured
     * mail driver (log driver in local dev) and records an email activity.
     */
    public function send(Request $request): JsonResponse
    {
        $data = $request->validate([
            'template_id' => ['required', 'integer', 'exists:email_templates,id'],
            'lead_ids' => ['required', 'array', 'min:1', 'max:200'],
            'lead_ids.*' => ['integer', 'exists:leads,id'],
        ]);

        $template = EmailTemplate::findOrFail($data['template_id']);
        $sent = 0;

        foreach (Lead::whereIn('id', $data['lead_ids'])->get() as $lead) {
            if (! $lead->email) {
                continue;
            }

            $rendered = $template->render($lead);

            Mail::raw($rendered['body'], function ($message) use ($lead, $rendered) {
                $message->to($lead->email, $lead->full_name)->subject($rendered['subject']);
            });

            Activity::create([
                'lead_id' => $lead->id,
                'user_id' => $request->user()->id,
                'type' => 'email',
                'subject' => 'Email sent: ' . $rendered['subject'],
                'metadata' => ['template_id' => $template->id],
            ]);

            $lead->update(['last_activity_at' => now()]);
            $this->scoring->recalculate($lead);
            LeadUpdated::dispatch($lead->fresh(['stage', 'owner']), 'activity');
            $sent++;
        }

        return response()->json(['message' => "Email sent to {$sent} lead(s).", 'sent' => $sent]);
    }
}
