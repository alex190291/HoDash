##### dockermod.py (modified - using DockerClient) #####
import docker
import time
import threading
import logging
from datetime import datetime


client = docker.from_env()
updating_containers = {}
image_update_info = {}

def parse_docker_created(created_str):
    if created_str.endswith('Z'):
        created_str = created_str[:-1]
    if '.' in created_str:
        base, frac = created_str.split('.', 1)
        frac = frac[:6]
        created_str = base + '.' + frac
        fmt = '%Y-%m-%dT%H:%M:%S.%f'
    else:
        fmt = '%Y-%m-%dT%H:%M:%S'
    try:
        return datetime.strptime(created_str, fmt)
    except:
        return datetime.now()

def get_docker_info():
    """
    Returns a list of container info.
    If a container is in updating_containers but not in the real Docker list, we create a "virtual" container object.
    Also, if it *is* found, we override the status with the current "phase" if in progress.
    """
    containers = []
    real_containers = {c.name: c for c in client.containers.list(all=True)}

    for cname, container in real_containers.items():
        try:
            created = container.attrs.get('Created', '')
            dt_created = parse_docker_created(created) if created else datetime.now()
            uptime = int(time.time() - dt_created.timestamp())
        except Exception:
            uptime = 0

        if container.image.tags:
            display_image = container.image.tags[0]
            used_image = display_image
            is_up_to_date = image_update_info.get(cname, True)
        elif "RepoDigests" in container.image.attrs and container.image.attrs["RepoDigests"]:
            repo_digest = container.image.attrs["RepoDigests"][0]
            repo_name = repo_digest.split("@")[0]
            used_image = repo_name + ":latest"
            display_image = repo_name
            is_up_to_date = image_update_info.get(cname, True)
        else:
            display_image = "untagged"
            used_image = "untagged"
            is_up_to_date = False

        status_str = container.status
        if cname in updating_containers:
            ud = updating_containers[cname]
            if ud["in_progress"]:
                status_str = f"Updating ({ud.get('phase','')})"
            elif ud["error"]:
                status_str = f"Update failed: {ud['error']}"
            elif ud["success"]:
                status_str = "Update success"

        containers.append({
            'name': cname,
            'status': status_str,
            'image': display_image,
            'used_image': used_image,
            'created': container.attrs.get('Created', ''),
            'uptime': uptime,
            'up_to_date': is_up_to_date
        })

    for cname, ud in updating_containers.items():
        if cname not in real_containers:
            phase_str = ud.get("phase", "Updating")
            status_str = f"Updating ({phase_str})"
            if ud["error"]:
                status_str = f"Update failed: {ud['error']}"
            elif ud["success"]:
                status_str = "Update success"
            containers.append({
                'name': cname,
                'status': status_str,
                'image': "(updating...)",
                'used_image': "(updating...)",
                'created': "",
                'uptime': 0,
                'up_to_date': False
            })

    return containers

def check_container_image_update(container):
    global image_update_info
    if container.image.tags:
        image_tag = container.image.tags[0]
    else:
        repo_digest = container.image.attrs.get("RepoDigests", [])
        if repo_digest:
            repo_name = repo_digest[0].split("@")[0]
            image_tag = repo_name + ":latest"
        else:
            return False # cannot check for update
    try:
        latest_img = client.images.pull(image_tag)
    except Exception as e:
        logging.error(f"Error pulling image for update check of {image_tag}: {e}")
        return False
    image_update_info[container.name] = (container.image.id == latest_img.id)
    return image_update_info[container.name]


def check_image_updates(): # Periodic check, still kept for background updates
    global image_update_info
    while True:
        try:
            for container in client.containers.list(all=True):
                check_container_image_update(container)
        except Exception as e:
            logging.error(f"Error in check_image_updates loop: {e}")
        time.sleep(60)

