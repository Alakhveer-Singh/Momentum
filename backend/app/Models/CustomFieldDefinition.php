<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class CustomFieldDefinition extends Model
{
    protected $fillable = ['label', 'key', 'type', 'options'];

    protected $casts = ['options' => 'array'];
}
