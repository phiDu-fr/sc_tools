from flask import Blueprint, jsonify, request
import json
import time
import requests
from apscheduler.triggers.cron import CronTrigger

import shared

alarm_bp = Blueprint('alarm_bp', __name__)

def trigger_bose_alarm(ip, preset):
    print(f"⏰ [ALARM] Déclenchement sur {ip} avec le {preset} !")
    try:
        requests.post(f"http://{ip}:8090/volume", data='<volume>25</volume>', headers={"Content-Type": "application/xml"}, timeout=2)
        time.sleep(1)
        requests.post(f"http://{ip}:8090/key", data=f'<key state="release" sender="Gabbo">{preset}</key>'.encode('utf-8'), headers={"Content-Type": "application/xml"}, timeout=2)
    except Exception as e: print(f"❌ Erreur alarme: {e}")

def sync_alarms_to_scheduler(alarms):
    for job in shared.scheduler.get_jobs(): shared.scheduler.remove_job(job.id)
    day_map = {"0": "sun", "1": "mon", "2": "tue", "3": "wed", "4": "thu", "5": "fri", "6": "sat"}
    for idx, a in enumerate(alarms):
        ap_days = ",".join([day_map[d.strip()] for d in a['days'].split(',') if d.strip() in day_map])
        trigger = CronTrigger(minute=a['minute'], hour=a['hour'], day_of_week=ap_days, timezone="Europe/Paris")
        shared.scheduler.add_job(func=trigger_bose_alarm, trigger=trigger, args=[a['ip'], a['preset']], id=f"alarm_{idx}")

@alarm_bp.route('/api/alarms', methods=['GET', 'POST', 'DELETE'])
def manage_alarms():
    if request.method == 'GET':
        try:
            with open(shared.JSON_FILE, 'r') as f: return jsonify(json.load(f))
        except: return jsonify([])
        
    if request.method == 'POST':
        try:
            with open(shared.JSON_FILE, 'r') as f: alarms = json.load(f)
        except: alarms = []
        alarms.append(request.json)
        with open(shared.JSON_FILE, 'w') as f: json.dump(alarms, f, indent=4)
        sync_alarms_to_scheduler(alarms)
        return jsonify({"status": "success"})
        
    if request.method == 'DELETE':
        idx = int(request.args.get('index', -1))
        try:
            with open(shared.JSON_FILE, 'r') as f: alarms = json.load(f)
            if 0 <= idx < len(alarms):
                alarms.pop(idx)
                with open(shared.JSON_FILE, 'w') as f: json.dump(alarms, f, indent=4)
                sync_alarms_to_scheduler(alarms)
                return jsonify({"status": "success"})
        except: pass
        return jsonify({"status": "error"}), 400