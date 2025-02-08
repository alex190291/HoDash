##### app.py (modified - corrected get_docker_info call) #####
from flask import Flask, render_template, jsonify
import threading
import logging
import queue # Import queue explicitly
from database import db_state
from dockermod import docker_state, update_container_task, start_docker_updater, task_check_all_updates, get_docker_info # Import get_docker_info

app = Flask(__name__)
task_queue = queue.Queue() # Initialize task queue here

# Start the worker thread for background task processing (database tasks)
def start_db_task_worker():
    worker_thread = threading.Thread(target=db_state.process_task_queue, daemon=True)
    worker_thread.start()

# Start the docker updater thread (image update checks)
def start_docker_workers():
    start_docker_updater(task_queue) # Pass task_queue instance to docker updater

# Worker thread for processing the task queue (general tasks, including docker updates)
def task_worker():
    while True:
        task = task_queue.get()
        try:
            task()
        except Exception as e:
            logging.error(f"Task processing error: {e}")
        finally:
            task_queue.task_done()

# Start the general task worker thread
def start_general_task_worker():
    worker_thread = threading.Thread(target=task_worker, daemon=True)
    worker_thread.start()


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stats')
def stats():
    # Return current stats, ensuring the latest data is fetched
    return jsonify({
        'cpu_history': db_state.get_cpu_history(),
        'memory_history_basic': db_state.get_memory_history_basic(),
        'disk_history_basic': db_state.get_disk_history_basic(),
        'cpu_history_24h': db_state.get_cpu_history_24h(),
        'memory_history_24h': db_state.get_memory_history_24h(),
        'disk_history': db_state.get_disk_history(),
        'network_history': db_state.get_network_history(),
        'docker': get_docker_info() # Call get_docker_info function directly
    })

@app.route('/update_status/<container_name>', methods=['GET'])
def update_status(container_name):
    # This route would check and return the update status for a container.
    container_status = docker_state.get_updating_containers().get(container_name)
    if container_status:
        return jsonify(container_status)
    return jsonify({"status": "Container not found"}), 404

@app.route('/update_container/<container_name>', methods=['POST'])
def update_container(container_name):
    # Add the update container task to the task queue
    docker_state.set_updating_container(container_name, {"phase": "starting update", "in_progress": True})
    task_queue.put(lambda: update_container_task(container_name)) # Use task_queue.put and dockermod.update_container_task
    return jsonify({"status": "Update started"}), 202

@app.route('/check_all', methods=['POST'])
def check_all():
    if docker_state.is_checking_all_updates():
        return jsonify({"status": "already_in_progress"}), 200 # or 409 Conflict
    task_queue.put(task_check_all_updates)
    return jsonify({"status": "check_started"}), 202

@app.route('/check_all_status', methods=['GET'])
def check_all_status():
    return jsonify({
        "in_progress": docker_state.is_checking_all_updates(),
        "checked": docker_state.get_checked_container_count(),
        "total": docker_state.get_total_container_count()
    })


# Removed old task_update_container function as it's replaced by dockermod.update_container_task

if __name__ == '__main__':
    # Initialize background workers and start Flask app
    start_db_task_worker()
    start_docker_workers()
    start_general_task_worker() # Start the general task worker
    app.run(host='0.0.0.0', port=5000)
