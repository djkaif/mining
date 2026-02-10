from gevent import monkey
monkey.patch_all()

from flask import Flask, request, jsonify
import websocket  # Using websocket instead of socket
import threading
import time
import requests

app = Flask(__name__)
pool_connections = {}
connection_lock = threading.Lock()

def get_pool_info():
    # We still fetch the pool IP, but we'll connect via the WS proxy
    try:
        r = requests.get("https://server.duinocoin.com/getPool", timeout=10).json()
        if r.get("success"):
            return r["ip"]
    except:
        pass
    return "magi.duinocoin.com"

@app.route('/connect', methods=['POST'])
def connect():
    client_id = request.json.get('client_id', 'default')
    pool_ip = get_pool_info()
    
    try:
        # We connect to the Official DUCO WebSocket Proxy (Port 14808 usually handles WS)
        # If raw sockets are blocked, we use the WSS (Secure WebSocket) bridge
        ws_url = f"ws://{pool_ip}:14808/" 
        
        ws = websocket.create_connection(ws_url, timeout=15)
        version = ws.recv().strip() # Receive version
        
        with connection_lock:
            pool_connections[client_id] = {"socket": ws, "version": version}
            
        return jsonify({"success": True, "version": version})
    except Exception as e:
        return jsonify({"success": False, "error": f"WS Bridge Failed: {e}"})

@app.route('/job', methods=['POST'])
def job():
    client_id = request.json.get('client_id', 'default')
    username = request.json.get('username')
    
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False, "error": "Not connected"})
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
        if client_id not in pool_connections: return jsonify({"success": False})
        ws = pool_connections[client_id]['socket']
        
    try:
        result = f"{data['result']},{data['hashrate']},{data['rig_name']}"
        ws.send(result)
        feedback = ws.recv().strip()
        return jsonify({"success": True, "feedback": feedback})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/status')
def status():
    return jsonify({"status": "online", "bridge": "websocket"})

@app.route('/')
def home():
    return "WebSocket Relay Active"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
