<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class EmailTemplate extends Model
{
    protected $fillable = ['name', 'subject', 'body', 'created_by'];

    public function creator()
    {
        return $this->belongsTo(User::class, 'created_by');
    }

    /**
     * Replace {{placeholders}} with lead attributes.
     */
    public function render(Lead $lead): array
    {
        $replacements = [
            '{{first_name}}' => $lead->first_name,
            '{{last_name}}' => (string) $lead->last_name,
            '{{full_name}}' => $lead->full_name,
            '{{company}}' => (string) $lead->company,
            '{{email}}' => (string) $lead->email,
        ];

        return [
            'subject' => strtr($this->subject, $replacements),
            'body' => strtr($this->body, $replacements),
        ];
    }
}
