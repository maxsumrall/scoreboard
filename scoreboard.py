import datetime
import json
import os
import sys
import uuid

import pika
from flask import Flask, render_template, request, redirect, send_from_directory
from werkzeug import secure_filename

app = Flask(__name__)

config_file_path = sys.argv[1]

config_file = open(config_file_path, "r")
server_uri = config_file.readline().strip()
queue_user = config_file.readline().strip()
queue_pw = config_file.readline().strip()
path_to_grader = config_file.readline().strip()
path_to_upload = config_file.readline().strip()
path_to_results = config_file.readline().strip()

app.config['UPLOAD_FOLDER'] = path_to_upload
app.config['RABBIT_MQ'] = server_uri
# These are the extension that we are accepting to be uploaded
app.config['ALLOWED_EXTENSIONS'] = {'zip', 'tar'}

credentials = pika.PlainCredentials(queue_user, queue_pw)
connection = pika.BlockingConnection(pika.ConnectionParameters(
    app.config['RABBIT_MQ'], 5672, '/', credentials, heartbeat_interval=0))
channel = connection.channel()
channel.queue_declare(queue='jobs')


# For a given file, return whether it's an allowed type or not
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS']


@app.route("/", methods=['GET', 'POST'])
def index():
    global channel
    if request.method == 'GET':
        results = []
        files = os.listdir(path_to_results)
        for file in files:
            data = json.load(open(path_to_results + file, "r"))
            results.append(data)
        results = sorted(results, key=lambda k: k["time"], reverse=True)
        return render_template("index.html", results=results)

    team = request.form['team']
    print(team)

    # Get the name of the uploaded file
    file = request.files['file']
    # Check if the file is one of the allowed types/extensions
    if file and allowed_file(file.filename):
        # Make the filename safe, remove unsupported chars
        filename = secure_filename(str(uuid.uuid4()) + "_" + str(file.filename).lower())
        # Move the file form the temporal folder to
        # the upload folder we setup
        print("Upload: " + file.filename)
        upload_location = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_location)
        # Redirect the user to the uploaded_file route, which
        # will basicaly show on the browser the uploaded file

        bundle = {"filename": filename, "team": team, 'uri': upload_location}
        bundle["time"] = str(datetime.datetime.now())

        channel.basic_publish(exchange='',
                              routing_key='jobs',
                              body=json.dumps(bundle))

        return redirect("/")


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)


if __name__ == '__main__':
    app.run(debug=True)
