<?php

namespace App\Events;

use App\Models\Lead;
use Illuminate\Broadcasting\InteractsWithSockets;
use Illuminate\Broadcasting\PrivateChannel;
use Illuminate\Contracts\Broadcasting\ShouldBroadcast;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class LeadUpdated implements ShouldBroadcast
{
    use Dispatchable, InteractsWithSockets, SerializesModels;

    public function __construct(public Lead $lead, public string $action)
    {
    }

    public function broadcastOn(): array
    {
        return [new PrivateChannel('leads')];
    }

    public function broadcastAs(): string
    {
        return 'lead.updated';
    }

    public function broadcastWith(): array
    {
        return [
            'action' => $this->action,
            'lead' => [
                'id' => $this->lead->id,
                'full_name' => $this->lead->full_name,
                'company' => $this->lead->company,
                'stage_id' => $this->lead->stage_id,
                'stage' => $this->lead->stage?->name,
                'score' => $this->lead->score,
                'owner_id' => $this->lead->owner_id,
            ],
        ];
    }
}
