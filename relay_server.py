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
    
    try:
        # Use the official Secure WebSocket bridge (WSS) on Port 443
        # This is what the Web Wallet uses to bypass strict firewalls
        ws_url = "wss://server.duinocoin.com:14808/" 
        
        print(f"🔌 [RELAY] Client {client_id} connecting to Secure Bridge...")
        
        # We use a 20-second timeout to give Render's slow network time to handshake
        ws = websocket.create_connection(ws_url, timeout=20)
        version = ws.recv().strip()
        
        with connection_lock:
            pool_connections[client_id] = {"socket": ws, "version": version}
            
        print(f"✅ [RELAY] Connected via WSS Bridge! Pool Version: {version}")
        return jsonify({"success": True, "version": version})
    except Exception as e:
        print(f"❌ [RELAY] WSS Bridge Failed: {e}")
        return jsonify({"success": False, "error": f"WSS Bridge Failed: {e}"})
        

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
