"""Managed preview launcher for development QA only; use start.sh/start.bat locally."""
import os
import uvicorn
os.environ['VOICEFRAME_ALLOWED_HOSTS'] = '*'
uvicorn.run('app.main:app', host='0.0.0.0', port=int(os.getenv('PORT', '5173')))
