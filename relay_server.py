from gevent import monkey
monkey.patch_all()

from flask import Flask, request, jsonify
import websocket
import threading
import time

app = Flask(__name__)
pool_connections = {}
connection_lock = threading.Lock()

# Ensure this is just the domain name
CF_WORKER_HOST = "dunio.kifehasan137.workers.dev" 

@app.route('/connect', methods=['POST'])
def connect():
    client_id = request.json.get('client_id', 'default')
    try:
        ws_url = f"wss://{CF_WORKER_HOST}/"
        ws = websocket.create_connection(
            ws_url, 
            timeout=15, 
            suppress_origin=True,
            header=["User-Agent: Mozilla/5.0"]
        )
        
        # 1. Drain the buffer to find the version string
        # Duco pools often send MOTD + Version. We need the version.
        version = "3.0"
        time.sleep(1.5)
        
        # Peek at the first few messages to clear the "Welcome" spam
        for _ in range(3):
            ws.settimeout(0.5)
            try:
                msg = ws.recv().strip()
                if msg and len(msg) < 10: # Likely the version (e.g., '3.0')
                    version = msg
            except:
                break
        
        ws.settimeout(20) # Reset to normal
        print(f"📡 [RELAY] {client_id} -> Pool Version: {version}")

        with connection_lock:
            pool_connections[client_id] = {"socket": ws, "version": version}
            
        # Return every possible key to fix the 'None:None' display
        return jsonify({
            "success": True, 
            "version": version,
            "pool_version": version,
            "pool_name": "Cloudflare-Bridge",
            "server": "Duco-Stealth"
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
        
        # Sometimes the pool sends MOTD before the JOB. We must loop until we get a hash.
        for _ in range(3):
            job_data = ws.recv().strip()
            if job_data and "," in job_data: # Valid jobs always have commas
                break
        
        print(f"📦 [JOB] {client_id} received: {job_data[:30]}...")
        return jsonify({"success": True, "job": job_data, "result": job_data})
    except Exception as e:
        print(f"❌ [JOB] Error: {e}")
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
        submission = f"{data['result']},{data['hashrate']},{data['rig_name']},{data.get('key', 'None')}"
        ws.send(submission)
        feedback = ws.recv().strip()
        return jsonify({"success": True, "feedback": feedback})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/disconnect', methods=['POST', 'GET'])
def disconnect():
    client_id = request.json.get('client_id', 'default') if request.is_json else 'default'
    with connection_lock:
        if client_id in pool_connections:
            try:
                pool_connections[client_id]['socket'].close()
                del pool_connections[client_id]
            except:
                pass
    return jsonify({"success": True})

@app.route('/status')
def status():
    return jsonify({"status": "online", "clients": len(pool_connections)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
