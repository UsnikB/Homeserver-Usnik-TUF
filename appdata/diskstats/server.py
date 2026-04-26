import subprocess, json
from http.server import HTTPServer, BaseHTTPRequestHandler

DISKS = {
    'e': '/mnt/e',
    'd': '/mnt/d',
}

try:
    import pynvml
    pynvml.nvmlInit()
    NVML_OK = True
except Exception:
    NVML_OK = False

def get_disk(path):
    try:
        out = subprocess.check_output(['df', '-B1', path], text=True).splitlines()[1].split()
        return {'size': int(out[1]), 'used': int(out[2]), 'free': int(out[3]), 'percent': float(out[4].rstrip('%'))}
    except Exception as ex:
        return {'error': str(ex)}

def get_gpu():
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        return {
            'util': util.gpu,
            'mem_used': mem.used // (1024 * 1024),
            'mem_total': mem.total // (1024 * 1024),
            'temp': temp,
        }
    except Exception as ex:
        return {'error': str(ex)}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/gpu':
            data = get_gpu() if NVML_OK else {'error': 'pynvml not available'}
        else:
            data = {k: get_disk(v) for k, v in DISKS.items()}
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

HTTPServer(('0.0.0.0', 61209), Handler).serve_forever()
