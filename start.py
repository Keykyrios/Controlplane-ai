"""
ControlPlane Manifold — One-Command Startup
=============================================
Start all backend services + frontend in a single terminal.

Usage:
    python start.py          # Start everything
    python start.py --backend-only   # Backend only (no frontend)
    python start.py --frontend-only  # Frontend only

All services run on localhost ports 8000-8016.
Frontend runs on http://localhost:5173 (or next available port).
"""

import subprocess
import sys
import time
import os
import signal
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SERVICES_DIR = PROJECT_ROOT / "services"

# Service definitions: (name, port)
SERVICES = [
    ("risk-observables", 8001),
    ("risk-multivector", 8002),
    ("fingerprint", 8003),
    ("drift", 8004),
    ("surprise", 8005),
    ("spectral", 8006),
    ("sheaf-fusion", 8007),
    ("portability-adapters", 8008),
    ("tropical-routing", 8009),
    ("conformal-calibration", 8010),
    ("game-theory-patcher", 8011),
    ("syndrome-decoder", 8012),
    ("thermo-accounting", 8013),
    ("queueing-monitor", 8014),
    ("audit-ledger", 8015),
    ("policy-manifold", 8016),
    # Orchestrator last — depends on the others
    ("orchestrator", 8000),
]

processes = []


def start_service(name: str, port: int) -> subprocess.Popen:
    """Start a single FastAPI service."""
    service_dir = SERVICES_DIR / name
    main_file = service_dir / "main.py"

    if not main_file.exists():
        print(f"  [WARN] {name}: main.py not found, skipping")
        return None

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0", "--port", str(port),
         "--log-level", "warning"],
        cwd=str(service_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def start_frontend() -> subprocess.Popen:
    """Start the Vite dev server."""
    frontend_dir = PROJECT_ROOT / "frontend"
    if not (frontend_dir / "package.json").exists():
        print("  [WARN] Frontend not found, skipping")
        return None

    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True,
    )
    return proc


def cleanup(signum=None, frame=None):
    """Kill all child processes."""
    print("\n\n  Shutting down all services...")
    for name, proc in processes:
        if proc and proc.poll() is None:
            if sys.platform == "win32":
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    proc.kill()
            else:
                proc.kill()
    print("  All services stopped.")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Start ControlPlane Manifold")
    parser.add_argument("--backend-only", action="store_true", help="Start backend only")
    parser.add_argument("--frontend-only", action="store_true", help="Start frontend only")
    args = parser.parse_args()

    # Register cleanup handler
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print()
    print("  +--------------------------------------------------+")
    print("  |     ControlPlane Manifold -- Starting Up          |")
    print("  +--------------------------------------------------+")
    print()

    if not args.frontend_only:
        print("  Starting backend services...")
        print()

        for name, port in SERVICES:
            proc = start_service(name, port)
            if proc:
                processes.append((name, proc))
                print(f"  [OK] {name:.<30} port {port}")
            time.sleep(0.2)  # Stagger startups

        print()
        print(f"  [OK] {len(processes)} services started")
        print(f"  [OK] Orchestrator:  http://localhost:8000")
        print(f"  [OK] Health check:  http://localhost:8000/health")
        print(f"  [OK] API docs:      http://localhost:8000/docs")
        print()

        # Wait for services to initialize
        print("  Waiting for services to initialize...")
        time.sleep(3)

    if not args.backend_only:
        print("  Starting frontend...")
        fe_proc = start_frontend()
        if fe_proc:
            processes.append(("frontend", fe_proc))
            time.sleep(2)
            print(f"  [OK] Frontend:      http://localhost:5173")
        print()

    print("  +--------------------------------------------------+")
    print("  |  All systems go. Open http://localhost:5173      |")
    print("  |  Press Ctrl+C to stop all services.              |")
    print("  +--------------------------------------------------+")
    print()

    # Keep running
    try:
        while True:
            # Check for crashed services
            for name, proc in processes:
                if proc and proc.poll() is not None:
                    pass  # Service exited — could restart here
            time.sleep(5)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
