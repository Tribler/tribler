"""
This script takes a Jenkins workspace and automatically fetches the Sonar Cloud task ID from it.
Next, it queries the SonarCloud API to get the status of the task. When the task is done, it fetches the status
of the quality gate from the server and exits with a non-zero exit code if the quality gate has failed.
"""
from __future__ import absolute_import, print_function

import json
import os
import time
from traceback import print_exc

import requests

from six.moves import xrange

# These env varialble should be set by Jenkins.
SERVER_URL = os.environ.get('SONAR_SERVER_URL', "https://sonarcloud.io")
PROJECT_KEY = os.environ.get('PROJECT_KEY', "org.sonarqube:tribler")
PR_COMMIT = os.environ.get('ghprbActualCommit', u'')
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

# Analysis URL for the project. Check https://sonarcloud.io/web_api/api/project_pull_requests for more info
pr_analysis_url = "%s/api/project_pull_requests/list?project=%s" % (SERVER_URL, PROJECT_KEY)
print("Analysis URL:", pr_analysis_url)
print("PR Commit:", PR_COMMIT)

# Analysis might take a few more seconds to complete and the results to be available so wait sometime
time.sleep(10)

# Fetch analysis response and find the status for the PR commit
try:
    json_response = requests.get(pr_analysis_url)
    data = json.loads(json_response.text)

    for pull_request in data[u'pullRequests']:
        print("Matching analysis:", pull_request[u'key'], PR_COMMIT, pull_request[u'key'] == PR_COMMIT)
        # If there is analysis result for the PR commit with status OK, then exit with success status (0)
        if pull_request[u'key'] == PR_COMMIT:
            print("Quality Gate:", pull_request[u'status'])
            if pull_request[u'status'][u'qualityGateStatus'] == u'OK':
                print("Status: OK")
                break
            else:
                print("Status: FAILED")
                exit(1)

except Exception:  # pylint: disable=broad-except
    print_exc()
    exit(1)
