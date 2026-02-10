from gevent import monkey
monkey.patch_all()  # THIS REPLACES THE EVENTLET MONKEY PATCH


from flask import Flask, request, jsonify
import socket
import threading
import time
import requests

app = Flask(__name__)
pool_connections = {}
connection_lock = threading.Lock()

def get_pool_info():
    """Get pool info with longer timeout and fallback hostname"""
    try:
        r = requests.get("https://server.duinocoin.com/getPool", timeout=20).json()
        if r.get("success"):
            return r["ip"], r.get("port", 2813)
    except:
        pass
    return "magi.duinocoin.com", 2813

@app.route('/connect', methods=['POST'])
def connect():
    client_id = request.json.get('client_id', 'default')
    ip, port = get_pool_info()
    try:
        s = socket.socket()
        s.settimeout(60) # Increased timeout for Render stability
        s.connect((ip, port))
        version = s.recv(1024).decode().strip()
        with connection_lock:
            pool_connections[client_id] = {"socket": s, "version": version}
        return jsonify({"success": True, "version": version})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/job', methods=['POST'])
def job():
    client_id = request.json.get('client_id', 'default')
    username = request.json.get('username')
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False, "error": "Not connected"})
        sock = pool_connections[client_id]['socket']
    try:
        sock.send(f"JOB,{username},LOW\n".encode())
        return jsonify({"success": True, "job": sock.recv(1024).decode().strip()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    client_id = data.get('client_id', 'default')
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False, "error": "Not connected"})
        sock = pool_connections[client_id]['socket']
    try:
        result = f"{data['result']},{data['hashrate']},{data['rig_name']}"
        sock.send(f"{result}\n".encode())
        feedback = sock.recv(1024).decode().strip()
        return jsonify({"success": True, "feedback": feedback})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/status')
def status():
    return jsonify({"status": "online", "active_clients": len(pool_connections)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
