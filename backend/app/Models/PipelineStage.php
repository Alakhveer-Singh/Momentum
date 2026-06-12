<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class PipelineStage extends Model
{
    protected $fillable = ['name', 'slug', 'position', 'color', 'is_won', 'is_lost'];

    protected $casts = [
        'is_won' => 'boolean',
        'is_lost' => 'boolean',
    ];

    public function leads()
    {
        return $this->hasMany(Lead::class, 'stage_id');
    }
}
