import re
import subprocess
import json
import time
import requests
import typer
from typing_extensions import Annotated
from autifyapi import web

app = typer.Typer()
maxlife = 600
output = []

def runtp(url, config):

    # will match URL for Autify For Web
    # capture: (proeject id), (test plan id)
    app = r'^.*\/app.*projects\/(.*?)\/test_plans\/(.*?)$'

    # will match URL + with-build data for Autify For Mobile
    # capture: (project id), (test plan id), (build ID)
    mob = r'^.*mobile-app.*projects\/(.*?)\/test_plans\/(.*?)\s*with-build\s*(.*)$'

    if re.match(app, url):
        ser = re.search(app, url)
        proj = ser.group(1)
        plan = ser.group(2)
        return runwebtp(proj, plan, config)

    if re.match(mob, url):
        ser = re.search(mob, url)
        proj = ser.group(1)
        plan = ser.group(2)
        bild = ser.group(3)
        return runmobtp(proj, plan, bild, config)

    print(f"ERROR - could not parse URL {url}")
    return False

def runwebtp(proj, plan, config):
    # dry run will just output target info then return true
    if config["dryrun"]:
        appendOutput("dryrun", {}, testtype="web", project=proj, testplan=plan)
        print(f"would run: project = {proj} | test plan = {plan}")
        return True

    print(f"running: project = {proj} | test plan = {plan}")

    output = web.run_testplan(config["web_token"], plan)

    if not output.ok:
        print("ERROR running testplan: " + output.data())
        return False

    result_id = output.res["data"]["id"]
    timeout = maxlife

    # poll result until success or fail state
    while timeout > 0:

        output = web.get_result(config["web_token"], proj, result_id)

        if not output.ok:
            print("ERROR checking result")
            print(output.res)
            return False
        if output.status == "running":
            print(".")
        elif output.status == "waiting":
            print("z")
        elif output.status == "queuing":
            print("q")
        elif output.status == "passed":
            print("PASSED")
            appendOutput(output.status, output.res, testtype="web", project=proj, testplan=plan)
            return True
        elif output.status == "failed":
            appendOutput(output.status, output.res, testtype="web", project=proj, testplan=plan)
            print("FAILED")
            return False
        elif output.status == "canceled":
            appendOutput(output.status, output.res, testtype="web", project=proj, testplan=plan)
            print("CANCELED")
            return False
        elif output.status == "error":
            print("got error status")
            print(output.res)
            print("ABORTING")
            return False
        else:
            print("got unknown status: " + output.status)
            print("ABORTING")
            return False

        time.sleep(5)
        timeout -= 5

    print("TIMEOUT - FAILED")
    return False

def runmobtp(proj, plan, bild, config):

    # dry run will just output target info then return true
    if config["dryrun"]:
        appendOutput("dryrun", {}, testtype="mobile", project=proj, testplan=plan, build=bild)
        print(f"would run: project = {proj} | test plan = {plan} | build = {bild}")
        return True

    print(f"running: project = {proj} | test plan = {plan} | build = {bild}")

    # run the api test plan and get result ID
    # this uses the API
    # see: https://mobile-app.autify.com/api/docs/index.html
    endpoint = "https://mobile-app.autify.com/api/v1/test_plans/"+plan+"/test_plan_results"
    headers = {"Authorization": "Bearer " + config["mobile_token"]}
    payload = dict(build_id=bild)

    res = requests.post(endpoint, data=payload, headers=headers)
    out = res.json()

    print(out)

    result_id = out["id"]
    timeout = maxlife

    # poll result until success or fail state
    while timeout > 0:

        # check status of result
        endpoint = "https://mobile-app.autify.com/api/v1/projects/"+proj+"/results/"+result_id
        headers = {"Authorization": "Bearer " + config["mobile_token"]}

        res = requests.get(endpoint, headers=headers)
        out = res.json()

        status = out["status"]

        if status == "running":
            print(".")
        elif status == "waiting":
            print("z")
        elif status == "passed":
            appendOutput(status, out, testtype="mobile", project=proj, testplan=plan, build=bild)
            print("PASSED")
            return True
        elif status == "failed":
            appendOutput(status, out, testtype="mobile", project=proj, testplan=plan, build=bild)
            print("FAILED")
            return False
        elif status == "canceled":
            appendOutput(status, out, testtype="mobile", project=proj, testplan=plan, build=bild)
            print("CANCELED")
            return False
        else:
            print("got unknown status: " + status)
            print("ABORTING")
            return False

        time.sleep(5)
        timeout -= 5

    print("TIMEOUT - FAILED")
    return False


def readconfig(f):
    with open(f) as infile:
        config = json.load(infile)

    return config

def appendOutput(status:str, response, testtype=None, project=None, testplan=None, build=None):
    append = {
        "status": status, 
        "test_type" : testtype,
        "project": project,
        "test_plan": testplan,
        "build": build,
        "response": response
    }

    filtered = dict(filter(lambda item: item[1] is not None, append.items()))

    output.append(filtered)    

def saveOutput(script, status, path):
    outputfile = {
        "script": script,
        "status": status,
        "results": output,
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(outputfile, f, ensure_ascii=False,indent=4)

@app.command()
def init(
    path: Annotated[str, typer.Option(help="path to save new config file")] = "./config.json"
):
    webtok = typer.prompt("Autify For Web Token (blank to ignore)")
    mobtok = typer.prompt("Autify For Mobile Token (blank to ignore)")

    config = {
        "mobile_token": mobtok,
        "web_token": webtok,
        "max_life": 600
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False,indent=4)

    print("confirm config at " + path)

@app.command()
def run(
    targetfile: str, 
    dryrun: Annotated[bool, typer.Option(help="only pretend to run tests")] = False,
    configfile: Annotated[str, typer.Option(help="path to config file")] = "./config.json",
    outputfile: Annotated[str, typer.Option(help="path to output file")] = None,
    ):

    config = readconfig(configfile)
    config["dryrun"] = dryrun

    # get the contents of the test file as an array (1 line each)
    with open(targetfile, 'r') as infile:
        commands = infile.read().splitlines()

    status = "passed"
    message = "TEST SCRIPT PASSED"

    for c in commands:
        # if you see "wait" then wait for keyboard input before continuing
        if c == "wait":
            input("WAITING... do any manual tasks here, then press any key to continue")
            print("RESUMING")

        # otherwise assume it's a test plan to run
        else:
            ok = runtp(c, config)

            if not ok:
                status = "failed"
                message = "TEST SCRIPT FAILED"
                break
    
    print(message)
    
    if outputfile is not None:
        print("SAVING OUTPUT")
        saveOutput(targetfile, status, outputfile)

    print("EXITING")

if __name__ == "__main__":
    app()