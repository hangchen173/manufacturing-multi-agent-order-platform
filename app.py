import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from core.orchestrator import OrderProcessingOrchestrator

app = Flask(__name__)
CORS(app)

config = Config()
orchestrator = OrderProcessingOrchestrator()

UPLOAD_FOLDER = 'data/sample_orders'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf', 'xlsx', 'xls', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'success': True,
        'message': 'Service is running',
        'status': 'healthy'
    })

@app.route('/api/upload', methods=['POST'])
def upload_order():
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'message': 'No file part in the request'
        }), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({
            'success': False,
            'message': 'No file selected for uploading'
        }), 400
    
    if file and allowed_file(file.filename):
        import uuid
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        result = orchestrator.process_order_from_document(filepath)
        
        return jsonify(result)
    
    return jsonify({
        'success': False,
        'message': 'File type not allowed'
    }), 400

@app.route('/api/upload_text', methods=['POST'])
def upload_order_text():
    data = request.get_json()
    
    if not data or 'order_text' not in data:
        return jsonify({
            'success': False,
            'message': 'order_text is required'
        }), 400
    
    order_text = data['order_text']
    result = orchestrator.process_order_from_text(order_text)
    
    return jsonify(result)

@app.route('/api/query_status/<order_id>', methods=['GET'])
def query_status(order_id):
    status = orchestrator.get_order_status(order_id)
    
    if not status:
        return jsonify({
            'success': False,
            'message': 'Order not found'
        }), 404
    
    return jsonify({
        'success': True,
        'data': status
    })

@app.route('/api/confirm/<order_id>', methods=['POST'])
def confirm_order(order_id):
    data = request.get_json()
    
    if not data or 'action' not in data:
        return jsonify({
            'success': False,
            'message': 'action is required (confirm or reject)'
        }), 400
    
    action = data['action']
    if action not in ['confirm', 'reject']:
        return jsonify({
            'success': False,
            'message': 'Invalid action. Must be either confirm or reject'
        }), 400
    
    result = orchestrator.confirm_order(order_id, {'action': action})
    
    if not result['success']:
        return jsonify(result), 400
    
    return jsonify(result)

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Resource not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': 'Internal server error'
    }), 500

if __name__ == '__main__':
    print(f"Starting server on http://localhost:{config.FLASK_PORT}")
    app.run(
        host='0.0.0.0',
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG
    )
