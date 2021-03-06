#
# Copyright 2017-2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# or in the "license" file accompanying this file. This file is distributed 
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either 
# express or implied. See the License for the specific language governing 
# permissions and limitations under the License.
#

#

import json
import boto3
import sys
import csv
import time
from datetime import datetime

STS_SESSION = ''

def get_sts_session(event, region_name=False):
    sts = boto3.client("sts")
    RoleArn = event["executionRoleArn"]
    if not region_name:
        region_name = event['configRuleArn'].split(":")[3]
    response = sts.assume_role(
        RoleArn=RoleArn,
        RoleSessionName='ComplianceAudit',
        DurationSeconds=900)
    sts_session = boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'], 
        aws_secret_access_key=response['Credentials']['SecretAccessKey'], 
        aws_session_token=response['Credentials']['SessionToken'], 
        region_name=region_name, 
        botocore_session=None, 
        profile_name=None)
    return(sts_session)

def root_no_last_access():    
    iam = STS_SESSION.client("iam")
    credreport = get_cred_report()
    if "Fail" in credreport:  # Report failure in control
        sys.exit(credreport)

    # Check if root is used in the last 24h
    now = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time()))
    frm = "%Y-%m-%dT%H:%M:%S+00:00"
    status = 'COMPLIANT'
    
    try:
        pwdDelta = (datetime.strptime(now, frm) - datetime.strptime(credreport[0]['password_last_used'], frm))
        if (pwdDelta.days == 0) & (pwdDelta.seconds > 0):  # Used within last 24h
            status = 'NON_COMPLIANT'
    except:
        if credreport[0]['password_last_used'] == "N/A" or "no_information":
            pass
        else:
            print("Something went wrong")

    try:
        key1Delta = (datetime.strptime(now, frm) - datetime.strptime(credreport[0]['access_key_1_last_used_date'], frm))
        if (key1Delta.days == 0) & (key1Delta.seconds > 0):  # Used within last 24h
            status = 'NON_COMPLIANT'
    except:
        if credreport[0]['access_key_1_last_used_date'] == "N/A" or "no_information":
            pass
        else:
            print("Something went wrong")
    try:
        key2Delta = datetime.strptime(now, frm) - datetime.strptime(credreport[0]['access_key_2_last_used_date'], frm)
        if (key2Delta.days == 0) & (key2Delta.seconds > 0):  # Used within last 24h
            status = 'NON_COMPLIANT'
    except:
        if credreport[0]['access_key_2_last_used_date'] == "N/A" or "no_information":
            pass
        else:
            print("Something went wrong")

        
    config = STS_SESSION.client("config")
    config.put_evaluations(
            Evaluations=[
                {
                    "ComplianceResourceType": "AWS::::Account",
                    "ComplianceResourceId": "Root No Access",
                    "ComplianceType": status,
                    "OrderingTimestamp": str(datetime.now())
                },
            ],
            ResultToken=result_token
        )

def get_cred_report():
    status=''
    x = 0
    iam = STS_SESSION.client("iam")
    while iam.generate_credential_report()['State'] != "COMPLETE":
        time.sleep(2)
        x += 1
        # If no credentail report is delivered within this time fail the check.
        if x > 10:
            status = "Fail: rootUse - no CredentialReport available."
            break
    if "Fail" in status:
        return status
    credentialReport = str(iam.get_credential_report()['Content'],'utf-8')
    report = []
    reader = csv.DictReader(credentialReport.splitlines())
    for row in reader:
        report.append(row)

    # Verify if root key's never been used, if so add N/A
    try:
        if report[0]['access_key_1_last_used_date']:
            pass
    except:
        report[0]['access_key_1_last_used_date'] = "N/A"
    try:
        if report[0]['access_key_2_last_used_date']:
            pass
    except:
        report[0]['access_key_2_last_used_date'] = "N/A"
    return report

# This is the handler that's invoked by Lambda
def lambda_handler(event, context):

    global STS_SESSION
    global result_token
    if "resultToken" in event:
        result_token = event["resultToken"]

    STS_SESSION = get_sts_session(event)

    root_no_last_access()    
