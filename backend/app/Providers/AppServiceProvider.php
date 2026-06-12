<?php

namespace App\Providers;

use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Broadcast;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        //
    }

    public function boot(): void
    {
        RateLimiter::for('public-intake', function (Request $request) {
            return Limit::perMinute(10)->by($request->ip());
        });

        // JWT-authenticated broadcast channel authorization
        Broadcast::routes(['middleware' => ['auth:api'], 'prefix' => 'api']);
        require base_path('routes/channels.php');
    }
}
