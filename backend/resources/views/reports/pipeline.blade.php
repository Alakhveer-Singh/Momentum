<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Pipeline Report</title>
    <style>
        body { font-family: DejaVu Sans, sans-serif; font-size: 11px; color: #1f2937; }
        h1 { font-size: 18px; margin-bottom: 2px; }
        .meta { color: #6b7280; margin-bottom: 16px; }
        h2 { font-size: 13px; margin: 14px 0 6px; padding: 4px 8px; color: #fff; border-radius: 3px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
        th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #e5e7eb; }
        th { background: #f3f4f6; font-size: 10px; text-transform: uppercase; color: #6b7280; }
        .right { text-align: right; }
        .empty { color: #9ca3af; font-style: italic; padding: 4px 8px; }
    </style>
</head>
<body>
    <h1>Quibus LMS — Pipeline Report</h1>
    <div class="meta">Generated {{ $generatedAt->format('d M Y, H:i') }} by {{ $generatedBy }}</div>

    @foreach ($stages as $stage)
        <h2 style="background: {{ $stage->color }};">
            {{ $stage->name }} — {{ $stage->leads->count() }} lead(s),
            ₹{{ number_format($stage->leads->sum('value'), 0) }}
        </h2>
        @if ($stage->leads->isEmpty())
            <div class="empty">No leads in this stage.</div>
        @else
            <table>
                <thead>
                    <tr>
                        <th>Name</th><th>Company</th><th>Email</th>
                        <th>Owner</th><th class="right">Score</th><th class="right">Value</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach ($stage->leads as $lead)
                        <tr>
                            <td>{{ $lead->full_name }}</td>
                            <td>{{ $lead->company }}</td>
                            <td>{{ $lead->email }}</td>
                            <td>{{ $lead->owner?->name }}</td>
                            <td class="right">{{ $lead->score }}</td>
                            <td class="right">₹{{ number_format($lead->value, 0) }}</td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        @endif
    @endforeach
</body>
</html>
