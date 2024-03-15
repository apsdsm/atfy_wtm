# api docs
# https://autifyhq.github.io/autify-api/#/schedule/executeSchedule

import requests
from .response import Response

def run_testplan(token, testplan_id):
    # run a schedule (testplan) and get result ID
    endpoint = f"https://app.autify.com/api/v1/schedules/{testplan_id}"
    headers = {"Authorization": f"Bearer {token}"}
    result = requests.post(endpoint, headers=headers)
    ok = result.status_code is 200
    res = result.json()

    return Response(ok, res)

    
def get_result(token, project_id, result_id):
    # get execution result
    endpoint = f"https://app.autify.com/api/v1/projects/{project_id}/results/{result_id}"
    headers = {"Authorization": f"Bearer {token}"}
    result = requests.get(endpoint, headers=headers)
    ok = result.status_code is 200
    res = result.json()
    status = res["status"] if ok else "error"

    return Response(ok, res, status=status)