def update_container_task(cname): # Renamed to *_task to indicate it's a task for the queue
    global updating_containers, image_update_info

    if cname in updating_containers:
        del updating_containers[cname]

    updating_containers[cname] = {
        "phase": "preparing...",
        "new_image_id": None,
        "in_progress": True,
        "error": None,
        "success": False
    }

    def do_update(cname):
        error_occurred = False
        error_message = None
        new_container = None
        try:
            old_container = client.containers.get(cname)
            container_config = old_container.attrs['Config']
            host_config = old_container.attrs['HostConfig']
            networking_config = old_container.attrs['NetworkSettings']

            updating_containers[cname]["phase"] = "pulling new image..."
            if old_container and old_container.image.tags:
                image_tag = old_container.image.tags[0]
            else:
                if old_container and old_container.image.attrs.get("RepoDigests"):
                    repo_digest = old_container.image.attrs["RepoDigests"][0]
                    repo_name = repo_digest.split("@")[0]
                    image_tag = repo_name + ":latest"
                else:
                    error_message = "No valid image tag/digest found"
                    raise Exception(error_message)

            fresh_img = None
            try:
                fresh_img = client.images.pull(image_tag)
            except Exception as pull_e:
                error_message = f"Error pulling {image_tag}: {str(pull_e)}"
                raise Exception(error_message)

            if fresh_img:
                updating_containers[cname]["new_image_id"] = fresh_img.id

            updating_containers[cname]["phase"] = "stopping old container..."
            try:
                old_container.stop()
            except Exception as stop_e:
                error_message = f"Error stopping container {cname}: {str(stop_e)}"
                raise Exception(error_message)

            updating_containers[cname]["phase"] = "removing old container..."
            try:
                old_container.remove()
            except Exception as remove_e:
                error_message = f"Error removing container {cname}: {str(remove_e)}"
                raise Exception(error_message)

            updating_containers[cname]["phase"] = "starting new container..."
            try:
                # Recreate container with old configuration but new image
                new_container = client.containers.run(
                    fresh_img.id,
                    detach=True,
                    name=cname, # Keep the same name! Important for persistent volumes and links
                    ports=container_config.get('ExposedPorts'),
                    environment=container_config.get('Env'),
                    volumes=host_config.get('Binds'),
                    network_mode=host_config.get('NetworkMode'),
                    restart_policy=host_config.get('RestartPolicy'),
                    dns=host_config.get('Dns'),
                    dns_search=host_config.get('DnsSearch'),
                    links=host_config.get('Links'), # Deprecated, consider using networks instead
                    privileged=host_config.get('Privileged'),
                    capabilities=host_config.get('CapAdd'), # and CapDrop
                    security_opt=host_config.get('SecurityOpt')
                    # Add more configurations as needed from container_config and host_config
                )
            except Exception as start_e:
                error_message = f"Error starting new container {cname}: {str(start_e)}"
                raise Exception(error_message)

            updating_containers[cname]["phase"] = "verifying update..."
            time.sleep(5) # Give it some time to start

            new_cont_status = client.containers.get(cname).status
            if new_cont_status not in ['running', 'restarting']: # Check for running or restarting status
                error_message = f"New container did not start correctly, status: {new_cont_status}"
                raise Exception(error_message)


            image_update_info[cname] = True
            updating_containers[cname]["success"] = True
            updating_containers[cname]["phase"] = "success"


        except Exception as e:
            error_occurred = True
            if error_message is None:
                error_message = str(e)
            logging.error(f"Error updating container '{cname}': {error_message}")
            updating_containers[cname]["error"] = error_message
            updating_containers[cname]["phase"] = "failed"
        finally:
            updating_containers[cname]["in_progress"] = False
            if error_occurred and new_container:
                try:
                    logging.info(f"Cleaning up potentially failed new container {cname}...")
                    new_container.stop()
                    new_container.remove()
                    updating_containers[cname]["phase"] = "failed - cleanup done"
                except Exception as cleanup_e:
                    logging.error(f"Error during cleanup of failed container {cname}: {cleanup_e}")
                    updating_containers[cname]["phase"] = "failed - cleanup error"


    threading.Thread(target=do_update, args=(cname,), daemon=True).start()


class DockerState:
    def __init__(self):
        self.updating_containers_lock = threading.Lock()
        self.image_update_info_lock = threading.Lock()
        self.check_all_updates_lock = threading.Lock() # Lock for check_all_updates status
        self._updating_containers = {}
        self._image_update_info = {}
        self._is_checking_all_updates = False # Track if check all updates is in progress
        self._checked_container_count = 0
        self._total_container_count = 0

    def get_updating_containers(self):
        with self.updating_containers_lock:
            return self._updating_containers.copy()

    def set_updating_container(self, container_name, status):
        with self.updating_containers_lock:
            self._updating_containers[container_name] = status

    def get_image_update_info(self):
        with self.image_update_info_lock:
            return self._image_update_info.copy()

    def set_image_update_info(self, container_name, is_up_to_date):
        with self.image_update_info_lock:
            self._image_update_info[container_name] = is_up_to_date

    def is_checking_all_updates(self):
        with self.check_all_updates_lock:
            return self._is_checking_all_updates

    def set_is_checking_all_updates(self, value):
        with self.check_all_updates_lock:
            self._is_checking_all_updates = value

    def get_checked_container_count(self):
        with self.check_all_updates_lock:
            return self._checked_container_count

    def set_checked_container_count(self, value):
        with self.check_all_updates_lock:
            self._checked_container_count = value

    def get_total_container_count(self):
        with self.check_all_updates_lock:
            return self._total_container_count

    def set_total_container_count(self, value):
        with self.check_all_updates_lock:
            self._total_container_count = value


docker_state = DockerState()
task_queue = None # Will be set from app.py

def start_docker_updater(task_queue_instance): # Pass task_queue instance
    global task_queue
    task_queue = task_queue_instance
    threading.Thread(target=check_image_updates, daemon=True).start()

def task_check_all_updates():
    global docker_state
    if docker_state.is_checking_all_updates():
        logging.info("Check all updates already in progress, skipping.")
        return

    docker_state.set_is_checking_all_updates(True)
    docker_state.set_checked_container_count(0)
    containers_to_check = client.containers.list(all=True)
    docker_state.set_total_container_count(len(containers_to_check))
    logging.info(f"Starting check all updates for {docker_state.get_total_container_count()} containers.")

    try:
        for container in containers_to_check:
            check_container_image_update(container) # Update image_update_info
            docker_state.set_checked_container_count(docker_state.get_checked_container_count() + 1)
            logging.info(f"Checked container {container.name} ({docker_state.get_checked_container_count()}/{docker_state.get_total_container_count()})")
    except Exception as e:
        logging.error(f"Error during check_all_updates: {e}")
    finally:
        docker_state.set_is_checking_all_updates(False)
        logging.info("Check all updates finished.")
