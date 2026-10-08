# Real-Time Notification & Monitoring Microservice

An automated, 24/7 cloud-hosted alerting microservice deployed on Render that calculates schedule offsets and dispatches high-priority push notifications directly to mobile devices via the ntfy REST API.

## Architecture & How It Works
* **Cloud Daemon:** Runs a lightweight Python HTTP server (`HTTPServer`) on Render to maintain port binding.
* **Cron Keep-Alive:** Integrated with automated 5-minute health check pings (`cron-job.org`) to eliminate cold boot delays and container suspension.
* **Dynamic Time Parsing:** Calculates daily schedule intervals and time offsets using timezone-aware logic (`Europe/London`).
* **API Delivery:** Dispatches structured HTTP POST requests to `ntfy.sh` with custom headers and priority levels for instant lock-screen mobile delivery.

## Tech Stack
* Python 3
* Render Cloud Platform
* ntfy REST API
* Cron-job.org
