"""
This script takes a Jenkins workspace and automatically fetches the Sonarqube task ID from it.
Next, it queries the Sonarqube API to get the status of the task. When the task is done, it fetches the status
of the quality gate from Sonarqube and exits with a non-zero exit code if the quality gate failed.
"""
from __future__ import absolute_import, print_function
import json
import os
import time
import requests

from six.moves import xrange

SERVER_URL = os.environ.get('SONAR_SERVER_URL', "https://sonarcloud.io")
PROJECT_KEY = os.environ.get('PROJECT_KEY', "org.sonarqube:tribler")
TASK_PATH = os.path.join(os.environ.get('WORKSPACE', os.getcwd()), '.scannerwork', 'report-task.txt')

task_status_url = None
with open(TASK_PATH, 'r') as task_file:
    for line in task_file.readlines():
        parts = line.split("=")
        if not parts:
            continue
        if parts[0] == "ceTaskUrl":
            task_status_url = '='.join(parts[1:])
            break

if not task_status_url:
    print("Fetching task ID has failed!")
    exit(1)

print("Task status URL: %s" % task_status_url)

for _ in xrange(0, 30):
    print("Fetching task status...")
    json_response = requests.get(task_status_url)
    data = json.loads(json_response.text)
    if data['task']['status'] == "IN_PROGRESS":
        print("Task still being processed, sleeping...")
        time.sleep(2)
    else:
        print("Task done, status: %s" % data['task']['status'])
        break

time.sleep(10)

# We now fetch the status of the quality gate
gate_response_url = "%s/api/measures/component?metricKeys=alert_status&componentKey=%s" % (SERVER_URL, PROJECT_KEY)
json_response = requests.get(gate_response_url)
data = json.loads(json_response.text)
if 'component' not in data:
    print("No sonar component found")
    exit(1)

sonar_component = data['component']
if sonar_component['key'] != PROJECT_KEY:
    print("%s != %s" % (sonar_component['key'], PROJECT_KEY))
    exit(1)

for measure in sonar_component["measures"]:
    if measure["metric"] == "alert_status":
        if measure["value"] == "OK":
            print("SonarQube says OK")
            exit(0)
        else:
            print("Quality gate failed")
            exit(1)
