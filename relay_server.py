from gevent import monkey
monkey.patch_all()  # MUST be the first two lines

from flask import Flask, request, jsonify
import socket
import threading
import time
import requests

app = Flask(__name__)

# Cache for active pool connections
pool_connections = {}
connection_lock = threading.Lock()

def get_pool_info():
    """Force Port 80 - The ultimate firewall bypass"""
    try:
        # We try to get the IP, but force the port to 80
        r = requests.get("https://server.duinocoin.com/getPool", timeout=10).json()
        if r.get("success"):
            return r["ip"], 80 
    except:
        pass
    return "magi.duinocoin.com", 80 # Fallback to Port 80
    

@app.route('/connect', methods=['POST'])
def connect():
    client_id = request.json.get('client_id', 'default')
    ip, port = get_pool_info()
    
    try:
        print(f"🔌 [RELAY] Client {client_id} connecting to {ip}:{port}...")
        s = socket.socket()
        s.settimeout(15)  # Fast-fail (shorter than bot timeout)
        s.connect((ip, port))
        
        # Get server version (e.g., '3.0')
        version = s.recv(1024).decode().strip()
        
        with connection_lock:
            pool_connections[client_id] = {
                "socket": s, 
                "version": version,
                "last_active": time.time()
            }
        
        print(f"✅ [RELAY] Client {client_id} connected. Pool Version: {version}")
        return jsonify({"success": True, "version": version})
    
    except Exception as e:
        print(f"❌ [RELAY] Connection failed for {client_id}: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/job', methods=['POST'])
def job():
    data = request.json
    client_id = data.get('client_id', 'default')
    username = data.get('username')
    
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False, "error": "Not connected to relay"})
        sock = pool_connections[client_id]['socket']
    
    try:
        sock.send(f"JOB,{username},LOW\n".encode())
        job_data = sock.recv(1024).decode().strip()
        return jsonify({"success": True, "job": job_data})
    except Exception as e:
        return jsonify({"success": False, "error": f"Job fetch failed: {e}"})

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    client_id = data.get('client_id', 'default')
    
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False, "error": "Not connected"})
        sock = pool_connections[client_id]['socket']
    
    try:
        # Format: result,hashrate,rig_name,key
        submission = f"{data['result']},{data['hashrate']},{data['rig_name']},{data.get('key', 'None')}"
        sock.send(f"{submission}\n".encode())
        feedback = sock.recv(1024).decode().strip()
        
        accepted = "GOOD" in feedback or "BLOCK" in feedback
        return jsonify({"success": True, "accepted": accepted, "feedback": feedback})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/status')
def status():
    return jsonify({
        "status": "online", 
        "clients": len(pool_connections),
        "port_forced": 14808
    })

@app.route('/')
def home():
    return "Duino-Coin Relay is Running on Port 14808 Bypass Mode."

if __name__ == '__main__':
    # Local testing
    app.run(host='0.0.0.0', port=10000)
    
