<?php

use App\Http\Controllers\ActivityController;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\EmailTemplateController;
use App\Http\Controllers\ExportController;
use App\Http\Controllers\LeadController;
use App\Http\Controllers\NotificationController;
use App\Http\Controllers\PublicLeadController;
use App\Http\Controllers\ReportController;
use App\Http\Controllers\TaskController;
use App\Http\Controllers\UserController;
use App\Models\CustomFieldDefinition;
use App\Models\PipelineStage;
use Illuminate\Support\Facades\Route;

// --- Public ---------------------------------------------------------------
Route::post('public/leads', [PublicLeadController::class, 'store'])
    ->middleware('throttle:public-intake');

Route::post('auth/login', [AuthController::class, 'login'])->middleware('throttle:10,1');

// --- Authenticated ----------------------------------------------------------
Route::middleware('auth:api')->group(function () {
    // Auth/session
    Route::get('auth/me', [AuthController::class, 'me']);
    Route::post('auth/refresh', [AuthController::class, 'refresh']);
    Route::post('auth/logout', [AuthController::class, 'logout']);
    Route::put('auth/profile', [AuthController::class, 'updateProfile']);

    // Reference data
    Route::get('stages', fn () => PipelineStage::orderBy('position')->get());
    Route::get('custom-fields', fn () => CustomFieldDefinition::all());

    // Leads
    Route::apiResource('leads', LeadController::class);
    Route::post('leads-import', [LeadController::class, 'bulkImport']);

    // Activities
    Route::get('activities', [ActivityController::class, 'index']);
    Route::post('activities', [ActivityController::class, 'store']);
    Route::delete('activities/{activity}', [ActivityController::class, 'destroy']);

    // Tasks
    Route::apiResource('tasks', TaskController::class)->except(['show']);

    // Email templates + sending
    Route::apiResource('email-templates', EmailTemplateController::class)->except(['show']);
    Route::post('emails/send', [EmailTemplateController::class, 'send']);

    // Reports
    Route::prefix('reports')->group(function () {
        Route::get('dashboard', [ReportController::class, 'dashboard']);
        Route::get('pipeline', [ReportController::class, 'pipeline']);
        Route::get('sources', [ReportController::class, 'sources'])->middleware('role:admin,manager');
        Route::get('team', [ReportController::class, 'team'])->middleware('role:admin,manager');
        Route::get('trend', [ReportController::class, 'trend']);
    });

    // Exports
    Route::get('exports/leads.csv', [ExportController::class, 'leadsCsv']);
    Route::get('exports/pipeline.pdf', [ExportController::class, 'pipelinePdf']);

    // Notifications
    Route::get('notifications', [NotificationController::class, 'index']);
    Route::post('notifications/read', [NotificationController::class, 'markRead']);

    // User management (admin only)
    Route::apiResource('users', UserController::class)
        ->except(['show'])
        ->middleware('role:admin');
});
