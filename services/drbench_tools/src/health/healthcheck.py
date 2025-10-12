#!/usr/bin/env python3
import logging
import os
import socket
import subprocess
import time

import requests
from flask import Flask, jsonify, render_template_string

# Configure logging
logger = logging.getLogger("healthcheck")

with open("src/health/index_template.html", "r") as f:
    HTML_TEMPLATE = f.read()

app = Flask(__name__)


@app.template_filter("timestamp_to_time")
def timestamp_to_time(timestamp):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


@app.route("/")
def index():
    health_data = global_health_data()
    return render_template_string(HTML_TEMPLATE, data=health_data)


@app.route("/health")
def health():
    health_data = global_health_data()
    status_code = 200 if health_data["status"] == "healthy" else 503
    return jsonify(health_data), status_code


def global_health_data():
    services = {
        "mattermost": check_mattermost(),
        "nextcloud": check_nextcloud(),
        "email": check_email(),
        "vnc": check_vnc(),
        "novnc": check_novnc(),
        "filebrowser": check_filebrowser(),
    }

    all_healthy = all(service["status"] == "healthy" for service in services.values())
    all_ready = all(service["ready"] for service in services.values())

    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "ready": all_ready,
        "services": services,
        "timestamp": time.time(),
    }


def check_mattermost():
    logger.debug("Checking Mattermost health...")
    ready = os.path.exists("/tmp/mattermost_initialized")
    try:
        response = requests.get("http://localhost:8082/api/v4/system/ping", timeout=2)
        status = "healthy" if response.status_code == 200 else "unhealthy"

        if response.status_code == 200:
            try:
                response_data = response.json()
                if response_data.get("status") != "OK":
                    status = "unhealthy"
            except ValueError:
                status = "unhealthy"

        details = {"response_code": response.status_code, "initialized": ready}

        try:
            details["response"] = response.json()
        except ValueError:
            details["response"] = response.text[:100] + "..." if len(response.text) > 100 else response.text

        return {"status": status, "ready": ready, "details": details}
    except Exception as e:
        logger.warning(f"Mattermost health check failed: {str(e)}")
        return {"status": "unhealthy", "ready": False, "details": {"error": str(e), "initialized": ready}}


def check_nextcloud():
    logger.debug("Checking Nextcloud health...")
    ready = os.path.exists("/var/www/nextcloud/config/config.php")

    try:
        response = requests.get("http://localhost:8081/status.php", timeout=2)
        status = "unhealthy"

        if response.status_code == 200:
            try:
                response_data = response.json()
                if response_data.get("installed") is True and response_data.get("maintenance") is False:
                    status = "healthy"
            except ValueError:
                pass

        details = {"response_code": response.status_code, "config_exists": ready}

        try:
            details["response"] = response.json()
        except ValueError:
            details["response"] = response.text[:100] + "..." if len(response.text) > 100 else response.text

        return {"status": status, "ready": ready, "details": details}
    except Exception as e:
        logger.warning(f"Nextcloud health check failed: {str(e)}")
        return {"status": "unhealthy", "ready": False, "details": {"error": str(e), "config_exists": ready}}


def check_vnc():
    logger.debug("Checking VNC health...")
    # Check if vnc process is running
    try:
        # Use ps to check for x11vnc process
        result = subprocess.run(["pgrep", "x11vnc"], capture_output=True, text=True)
        process_running = result.returncode == 0

        # Try socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        socket_result = sock.connect_ex(("localhost", 5901))
        sock.close()

        socket_ok = socket_result == 0

        details = {"process_running": process_running, "port_accessible": socket_ok}

        if result.stdout:
            details["process_ids"] = result.stdout.strip().split("\n")

        status = "healthy" if process_running and socket_ok else "unhealthy"
        ready = process_running and socket_ok

        return {"status": status, "ready": ready, "details": details}
    except Exception as e:
        logger.warning(f"VNC health check failed: {str(e)}")
        return {"status": "unhealthy", "ready": False, "details": {"error": str(e)}}


def check_novnc():
    logger.debug("Checking NoVNC health...")
    # NoVNC depends on VNC, so check VNC first
    vnc_health = check_vnc()

    try:
        response = requests.get("http://localhost:6080/", timeout=2)

        websocket_check = False
        if response.status_code == 200:
            # Check for websockify process
            result = subprocess.run(["pgrep", "websockify"], capture_output=True, text=True)
            websocket_check = result.returncode == 0

        details = {
            "response_code": response.status_code,
            "websockify_running": websocket_check,
            "vnc_status": vnc_health["status"],
            "response_size": len(response.text),
        }

        # Websockify is not strictly necessary for NoVNC to be healthy, but it's a good indicator
        status = "healthy" if response.status_code == 200 else "unhealthy"  # and websocket_check else "unhealthy"

        # NoVNC is ready if both it and VNC are healthy
        ready = status == "healthy" and vnc_health["status"] == "healthy"

        return {"status": status, "ready": ready, "details": details}
    except Exception as e:
        logger.warning(f"NoVNC health check failed: {str(e)}")
        return {"status": "unhealthy", "ready": False, "details": {"error": str(e), "vnc_status": vnc_health["status"]}}


