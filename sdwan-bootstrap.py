#!/usr/bin/env python3

# *** Attach a list of devices to a device template and download the bootstrap config
# Get a list of device serial numbers
# Check the devices are not attached to an SDWAN device template
# Attach the devices to the tenplate and report on the status - use variables defined from sdwan-import.py
# Generate and download bootsrap configs for each device

import logging
import urllib3
import requests
import json

from pwinput import pwinput
from pprint import pprint
import sys

# Disable invalid certificate warnings - vManage is using a self signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

username = input("Enter your vManage username: ")
password = pwinput("Enter your vManage password: ")

vmanage_host = "https://vmanage-171203704.sdwan.cisco.com/"

print(f"\nConnecting to vManage...\n")

# Login and retrieve API token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
vmanage_host='vmanage-171203704.sdwan.cisco.com'
vmanage_port=443
api = "/j_security_check"
base_url = "https://%s:%s"%(vmanage_host, vmanage_port)
url = base_url + api
payload = {'j_username' : username, 'j_password' : password}

response = requests.post(url=url, data=payload, verify=False)
try:
    cookies = response.headers["Set-Cookie"]
    jsessionid = cookies.split(";")
    print(f'API token: {jsessionid[0]}')
except:
    if logger is not None:
        logger.error("No valid JSESSION ID returned\n")
        sys.exit()

# Get cross-site request forgery prevention token (XRSF) token - required for POST requests

headers = {'Cookie': jsessionid[0]}
base_url = "https://%s:%s"%(vmanage_host, vmanage_port)
api = "/dataservice/client/token"
url = base_url + api      
try:
    response = requests.get(url=url, headers=headers, verify=False)
    if response.status_code == 200:
        xsrf = response.text
        print(f'XSRF token: {xsrf}')
        
except:
    if logger is not None:
        logger.error("No valid XSRF token returned\n")
        sys.exit()

# Prompt for list of serial numbers

serials = set()
serial = ''

while serial != '':
    serial = input('Enter a serial number or leave blank to continue: ')
    if serial != None:
        serials.add(serial)

# Get the device inventory

headers = {'Cookie': jsessionid[0]}
base_url = "https://%s:%s"%(vmanage_host, vmanage_port)
api = "/dataservice/system/device/vedges"
url = base_url + api
try:
    response = requests.get(url=url, headers=headers, verify=False)
    print(f'Responce code (200=OK): {response.status_code}')
    device_inventory = json.loads(response.content)
    #pprint(device_inventory)

except:
    if logger is not None:
        logger.error("Error occurred\n")
        # CLOSE SEESSION

# Check the serial numbers exist in the device inventory, also check the device is in cli mode
serials_valid = set()
for device in device_inventory['data']:
    uuid = str(device['uuid'])
    serial = uuid.split('-')[-1]
    model = uuid.split('-' + serial)[0]
    if serial in serials:
        if device['configOperationMode'] == 'cli':
            serials_valid.add(serial)
            print(f'Model: {model} Serial Number: {serial} found and operating in CLI mode')
        else:
            print(f'Model: {model} Serial Number: {serial} found - device has template {device["template"]} attached - skipping')

# Compare serials and serials_vlaid to determine serial numbers missing form the device inventory

missing = serials - serials_valid
if len(missing) == 0:
    print(f'\nAll serial numbers have been located in the device inventory./n')
else:
    print(f'The following serial numbers are not in the device inventory:\n\n')
    for item in missing:
        print(item)
    
# Close session

headers = {'Cookie': jsessionid[0]}
base_url = "https://%s:%s"%(vmanage_host, vmanage_port)
api = "/logout?nocache={random-number}"
url = base_url + api      
try:
    response = requests.get(url=url, headers=headers, verify=False)
    print(f'Responce code (200=OK): {response.status_code}')
except:
    if logger is not None:
        logger.error("There was a problem closing the session\n")
sys.exit()