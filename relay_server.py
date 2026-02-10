from gevent import monkey
monkey.patch_all()

from flask import Flask, request, jsonify
import websocket
import threading
import time
import requests

app = Flask(__name__)
pool_connections = {}
connection_lock = threading.Lock()

# PASTE YOUR CLOUDFLARE WORKER URL HERE (WITHOUT https://)
CF_WORKER_HOST = "dunio.kifehasan137.workers.dev" 


@app.route('/connect', methods=['POST'])
def connect():
    client_id = request.json.get('client_id', 'default')
    try:
        ws_url = f"wss://{CF_WORKER_HOST}/"
        ws = websocket.create_connection(
            ws_url, 
            timeout=10, 
            suppress_origin=True,
            header=["User-Agent: Mozilla/5.0"]
        )
        
        # Try to get version, if it fails, use 3.0 as fallback 
        # so the bot doesn't show 'None:None'
        try:
            version = ws.recv().strip()
            if not version or len(version) > 10: # Sanity check
                version = "3.0"
        except:
            version = "3.0"

        print(f"📡 [RELAY] Connected! Version: {version}")

        with connection_lock:
            pool_connections[client_id] = {"socket": ws, "version": version}
            
        return jsonify({"success": True, "version": version})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
        
        
        
        


@app.route('/job', methods=['POST'])
def job():
    data = request.json
    client_id = data.get('client_id', 'default')
    username = data.get('username')
    
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False, "error": "Relay not connected"})
        ws = pool_connections[client_id]['socket']
    
    try:
        ws.send(f"JOB,{username},LOW")
        job_data = ws.recv().strip()
        return jsonify({"success": True, "job": job_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    client_id = data.get('client_id', 'default')
    
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False})
        ws = pool_connections[client_id]['socket']
    
    try:
        # Format: result,hashrate,rig_name,key
        submission = f"{data['result']},{data['hashrate']},{data['rig_name']},{data.get('key', 'None')}"
        ws.send(submission)
        feedback = ws.recv().strip()
        return jsonify({"success": True, "feedback": feedback})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/status')
def status():
    return jsonify({"status": "online", "mode": "stealth-cloudflare"})

@app.route('/')
def home():
    return "Stealth Cloudflare Relay is Active."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
    
