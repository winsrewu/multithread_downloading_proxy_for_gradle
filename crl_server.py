from flask import Flask, send_file
from configs import CRL_FILE, CRL_SERVER_HOST, CRL_SERVER_PORT
import waitress

app = Flask(__name__)

@app.route('/crl.pem')
def serve_crl():
    """Serve the Certificate Revocation List file"""
    return send_file(CRL_FILE, mimetype='application/x-pem-file')

def start_crl_server():
    """Start the CRL server in a separate thread"""
    waitress.serve(
        app,
        host=CRL_SERVER_HOST,
        port=CRL_SERVER_PORT,
        threads=4
    )

if __name__ == '__main__':
    start_crl_server()
