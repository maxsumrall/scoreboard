import json
import os
import uuid

import pika
from flask import Flask, render_template, request, redirect, send_from_directory
from werkzeug import secure_filename

app = Flask(__name__)

config_file = open("config.txt", "r")
server_uri = config_file.readline().strip()
queue_user = config_file.readline().strip()
queue_pw = config_file.readline().strip()

app.config['UPLOAD_FOLDER'] = '/Users/Max/Desktop/test/'
app.config['RABBIT_MQ'] = server_uri
# These are the extension that we are accepting to be uploaded
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

credentials = pika.PlainCredentials(queue_user, queue_pw)
connection = pika.BlockingConnection(pika.ConnectionParameters(
    app.config['RABBIT_MQ'], 5672, '/', credentials))
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
        return render_template("index.html")

    option = request.form['lang']
    team = request.form['team']
    print(team + " " + option)

    # Get the name of the uploaded file
    file = request.files['file']
    # Check if the file is one of the allowed types/extensions
    if file and allowed_file(file.filename):
        # Make the filename safe, remove unsupported chars
        filename = secure_filename(str(uuid.uuid4()) + "_" + file.filename)
        # Move the file form the temporal folder to
        # the upload folder we setup
        print("Upload: " + file.filename)
        upload_location = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_location)
        # Redirect the user to the uploaded_file route, which
        # will basicaly show on the browser the uploaded file

        bundle = {"filename": filename, "team": team, "lang": option}

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
