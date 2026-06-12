<?php

namespace App\Http\Controllers;

use App\Models\Activity;
use App\Models\Lead;
use App\Models\PipelineStage;
use App\Models\Task;
use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class ReportController extends Controller
{
    public function dashboard(Request $request): JsonResponse
    {
        $user = $request->user();
        $leadScope = fn () => $user->role === 'rep'
            ? Lead::where('owner_id', $user->id)
            : Lead::query();

        $wonStage = PipelineStage::where('is_won', true)->first();
        $lostStage = PipelineStage::where('is_lost', true)->first();
        $openStageIds = PipelineStage::where('is_won', false)->where('is_lost', false)->pluck('id');

        $total = $leadScope()->count();
        $won = $leadScope()->where('stage_id', $wonStage?->id)->count();
        $lost = $leadScope()->where('stage_id', $lostStage?->id)->count();
        $closed = $won + $lost;

        return response()->json([
            'total_leads' => $total,
            'open_leads' => $leadScope()->whereIn('stage_id', $openStageIds)->count(),
            'won_leads' => $won,
            'lost_leads' => $lost,
            'conversion_rate' => $closed > 0 ? round($won / $closed * 100, 1) : 0,
            'pipeline_value' => (float) $leadScope()->whereIn('stage_id', $openStageIds)->sum('value'),
            'won_value' => (float) $leadScope()->where('stage_id', $wonStage?->id)->sum('value'),
            'new_this_week' => $leadScope()->where('created_at', '>=', now()->subDays(7))->count(),
            'avg_score' => round((float) $leadScope()->avg('score'), 1),
            'pending_tasks' => Task::where('status', 'pending')
                ->when($user->role === 'rep', fn ($q) => $q->where('assigned_to', $user->id))
                ->count(),
            'overdue_tasks' => Task::where('status', 'pending')->where('due_at', '<', now())
                ->when($user->role === 'rep', fn ($q) => $q->where('assigned_to', $user->id))
                ->count(),
        ]);
    }

    public function pipeline(Request $request): JsonResponse
    {
        $stages = PipelineStage::orderBy('position')
            ->withCount(['leads' => function ($q) use ($request) {
                if ($request->user()->role === 'rep') {
                    $q->where('owner_id', $request->user()->id);
                }
            }])
            ->get()
            ->map(function ($stage) use ($request) {
                $valueQuery = $stage->leads();
                if ($request->user()->role === 'rep') {
                    $valueQuery->where('owner_id', $request->user()->id);
                }
                $stage->total_value = (float) $valueQuery->sum('value');

                return $stage;
            });

        return response()->json($stages);
    }

    public function sources(): JsonResponse
    {
        $wonStageId = PipelineStage::where('is_won', true)->value('id');

        $rows = DB::table('leads')->whereNull('deleted_at')->select('source')
            ->selectRaw('count(*) as total')
            ->selectRaw('sum(case when stage_id = ? then 1 else 0 end) as won', [$wonStageId])
            ->selectRaw('sum(case when stage_id = ? then value else 0 end) as won_value', [$wonStageId])
            ->selectRaw('sum(value) as total_value')
            ->groupBy('source')
            ->orderByDesc('total')
            ->get()
            ->map(function ($row) {
                $row->conversion_rate = $row->total > 0 ? round($row->won / $row->total * 100, 1) : 0;

                return $row;
            });

        return response()->json($rows);
    }

    public function team(): JsonResponse
    {
        $wonStageId = PipelineStage::where('is_won', true)->value('id');

        $rows = User::where('is_active', true)
            ->get()
            ->map(function ($user) use ($wonStageId) {
                $leads = Lead::where('owner_id', $user->id);

                return [
                    'id' => $user->id,
                    'name' => $user->name,
                    'role' => $user->role,
                    'total_leads' => (clone $leads)->count(),
                    'won_leads' => (clone $leads)->where('stage_id', $wonStageId)->count(),
                    'won_value' => (float) (clone $leads)->where('stage_id', $wonStageId)->sum('value'),
                    'pipeline_value' => (float) (clone $leads)->sum('value'),
                    'activities_30d' => Activity::where('user_id', $user->id)
                        ->where('occurred_at', '>=', now()->subDays(30))->count(),
                    'pending_tasks' => Task::where('assigned_to', $user->id)->where('status', 'pending')->count(),
                ];
            });

        return response()->json($rows);
    }

    public function trend(): JsonResponse
    {
        $rows = DB::table('leads')->whereNull('deleted_at')
            ->selectRaw("date_format(created_at, '%Y-%m') as month")
            ->selectRaw('count(*) as leads')
            ->selectRaw('sum(case when converted_at is not null then 1 else 0 end) as won')
            ->where('created_at', '>=', now()->subMonths(6)->startOfMonth())
            ->groupBy('month')
            ->orderBy('month')
            ->get();

        return response()->json($rows);
    }
}
