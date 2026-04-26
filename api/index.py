import os
import sys

# Add the backend directory to the sys.path so Vercel can find your modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app import app

# Vercel's Python runtime expects a variable named 'app' or 'handler'
app = app
