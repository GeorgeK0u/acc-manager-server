import subprocess
from subprocess import PIPE, DEVNULL
import json
import time

user = None
url = None

def Init():
    global user, url
    # read api credentials
    with open('./apiCredentials.json', 'r') as file:
        data = json.load(file)
        user = data['user']
        url = data['url']

def UpdateIP():
        ip_update_status = subprocess.run(args=f'curl -u {user} {url}', shell=True, stdout=PIPE, stderr=DEVNULL).stdout.decode().strip()
        if not(ip_update_status.__contains__('good')) and not(ip_update_status.__contains__('nochg')):
            print(f'Status error: {ip_update_status}')
            return -1
        return 1

if __name__ == '__main__':
    Init()
    print('Started')
    sec_to_min = 60
    timeout_secs = 5 * sec_to_min
    while True:
        resp = UpdateIP()
        if resp == -1:
            break
        time.sleep(timeout_secs) 
