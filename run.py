import re
import subprocess
import json
import time
import requests
import typer
from typing_extensions import Annotated

app = typer.Typer()
mobtok = "MOBILE-API-TOKEN"
webtok = "WEB-API-TOKEN"
maxlife = 600

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
        print(f"would run: project = {proj} | test plan = {plan}")
        return True

    print(f"running: project = {proj} | test plan = {plan}")

    # run the web plan and get result ID
    # this uses the command line tool
    # see: https://github.com/autifyhq/autify-cli
    run_res = subprocess.run(["autify", "web", "api", "execute-schedule", "--schedule-id="+plan], stdout=subprocess.PIPE)
    run_out = json.loads(run_res.stdout.decode())

    result_id = run_out["data"]["id"]
    timeout = maxlife

    # poll result until success or fail state
    while timeout > 0:

        # check status of result
        # e.g., runs command: autify web api describe-result --project-id=4865 --result-id=3057313
        chk_res = subprocess.run(["autify", "web", "api", "describe-result", "--project-id="+proj, "--result-id="+result_id], stdout=subprocess.PIPE)
        chk_res = json.loads(chk_res.stdout.decode())

        status = chk_res["status"]

        if status == "running":
            print(".")
        elif status == "waiting":
            print("z")
        elif status == "queuing":
            print("q")
        elif status == "passed":
            print("PASSED")
            return True
        elif status == "failed":
            print("FAILED")
            return False
        elif status == "canceled":
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

def runmobtp(proj, plan, bild, config):

    # dry run will just output target info then return true
    if config["dryrun"]:
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
            print("PASSED")
            return True
        elif status == "failed":
            print("FAILED")
            return False
        elif status == "canceled":
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
    configfile: Annotated[str, typer.Option(help="path to config file")] = "./config.json"
    ):

    config = readconfig(configfile)
    config["dryrun"] = dryrun

    # get the contents of the test file as an array (1 line each)
    with open(targetfile, 'r') as infile:
        commands = infile.read().splitlines()

    for c in commands:
        # if you see "wait" then wait for keyboard input before continuing
        if c == "wait":
            input("WAITING... do any manual tasks here, then press any key to continue")
            print("RESUMING")

        # otherwise assume it's a test plan to run
        else:
            ok = runtp(c, config)

            if not ok:
                print("TEST SCRIPT FAILED - EXITING")
                exit()

    print("TEST SCRIPT PASSED - EXITING")


if __name__ == "__main__":
    app()