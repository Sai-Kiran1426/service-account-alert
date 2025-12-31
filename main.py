from typing import List

from google.cloud import iam_admin_v1

from google.cloud.iam_admin_v1 import types

import csv

from googleapiclient.discovery import build

from oauth2client.client import GoogleCredentials

import datetime

import base64

import functions_framework

import json

import smtplib

from email.mime.text import MIMEText

from email.mime.multipart import MIMEMultipart

import os



# Triggered from a message on a Cloud Pub/Sub topic.

@functions_framework.cloud_event

def send_notification(cloud_event):

    # Print out the data from Pub/Sub, to prove that it worked

    print(base64.b64decode(cloud_event.data["message"]["data"]))

    print('START')



    credentials = GoogleCredentials.get_application_default()

    credentials = credentials.create_scoped(['https://www.googleapis.com/auth/cloud-platform'])

    service = build('cloudresourcemanager', 'v1', credentials=credentials)

    projects = service.projects().list().execute()

    iam_admin_client = iam_admin_v1.IAMClient()

    request = types.ListServiceAccountsRequest()

    results = []

    i = 0

    for project in projects['projects']:

        i += 1

        project_id = project['projectId']

        #project_id = "gcp-5ann122-prd-dv360-na"

        request.name = f"projects/{project_id}"

        try:

            accounts = iam_admin_client.list_service_accounts(request=request)

            for account in accounts:

                keys = keyinfo(account.name)

                if keys: 

                    for key in keys:

                        results.append(key)



        except Exception as e:

            print(f"{request.name=}, {e=}")

        

        if i > 1000:

            break

    if results:

        sorted_list = sorted(results, key=lambda x: int(x[-1]))

        send_mail(sorted_list)

    print("done")



def send_mail(keys):

    print("start mail process")

    username = os.environ.get('username')

    password = os.environ.get('password')

    sender = os.environ.get('sender')

    SMTP = os.environ.get('SMTP')

    msg = MIMEMultipart('mixed')



    recipients_str = os.environ.get('recipients')

    recipients = recipients_str.split(',')



    content = ""

    for key in keys:

        content += "Account: " + key[0] + "\nKey: " + key[1] + "\nExpires at: " + key[3] + "\nDays left: " + key[4] + "\n\n"



    msg['Subject'] = "GCP Service Account Key Alert"

    msg['From'] = sender

    msg["To"] = recipients_str

    stringline = ""

    stringline += content + "\n\n"



    print(f"{stringline=}")



    text_message = MIMEText(stringline, 'plain')

    html_message = MIMEText(stringline, 'html')

    msg.attach(text_message)



    with smtplib.SMTP(SMTP, 2525) as mailServer:

        mailServer.ehlo()

        mailServer.starttls()

        mailServer.ehlo()

        mailServer.login(username, password)

        # Loop through each recipient and send the email individually

        for recipient in recipients:

            mailServer.sendmail(sender, recipient, msg.as_string())



def keyinfo(account_name):

    keys = []

    iam_admin_client = iam_admin_v1.IAMClient()

    request = types.ListServiceAccountKeysRequest()

    request.name = account_name

    response = iam_admin_client.list_service_account_keys(request=request)



    for key in response.keys:

        valid_after_time = convert_nanoseconds_to_datetime(key.valid_after_time)

        valid_before_time = convert_nanoseconds_to_datetime(key.valid_before_time)



        key_type_name = key.key_type.name

        key_name = key.name.split("/")[-1]

        if key_type_name == "USER_MANAGED" and valid_before_time < datetime.datetime(2100,11,20, 0,0,0, tzinfo=datetime.timezone.utc):

            print(f"{account_name=}, {key_name=}")

            valid_after_time_str = valid_after_time.strftime("%Y-%m-%d %H:%M:%S%z")

            valid_before_time_str = valid_before_time.strftime("%Y-%m-%d %H:%M:%S%z")

            print(f"{valid_after_time_str=}, {valid_before_time_str=}")

            today = datetime.datetime(datetime.date.today().year, datetime.date.today().month, datetime.date.today().day, 0,0,0, tzinfo=datetime.timezone.utc)

            gap = valid_before_time - today

            if gap.days > 0:

                keys.append([account_name, key_name, valid_after_time_str, valid_before_time_str, str(gap.days)])

    return keys



def convert_nanoseconds_to_datetime(dt_with_nanoseconds) -> datetime:

    dt = datetime.datetime(

        dt_with_nanoseconds.year,

        dt_with_nanoseconds.month,

        dt_with_nanoseconds.day,

        dt_with_nanoseconds.hour,

        dt_with_nanoseconds.minute,

        dt_with_nanoseconds.second,

        microsecond=dt_with_nanoseconds.nanosecond // 1000,  # Convert nanoseconds to microseconds

        tzinfo=dt_with_nanoseconds.tzinfo

    )

    return dt
