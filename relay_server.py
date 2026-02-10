from gevent import monkey
monkey.patch_all()

from flask import Flask, request, jsonify
import websocket
import threading
import time

app = Flask(__name__)
pool_connections = {}
connection_lock = threading.Lock()

# Ensure this is just the domain
CF_WORKER_HOST = "dunio.kifehasan137.workers.dev" 

@app.route('/connect', methods=['POST'])
def connect():
    client_id = request.json.get('client_id', 'default')
    try:
        ws_url = f"wss://{CF_WORKER_HOST}/"
        ws = websocket.create_connection(
            ws_url, 
            timeout=20, 
            suppress_origin=True,
            header=["User-Agent: Mozilla/5.0"]
        )
        
        # 1. Wait for pool version
        time.sleep(1)
        version = ws.recv().strip()
        
        # 2. Safety Fallback: If pool is silent, assume 3.0
        if not version or len(version) > 10:
            version = "3.0"

        with connection_lock:
            pool_connections[client_id] = {"socket": ws, "version": version}
        
        print(f"📡 [RELAY] {client_id} linked to Pool v{version}")
            
        # 3. We send EVERY possible key so the bot can't miss it
        return jsonify({
            "success": True, 
            "version": version,
            "pool_version": version,
            "name": "Cloudflare-Bridge",
            "pool_name": "Duco-Stealth-Pool"
        })
    except Exception as e:
        print(f"❌ [RELAY] Connect Error: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/job', methods=['POST'])
def job():
    data = request.json
    client_id = data.get('client_id', 'default')
    username = data.get('username', 'dj_kaif')
    
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False, "error": "Not connected"})
        ws = pool_connections[client_id]['socket']
    
    try:
        # Request a job
        ws.send(f"JOB,{username},LOW")
        job_data = ws.recv().strip()
        
        # If the pool sends a 'MOTD' or 'NOTICE' instead of a job, skip it
        if "MOTD" in job_data or "NOTICE" in job_data:
            job_data = ws.recv().strip()

        print(f"📦 [RELAY] Job Sent: {job_data[:20]}...")
        
        return jsonify({
            "success": True, 
            "job": job_data,
            "result": job_data.split(",") # Some bots want the list, some want the string
        })
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
    return jsonify({"status": "online", "active_clients": len(pool_connections)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
    
