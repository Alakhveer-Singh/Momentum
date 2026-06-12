<?php

namespace App\Services;

use App\Models\Lead;

class LeadScoringService
{
    /**
     * Source quality weights.
     */
    private const SOURCE_WEIGHTS = [
        'referral' => 25,
        'web_form' => 20,
        'linkedin' => 15,
        'google_ads' => 12,
        'facebook_ads' => 10,
        'cold_call' => 5,
        'manual' => 5,
    ];

    /**
     * Stage progression weights.
     */
    private const STAGE_WEIGHTS = [
        'new' => 0,
        'contacted' => 10,
        'qualified' => 25,
        'negotiating' => 35,
        'won' => 40,
        'lost' => 0,
    ];

    /**
     * Engagement points per activity type (capped).
     */
    private const ACTIVITY_WEIGHTS = [
        'meeting' => 8,
        'call' => 5,
        'email' => 3,
        'note' => 1,
    ];

    private const ENGAGEMENT_CAP = 30;

    /**
     * Score 0–100: source quality + stage progression + engagement + profile completeness.
     */
    public function calculate(Lead $lead): int
    {
        $score = self::SOURCE_WEIGHTS[$lead->source] ?? 5;
        $score += self::STAGE_WEIGHTS[$lead->stage->slug] ?? 0;

        $engagement = 0;
        foreach ($lead->activities as $activity) {
            $engagement += self::ACTIVITY_WEIGHTS[$activity->type] ?? 0;
        }
        $score += min($engagement, self::ENGAGEMENT_CAP);

        // Profile completeness (max 5)
        $score += collect([$lead->email, $lead->phone, $lead->company])
            ->filter()->count() + ($lead->value > 0 ? 2 : 0);

        return min($score, 100);
    }

    public function recalculate(Lead $lead): void
    {
        $lead->updateQuietly(['score' => $this->calculate($lead->fresh('stage', 'activities'))]);
    }
}
