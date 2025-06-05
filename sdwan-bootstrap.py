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

def CloseSession():
    # Close session

    print('\nClosing the vManage session')
    headers = {'Content-Type': "application/json",'Cookie': token, 'X-XSRF-TOKEN': xsrf}
    #headers = {'Cookie': jsessionid[0]}
    base_url = "https://%s:%s"%(vmanage_host, vmanage_port)
    api = "/logout"
    url = base_url + api      
    try:
        response = requests.get(url=url, headers=headers, verify=False)
        if response.status_code == 200:
            print('vManage session closed successfully')
        else:
            print('Error closing vManage session')
            print(f'Response code: {response.status_code}\n')
    except:
        if logger is not None:
            logger.error("There was a problem closing the session\n")
    sys.exit()

# Disable invalid certificate warnings - vManage is using a self signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

username = input("Enter your vManage username: ")
password = pwinput("Enter your vManage password: ")

vmanage_host = "https://vmanage-2044406.sdwan.cisco.com/"

print(f"\nConnecting to vManage...\n")

# Login and retrieve API token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
#vmanage_host='vmanage-171203704.sdwan.cisco.com'
vmanage_host='vmanage-2044406.sdwan.cisco.com'
vmanage_port=443
api = "/j_security_check"
base_url = "https://%s:%s"%(vmanage_host, vmanage_port)
url = base_url + api
payload = {'j_username' : username, 'j_password' : password}

response = requests.post(url=url, data=payload, verify=False)
try:
    cookies = response.headers["Set-Cookie"]
    jsessionid = cookies.split(";")
    token='JSESSIONID='+response.cookies.get_dict()['JSESSIONID']
    #print(f'API token: {token}')
except:
    if logger is not None:
        logger.error("No valid JSESSION ID returned\n")
        sys.exit()

# Get cross-site request forgery prevention token (XRSF) token - required for POST requests

#headers = {'Cookie': token}
headers = {'Content-Type': "application/json",'Cookie': token}
base_url = "https://%s:%s"%(vmanage_host, vmanage_port)
api = "/dataservice/client/token"
url = base_url + api      
try:
    response = requests.get(url=url, headers=headers, verify=False)
    if response.status_code == 200:
        xsrf = response.text
        #print(f'XSRF token: {xsrf}')
        
except:
    if logger is not None:
        logger.error("No valid XSRF token returned\n")
        sys.exit()

# Prompt for list of serial numbers

serials = set()
serial = 'anytext'

while len(serial) >0:
    serial = input('Enter a serial number or leave blank to continue (NickO 1121X = FGL2428L1MH): ')
    if len(serial) >0:
        serials.add(serial)

# Get the device inventory

headers = {'Content-Type': "application/json",'Cookie': token, 'X-XSRF-TOKEN': xsrf}
base_url = "https://%s:%s"%(vmanage_host, vmanage_port)
api = "/dataservice/system/device/vedges"
url = base_url + api
try:
    response = requests.get(url=url, headers=headers, verify=False)
    print(f'Response code (200=OK): {response.status_code}\n')
    device_inventory = json.loads(response.content)
    #pprint(device_inventory)

except:
    if logger is not None:
        logger.error("Error occurred\n")
        CloseSession()

# Check the serial numbers exist in the device inventory, also check the device is in cli mode

serials_valid = set()
serials_attached = set()
serials_model = set()

for device in device_inventory['data']:
    uuid = str(device['uuid'])
    serial = uuid.split('-')[-1]
    model = uuid.split('-' + serial)[0]
    if serial in serials:
        if device['configOperationMode'] == 'cli':
            serials_valid.add(serial)
            serials_model.add(model)
            serials_devicemodel = model
            print(f'Serial Number: {serial:<20}Model: {model:<20} Mode: CLI')
        else:
            serials_attached.add(serial)
            print(f'Serial Number: {serial:<20}Model: {model:<20} Template: {device["template"]} attached - skipping')

# Compare serials and serials_valid to determine serial numbers missing form the device inventory

missing = serials - serials_valid
missing = missing - serials_attached
if len(missing) > 0:
    print(f'\nThe following serial numbers are not in the device inventory:\n')
    for item in missing:
        print(item)

if len(serials_valid) == 0:
    print(f'\nThere are no valid serial numbers provided for bootstrapping')
    CloseSession()

# check serials are all the same device model

if len(serials_model) >1:
    print("\nAll device serial numbers must be the same model.  The following models were found:\n")
    for model in serials_model:
        print(model)
    CloseSession()

# Print list of device templates containing 'onboard' in the name (nicko for now)

headers = {'Content-Type': "application/json",'Cookie': token, 'X-XSRF-TOKEN': xsrf}
base_url = "https://%s:%s"%(vmanage_host, vmanage_port)
api = "/dataservice/template/device"
url = base_url + api
try:
    response = requests.get(url=url, headers=headers, verify=False)
    print(f'Response code (200=OK): {response.status_code}\n')
    device_templates = json.loads(response.content)
    #pprint(device_templates)

except:
    if logger is not None:
        logger.error("Error occurred\n")
        CloseSession()

for template in device_templates['data']:
    if 'NickO' in template['templateName']:
        print(f"Name: {template['templateName']:<40} Model: {template['deviceType']:<30} ID: {template['templateId']}")

print()

# Select template

attachtemplate = ''
waitforvalidtemplate = True

while waitforvalidtemplate:
    while attachtemplate == '':
        attachtemplate = input('Enter Template name to attach: ')
    
    for template in device_templates['data']:
        if attachtemplate == template['templateName']:
            print(f"\nName: {template['templateName']} ID: {template['templateId']} located")
            template_model=template['deviceType'].split('vedge-')
            
            if len(template_model) == 1:
                print("\nTemplate not valid.  Please try again.\n")
                attachtemplate = ''
                break
            
            if template_model[1] not in serials_devicemodel:
                print("\nTemplate does not match the serial number device model. Please try again.\n")
                print(f"serials_devicemodel:{serials_devicemodel} template_model[1]:{template_model[1]}")
                attachtemplate = ''
                break

            attachtemplateid = template['templateId']
            waitforvalidtemplate = False
    
    if waitforvalidtemplate is True and attachtemplate != '':
        print("\nTemplate not found.  Please try again.\n")
        attachtemplate = ''
        
# Attach devices

print('\n')
for serial in serials_valid:
    print(f'Attaching {serial} ...')
    
# All done
CloseSession()