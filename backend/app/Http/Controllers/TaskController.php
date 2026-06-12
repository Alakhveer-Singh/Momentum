<?php

namespace App\Http\Controllers;

use App\Models\Task;
use App\Notifications\TaskAssigned;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class TaskController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $query = Task::with(['lead:id,first_name,last_name,company', 'assignee:id,name', 'creator:id,name']);

        if ($request->user()->role === 'rep') {
            $query->where('assigned_to', $request->user()->id);
        } elseif ($assignee = $request->query('assigned_to')) {
            $query->where('assigned_to', $assignee);
        }

        if ($status = $request->query('status')) {
            $query->where('status', $status);
        }
        if ($request->boolean('overdue')) {
            $query->where('status', 'pending')->where('due_at', '<', now());
        }
        if ($leadId = $request->query('lead_id')) {
            $query->where('lead_id', $leadId);
        }

        return response()->json(
            $query->orderByRaw('due_at IS NULL, due_at asc')->paginate($request->integer('per_page', 25))
        );
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'lead_id' => ['nullable', 'integer', 'exists:leads,id'],
            'assigned_to' => ['required', 'integer', 'exists:users,id'],
            'title' => ['required', 'string', 'max:255'],
            'description' => ['nullable', 'string'],
            'priority' => ['nullable', 'in:low,medium,high'],
            'due_at' => ['nullable', 'date'],
        ]);

        $task = Task::create($data + ['created_by' => $request->user()->id]);
        $task->load(['lead:id,first_name,last_name,company', 'assignee:id,name']);

        if ($task->assigned_to !== $request->user()->id) {
            $task->assignee->notify(new TaskAssigned($task));
        }

        return response()->json($task, 201);
    }

    public function update(Request $request, Task $task): JsonResponse
    {
        if ($request->user()->role === 'rep' && $task->assigned_to !== $request->user()->id) {
            return response()->json(['message' => 'Forbidden.'], 403);
        }

        $data = $request->validate([
            'title' => ['sometimes', 'string', 'max:255'],
            'description' => ['nullable', 'string'],
            'priority' => ['sometimes', 'in:low,medium,high'],
            'status' => ['sometimes', 'in:pending,completed'],
            'due_at' => ['nullable', 'date'],
            'assigned_to' => ['sometimes', 'integer', 'exists:users,id'],
        ]);

        if (($data['status'] ?? null) === 'completed' && $task->status !== 'completed') {
            $data['completed_at'] = now();
        } elseif (($data['status'] ?? null) === 'pending') {
            $data['completed_at'] = null;
        }

        $task->update($data);

        return response()->json($task->load(['lead:id,first_name,last_name,company', 'assignee:id,name']));
    }

    public function destroy(Request $request, Task $task): JsonResponse
    {
        if (! $request->user()->isManager() && $task->created_by !== $request->user()->id) {
            return response()->json(['message' => 'Forbidden.'], 403);
        }

        $task->delete();

        return response()->json(['message' => 'Task deleted.']);
    }
}
