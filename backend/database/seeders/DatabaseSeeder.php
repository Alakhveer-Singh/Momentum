<?php

namespace Database\Seeders;

use App\Models\Activity;
use App\Models\CustomFieldDefinition;
use App\Models\EmailTemplate;
use App\Models\Lead;
use App\Models\PipelineStage;
use App\Models\Task;
use App\Models\User;
use App\Services\LeadScoringService;
use Illuminate\Database\Seeder;
use Illuminate\Support\Carbon;

class DatabaseSeeder extends Seeder
{
    public function run(): void
    {
        // --- Pipeline stages -------------------------------------------------
        $stages = collect([
            ['name' => 'New', 'slug' => 'new', 'position' => 1, 'color' => '#3b82f6'],
            ['name' => 'Contacted', 'slug' => 'contacted', 'position' => 2, 'color' => '#8b5cf6'],
            ['name' => 'Qualified', 'slug' => 'qualified', 'position' => 3, 'color' => '#f59e0b'],
            ['name' => 'Negotiating', 'slug' => 'negotiating', 'position' => 4, 'color' => '#f97316'],
            ['name' => 'Won', 'slug' => 'won', 'position' => 5, 'color' => '#22c55e', 'is_won' => true],
            ['name' => 'Lost', 'slug' => 'lost', 'position' => 6, 'color' => '#ef4444', 'is_lost' => true],
        ])->mapWithKeys(fn ($s) => [$s['slug'] => PipelineStage::create($s)]);

        // --- Users ------------------------------------------------------------
        $admin = User::create([
            'name' => 'Parul Saxena', 'email' => 'admin@quibus.in',
            'password' => 'password', 'role' => 'admin', 'phone' => '+91 98290 00001',
        ]);
        $manager = User::create([
            'name' => 'Rohit Sharma', 'email' => 'manager@quibus.in',
            'password' => 'password', 'role' => 'manager', 'phone' => '+91 98290 00002',
        ]);
        $rep1 = User::create([
            'name' => 'Anjali Verma', 'email' => 'anjali@quibus.in',
            'password' => 'password', 'role' => 'rep', 'phone' => '+91 98290 00003',
        ]);
        $rep2 = User::create([
            'name' => 'Vikram Singh', 'email' => 'vikram@quibus.in',
            'password' => 'password', 'role' => 'rep', 'phone' => '+91 98290 00004',
        ]);

        // --- Custom field definitions ------------------------------------------
        CustomFieldDefinition::create(['label' => 'Budget Range', 'key' => 'budget_range', 'type' => 'select',
            'options' => ['< ₹50k', '₹50k–₹2L', '₹2L–₹5L', '> ₹5L']]);
        CustomFieldDefinition::create(['label' => 'Industry', 'key' => 'industry', 'type' => 'text']);
        CustomFieldDefinition::create(['label' => 'Decision Maker', 'key' => 'decision_maker', 'type' => 'boolean']);

        // --- Email templates ----------------------------------------------------
        EmailTemplate::create([
            'name' => 'Welcome / First Touch',
            'subject' => 'Great connecting with you, {{first_name}}!',
            'body' => "Hi {{first_name}},\n\nThanks for your interest in our services. I'd love to set up a quick 15-minute call to understand {{company}}'s goals.\n\nBest,\nQuibus Team",
            'created_by' => $admin->id,
        ]);
        EmailTemplate::create([
            'name' => 'Follow-up After Call',
            'subject' => 'Next steps for {{company}}',
            'body' => "Hi {{first_name}},\n\nGreat speaking with you today. As discussed, I'm attaching our proposal. Let me know if you have questions.\n\nBest,\nQuibus Team",
            'created_by' => $manager->id,
        ]);
        EmailTemplate::create([
            'name' => 'Proposal Reminder',
            'subject' => 'Checking in on the proposal, {{first_name}}',
            'body' => "Hi {{first_name}},\n\nJust checking in on the proposal I sent over. Happy to walk through it together if helpful.\n\nBest,\nQuibus Team",
            'created_by' => $manager->id,
        ]);

        // --- Leads ---------------------------------------------------------------
        $owners = [$rep1, $rep2, $manager];
        $demoLeads = [
            ['Aarav', 'Mehta', 'aarav.mehta@technova.in', 'TechNova Solutions', 'CTO', 'web_form', 'qualified', 250000],
            ['Priya', 'Iyer', 'priya@brightedu.com', 'BrightEdu Academy', 'Founder', 'google_ads', 'negotiating', 480000],
            ['Karan', 'Kapoor', 'karan.k@stylehub.in', 'StyleHub Retail', 'Marketing Head', 'facebook_ads', 'contacted', 120000],
            ['Sneha', 'Reddy', 'sneha@greenleaf.org', 'GreenLeaf Organics', 'CEO', 'referral', 'won', 350000],
            ['Aditya', 'Joshi', 'aditya@finwise.co', 'FinWise Advisors', 'Partner', 'linkedin', 'new', 200000],
            ['Meera', 'Nair', 'meera.nair@oceanic.in', 'Oceanic Exports', 'Director', 'cold_call', 'contacted', 600000],
            ['Rahul', 'Gupta', 'rahul@speedlogix.com', 'SpeedLogix', 'Ops Manager', 'web_form', 'qualified', 175000],
            ['Divya', 'Malhotra', 'divya@craftnest.in', 'CraftNest', 'Owner', 'manual', 'lost', 90000],
            ['Arjun', 'Bose', 'arjun@medicare-plus.in', 'MediCare Plus', 'Admin Head', 'google_ads', 'negotiating', 320000],
            ['Ishita', 'Chawla', 'ishita@urbanbite.com', 'UrbanBite Foods', 'Co-founder', 'referral', 'new', 150000],
            ['Nikhil', 'Rao', 'nikhil@cloudpeak.io', 'CloudPeak Systems', 'VP Sales', 'linkedin', 'qualified', 420000],
            ['Tanvi', 'Desai', 'tanvi@blossomco.in', 'Blossom Cosmetics', 'Brand Manager', 'facebook_ads', 'new', 80000],
        ];

        $scoring = app(LeadScoringService::class);

        foreach ($demoLeads as $i => [$first, $last, $email, $company, $title, $source, $stageSlug, $value]) {
            $stage = $stages[$stageSlug];
            $owner = $owners[$i % count($owners)];
            $created = Carbon::now()->subDays(rand(3, 45));

            $lead = Lead::create([
                'first_name' => $first,
                'last_name' => $last,
                'email' => $email,
                'phone' => '+91 9' . rand(100000000, 999999999),
                'company' => $company,
                'job_title' => $title,
                'source' => $source,
                'stage_id' => $stage->id,
                'owner_id' => $owner->id,
                'value' => $value,
                'custom_fields' => [
                    'industry' => ['Technology', 'Education', 'Retail', 'Healthcare', 'Food'][$i % 5],
                    'decision_maker' => (bool) ($i % 2),
                ],
                'converted_at' => $stage->is_won ? $created->copy()->addDays(rand(5, 20)) : null,
                'lost_reason' => $stage->is_lost ? 'Budget constraints' : null,
                'created_at' => $created,
            ]);

            Activity::create([
                'lead_id' => $lead->id, 'user_id' => $owner->id, 'type' => 'system',
                'subject' => 'Lead created via ' . str_replace('_', ' ', $source),
                'occurred_at' => $created,
            ]);
            if ($stageSlug !== 'new') {
                Activity::create([
                    'lead_id' => $lead->id, 'user_id' => $owner->id, 'type' => 'call',
                    'subject' => 'Intro call with ' . $first,
                    'description' => 'Discussed requirements and budget. Positive response.',
                    'occurred_at' => $created->copy()->addDays(1),
                ]);
                Activity::create([
                    'lead_id' => $lead->id, 'user_id' => $owner->id, 'type' => 'email',
                    'subject' => 'Sent welcome email',
                    'occurred_at' => $created->copy()->addDays(1)->addHours(2),
                ]);
            }
            if (in_array($stageSlug, ['qualified', 'negotiating', 'won'])) {
                Activity::create([
                    'lead_id' => $lead->id, 'user_id' => $owner->id, 'type' => 'meeting',
                    'subject' => 'Discovery meeting',
                    'description' => 'Demo of platform; stakeholders aligned.',
                    'occurred_at' => $created->copy()->addDays(4),
                ]);
            }

            $lead->update([
                'last_activity_at' => $lead->activities()->max('occurred_at'),
                'score' => $scoring->calculate($lead->fresh('stage', 'activities')),
            ]);

            if (! $stage->is_won && ! $stage->is_lost) {
                Task::create([
                    'lead_id' => $lead->id,
                    'assigned_to' => $owner->id,
                    'created_by' => $manager->id,
                    'title' => 'Follow up with ' . $first . ' (' . $company . ')',
                    'priority' => ['low', 'medium', 'high'][$i % 3],
                    'due_at' => Carbon::now()->addDays(rand(-2, 7)),
                ]);
            }
        }

        Task::create([
            'assigned_to' => $rep1->id, 'created_by' => $manager->id,
            'title' => 'Prepare Q3 outreach list', 'priority' => 'medium',
            'due_at' => Carbon::now()->addDays(3),
        ]);
        Task::create([
            'assigned_to' => $rep2->id, 'created_by' => $manager->id,
            'title' => 'Update proposal deck with new pricing', 'priority' => 'high',
            'due_at' => Carbon::now()->addDay(),
        ]);
    }
}
