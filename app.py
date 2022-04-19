# -*- coding: utf-8 -*-
import os
import json
import requests

from flask import Flask, render_template, redirect, request, Response

app = Flask(__name__)


def validate(params):
    if params["event"]["type"] != "message":
        print("Event type is ", params["event"]["type"], "but not `message`")

    app_id = params["api_app_id"] == os.environ["APP_ID"]
    token = params["token"] == os.environ["VERIFICATION_TOKEN"]
    team = params["team_id"] == os.environ["TEAM_ID"]
    channel = params["event"]["channel"] == os.environ["USLACKBOT_CHANNEL"]
    bot_token = params["bot_token"] =  os.environ["BOT_TOKEN"]
    email_channel_map = params["email_channel_map"] = os.environ["EMAIL_CHANNEL_MAP"]

    user = params["event"].get("user", "") == "USLACKBOT"
    subtype = params["event"]["subtype"] == "file_share"

    if app_id and token and team and channel and user and subtype:
        return True
    else:
        if not app_id:
            print("env: APP_ID is not right!")
        if not token:
            print("env: TOKEN is not right!")
        if not team:
            print("env: TEAM_ID is not right!")
        if not channel:
            print("env: USLACKBOT channel is not right!")
        if not user:
            print("User is not right! user: ", params["event"].get("user", ""))
        if not subtype:
            print("Email subtype not right subtype: ",
                  params["event"]["subtype"])
        if not bot_token:
            print("env: BOT_TOKEN is not right!")
        if not email_channel_map:
            print("env: EMAIL_CHANNEL_MAP is not right")
        return False


@app.route("/", methods=['GET', 'POST'])
def main():
    if request.method == "GET":
        return redirect("https://github.com/kossiitkgp/email-to-slack")
    elif request.method == "POST":

        print("New Email recieved\n Parameters")
        params = request.get_json(force=True)
        print(json.dumps(params))
        print("\n\n===HEADERS====\n")
        print(request.headers)
        """
        Enable this to verify the URL while installing the app
        """
        if 'challenge' in params:
            data = {
                'challenge': params.get('challenge'),
            }
            resp = Response(
                response=json.dumps(data),
                status=200,
                mimetype='application/json'
            )
            resp.headers['Content-type'] = 'application/json'

            return resp
        if validate(params):
            email = params["event"]["files"][0]

            if f"CHECKED_{email['id']}" in os.environ or "X-Slack-Retry-Num" in request.headers:
                # This email has already been processed
                return Response(response="Duplicate", status=409)

            headers = {
                "content-type": "application/json;charset=UTF-8",
                "Authorization": "Bearer " + params["bot_token"],
            }

            # this is loaded from JSON string in the environment variable
            channels_dict = json.loads(params["email_channel_map"])

            # to avoid double sharing, remove duplicates in the to_emails (don't trust the users)
            clean_emails = []
            for to_email_dict in email["to"]:
                lowercase_email = to_email_dict["address"].lower()
                if lowercase_email not in clean_emails:
                    clean_emails.append(lowercase_email)
            # loop through each email and forward the emails to the right channel
            # if doing this with BOT user OAUTH token, then you need to grant the Bot Token scope remote_files:share
            for to_email in clean_emails:
                if to_email in channels_dict:
                    channel = channels_dict[to_email]
                    data = {
                        "channel": channel,
                        "text": "<" + email["permalink"] + "|email>",
                    }

                    # this could be security risk so remove before going prod
                    print(json.dumps(email))
                    print(json.dumps(headers))
                    print(json.dumps(data))

                    r = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=data)
                    print("\n\n\nchat.postMessage Exit with status code {}\n\n".format(r.status_code))

            # Slack API sends two payloads for single event. This is a bug
            # involving Heroku and Slack API.
            os.environ[f"CHECKED_{email['id']}"] = ''

            return Response(
                response="ok",
                status=200
            )
        else:
            return Response(
                response="Bad request",
                status=401
            )

app.secret_key = os.environ.setdefault("APP_SECRET_KEY", "notsosecret")
app.config['SESSION_TYPE'] = 'filesystem'

app.debug = False

if __name__ == '__main__':
    app.run(debug=True)