def check_filebrowser():
    logger.debug("Checking Filebrowser health...")
    ready = os.path.exists("/var/lib/filebrowser/.setup_complete")

    try:
        # Filebrowser doesn't have a dedicated health endpoint, so we check the main page
        response = requests.get("http://localhost:8090/", timeout=2, allow_redirects=True)

        details = {"response_code": response.status_code, "setup_complete": ready, "url_after_redirects": response.url}

        # Check if the response looks like Filebrowser (login page or file list)
        is_filebrowser_resp = "filebrowser" in response.text.lower() or "login" in response.text.lower()
        status = "healthy" if response.status_code in (200, 302) and is_filebrowser_resp else "unhealthy"

        # Also check if we can get the version info
        try:
            version_response = requests.get("http://localhost:8090/api/version", timeout=1)
            if version_response.status_code == 200:
                details["version"] = version_response.json()
        except:
            pass

        return {"status": status, "ready": ready, "details": details}
    except Exception as e:
        logger.warning(f"Filebrowser health check failed: {str(e)}")
        return {"status": "unhealthy", "ready": False, "details": {"error": str(e), "setup_complete": ready}}


def check_email():
    logger.debug("Checking Email services health...")
    ready = os.path.exists("/tmp/mail_data_initialized")
    
    services_status = {}
    
    # Check Postfix
    try:
        # Check if Postfix process is running
        postfix_result = subprocess.run(["pgrep", "-f", "postfix"], capture_output=True, text=True)
        postfix_running = postfix_result.returncode == 0
        
        # Check SMTP port (using non-reserved port 1025)
        smtp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        smtp_sock.settimeout(1)
        smtp_result = smtp_sock.connect_ex(("localhost", 1025))
        smtp_sock.close()
        smtp_accessible = smtp_result == 0
        
        services_status["postfix"] = {
            "process_running": postfix_running,
            "smtp_port_accessible": smtp_accessible,
            "status": "healthy" if postfix_running and smtp_accessible else "unhealthy"
        }
    except Exception as e:
        services_status["postfix"] = {"status": "unhealthy", "error": str(e)}
    
    # Check Dovecot
    try:
        # Check if Dovecot process is running
        dovecot_result = subprocess.run(["pgrep", "-f", "dovecot"], capture_output=True, text=True)
        dovecot_running = dovecot_result.returncode == 0
        
        # Check IMAP port (using non-reserved port 1143)
        imap_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        imap_sock.settimeout(1)
        imap_result = imap_sock.connect_ex(("localhost", 1143))
        imap_sock.close()
        imap_accessible = imap_result == 0
        
        services_status["dovecot"] = {
            "process_running": dovecot_running,
            "imap_port_accessible": imap_accessible,
            "status": "healthy" if dovecot_running and imap_accessible else "unhealthy"
        }
    except Exception as e:
        services_status["dovecot"] = {"status": "unhealthy", "error": str(e)}
    
    # Check Roundcube
    try:
        response = requests.get("http://localhost:8085/", timeout=2, allow_redirects=True)
        roundcube_accessible = response.status_code == 200
        
        # Check if it's actually Roundcube by looking for specific indicators
        is_roundcube = "roundcube" in response.text.lower() or "rcube" in response.text.lower()
        
        services_status["roundcube"] = {
            "response_code": response.status_code,
            "accessible": roundcube_accessible,
            "is_roundcube_page": is_roundcube,
            "status": "healthy" if roundcube_accessible and is_roundcube else "unhealthy"
        }
    except Exception as e:
        services_status["roundcube"] = {"status": "unhealthy", "error": str(e)}
    
    # Check email user count
    try:
        if os.path.exists("/etc/dovecot/passwd"):
            with open("/etc/dovecot/passwd", "r") as f:
                user_count = len([line for line in f if line.strip()])
            services_status["users"] = {"count": user_count}
    except Exception as e:
        services_status["users"] = {"error": str(e)}
    
    # Overall email system health
    all_healthy = all(
        service.get("status") == "healthy" 
        for service in [services_status.get("postfix", {}), 
                        services_status.get("dovecot", {}), 
                        services_status.get("roundcube", {})]
    )
    
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "ready": ready and all_healthy,
        "details": {
            "initialized": ready,
            "services": services_status
        }
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # Add delay to ensure other services have started
    logger.info("Starting health check service...")
    
    # Get port from environment variable or use default
    port = int(os.environ.get("HEALTHCHECK_PORT", "8099"))
    logger.info(f"Health check service will listen on port {port}")
    
    app.run(host="0.0.0.0", port=port)
