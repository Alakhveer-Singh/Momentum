<?php

namespace App\Http\Controllers;

use App\Models\Lead;
use App\Models\PipelineStage;
use Barryvdh\DomPDF\Facade\Pdf;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\StreamedResponse;

class ExportController extends Controller
{
    public function leadsCsv(Request $request): StreamedResponse
    {
        $query = Lead::with(['stage', 'owner']);

        if ($request->user()->role === 'rep') {
            $query->where('owner_id', $request->user()->id);
        }
        if ($stage = $request->query('stage_id')) {
            $query->where('stage_id', $stage);
        }

        return response()->streamDownload(function () use ($query) {
            $out = fopen('php://output', 'w');
            fputcsv($out, ['ID', 'First Name', 'Last Name', 'Email', 'Phone', 'Company',
                'Job Title', 'Source', 'Stage', 'Owner', 'Score', 'Value', 'Created At']);

            $query->chunk(200, function ($leads) use ($out) {
                foreach ($leads as $lead) {
                    fputcsv($out, [
                        $lead->id, $lead->first_name, $lead->last_name, $lead->email,
                        $lead->phone, $lead->company, $lead->job_title, $lead->source,
                        $lead->stage?->name, $lead->owner?->name, $lead->score,
                        $lead->value, $lead->created_at?->toDateTimeString(),
                    ]);
                }
            });

            fclose($out);
        }, 'leads-' . now()->format('Y-m-d') . '.csv', ['Content-Type' => 'text/csv']);
    }

    public function pipelinePdf(Request $request)
    {
        $stages = PipelineStage::orderBy('position')->with(['leads' => function ($q) use ($request) {
            if ($request->user()->role === 'rep') {
                $q->where('owner_id', $request->user()->id);
            }
            $q->with('owner:id,name')->orderByDesc('value');
        }])->get();

        $pdf = Pdf::loadView('reports.pipeline', [
            'stages' => $stages,
            'generatedAt' => now(),
            'generatedBy' => $request->user()->name,
        ]);

        return $pdf->download('pipeline-report-' . now()->format('Y-m-d') . '.pdf');
    }
}
