"""
Duino-Coin Mining Relay Server
Deployed on Render.com (free tier)

This acts as a proxy/tunnel between restricted bots and mining pools.
Perfect example of penetration testing relay technique!
"""

from flask import Flask, request, jsonify
import socket
import threading
import time

app = Flask(__name__)

# Pool connection cache
pool_connections = {}
connection_lock = threading.Lock()

def get_pool_info():
    """Get current best mining pool"""
    import requests
    try:
        response = requests.get("https://server.duinocoin.com/getPool", timeout=10).json()
        if response.get("success"):
            return response["ip"], response.get("port", 2813)
    except:
        pass
    return "149.91.88.18", 2813

def create_pool_connection(client_id):
    """Create a persistent connection to the mining pool"""
    ip, port = get_pool_info()
    
    try:
        s = socket.socket()
        s.settimeout(30)
        s.connect((ip, port))
        
        # Receive server version
        version = s.recv(1024).decode().strip()
        
        with connection_lock:
            pool_connections[client_id] = {
                "socket": s,
                "version": version,
                "created": time.time()
            }
        
        return {"success": True, "version": version, "ip": ip, "port": port}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/')
def home():
    return '''
    <h1>🔓 Duino-Coin Mining Relay Server</h1>
    <p>This server acts as a proxy between restricted bots and mining pools.</p>
    <p><strong>Endpoints:</strong></p>
    <ul>
        <li>POST /connect - Establish pool connection</li>
        <li>POST /job - Request mining job</li>
        <li>POST /submit - Submit work result</li>
        <li>GET /status - Server status</li>
    </ul>
    <p>🎓 Educational penetration testing technique - Relay/Proxy pattern</p>
    '''

@app.route('/status')
def status():
    """Server status endpoint"""
    return jsonify({
        "status": "online",
        "active_connections": len(pool_connections),
        "relay_server": "Duino-Coin Mining Proxy",
        "technique": "HTTPS Relay Bypass"
    })

@app.route('/connect', methods=['POST'])
def connect():
    """Establish connection to mining pool"""
    data = request.json
    client_id = data.get('client_id', 'default')
    
    # Clean old connections (older than 5 minutes)
    with connection_lock:
        current_time = time.time()
        expired = [cid for cid, conn in pool_connections.items() 
                   if current_time - conn['created'] > 300]
        for cid in expired:
            try:
                pool_connections[cid]['socket'].close()
            except:
                pass
            del pool_connections[cid]
    
    result = create_pool_connection(client_id)
    
    if result['success']:
        print(f"✅ [RELAY] Client {client_id} connected to pool")
    else:
        print(f"❌ [RELAY] Client {client_id} connection failed: {result['error']}")
    
    return jsonify(result)

@app.route('/job', methods=['POST'])
def request_job():
    """Request mining job from pool"""
    data = request.json
    client_id = data.get('client_id', 'default')
    username = data.get('username', 'unknown')
    mining_key = data.get('mining_key', 'None')
    
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False, "error": "Not connected. Call /connect first"})
        
        conn = pool_connections[client_id]
        sock = conn['socket']
    
    try:
        # Request job from pool
        job_request = f"JOB,{username},LOW,{mining_key}\n"
        sock.send(job_request.encode())
        
        # Receive job
        job_response = sock.recv(1024).decode().strip()
        
        if not job_response:
            return jsonify({"success": False, "error": "Empty response from pool"})
        
        job_parts = job_response.split(",")
        
        if len(job_parts) >= 3:
            return jsonify({
                "success": True,
                "last_hash": job_parts[0],
                "expected_hash": job_parts[1],
                "difficulty": int(job_parts[2])
            })
        else:
            return jsonify({"success": False, "error": "Invalid job format"})
    
    except Exception as e:
        print(f"❌ [RELAY] Job request error: {e}")
        # Connection died, remove it
        with connection_lock:
            if client_id in pool_connections:
                try:
                    pool_connections[client_id]['socket'].close()
                except:
                    pass
                del pool_connections[client_id]
        
        return jsonify({"success": False, "error": str(e)})

@app.route('/submit', methods=['POST'])
def submit_work():
    """Submit mining work to pool"""
    data = request.json
    client_id = data.get('client_id', 'default')
    result = data.get('result')
    rig_name = data.get('rig_name', 'RelayMiner')
    
    with connection_lock:
        if client_id not in pool_connections:
            return jsonify({"success": False, "error": "Not connected"})
        
        conn = pool_connections[client_id]
        sock = conn['socket']
    
    try:
        # Submit work
        submit_msg = f"{result},,PythonMiner,{rig_name}\n"
        sock.send(submit_msg.encode())
        
        # Get feedback
        feedback = sock.recv(1024).decode().strip()
        
        accepted = "GOOD" in feedback or "BLOCK" in feedback
        
        return jsonify({
            "success": True,
            "accepted": accepted,
            "feedback": feedback
        })
    
    except Exception as e:
        print(f"❌ [RELAY] Submit error: {e}")
        with connection_lock:
            if client_id in pool_connections:
                try:
                    pool_connections[client_id]['socket'].close()
                except:
                    pass
                del pool_connections[client_id]
        
        return jsonify({"success": False, "error": str(e)})

@app.route('/disconnect', methods=['POST'])
def disconnect():
    """Disconnect from pool"""
    data = request.json
    client_id = data.get('client_id', 'default')
    
    with connection_lock:
        if client_id in pool_connections:
            try:
                pool_connections[client_id]['socket'].close()
            except:
                pass
            del pool_connections[client_id]
            return jsonify({"success": True, "message": "Disconnected"})
        else:
            return jsonify({"success": False, "error": "Not connected"})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    print(f"🔓 Starting Duino-Coin Relay Server on port {port}")
    print(f"🎓 Educational penetration testing: HTTPS Relay technique")
    app.run(host='0.0.0.0', port=port)

