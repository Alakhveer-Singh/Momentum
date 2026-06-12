<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Lead extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'first_name',
        'last_name',
        'email',
        'phone',
        'company',
        'job_title',
        'source',
        'stage_id',
        'owner_id',
        'score',
        'value',
        'notes',
        'custom_fields',
        'lost_reason',
        'last_activity_at',
        'converted_at',
    ];

    protected $casts = [
        'custom_fields' => 'array',
        'value' => 'decimal:2',
        'last_activity_at' => 'datetime',
        'converted_at' => 'datetime',
    ];

    protected $appends = ['full_name'];

    public function getFullNameAttribute(): string
    {
        return trim($this->first_name . ' ' . $this->last_name);
    }

    public function stage()
    {
        return $this->belongsTo(PipelineStage::class, 'stage_id');
    }

    public function owner()
    {
        return $this->belongsTo(User::class, 'owner_id');
    }

    public function activities()
    {
        return $this->hasMany(Activity::class)->latest('occurred_at');
    }

    public function tasks()
    {
        return $this->hasMany(Task::class);
    }
}
