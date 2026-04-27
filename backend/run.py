"""
===========================================================
  TrafficAI — Entry Point
  Run this file to start the server: python run.py
===========================================================
"""
import os, sys

# Auto-train model if not yet done
MODEL_PATH = os.path.join("models", "traffic_model.pkl")
DATA_PATH  = os.path.join("data",   "bhopal_traffic_dataset.csv")

"""if not os.path.exists(MODEL_PATH) or not os.path.exists(DATA_PATH):
    print("=" * 55)
    print("  First run detected — training model...")
    print("  This takes ~60 seconds. Please wait.")
    print("=" * 55)
    import subprocess
    result = subprocess.run([sys.executable, "model.py"], check=True)
    print("=" * 55)
    print("  Model trained successfully!")
    print("=" * 55)"""

# Start Flask app
from app import app

if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  TrafficAI Server Starting...")
    print("  Open browser at:  http://localhost:5000")
    print("  Press Ctrl+C to stop")
    print("=" * 55 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
