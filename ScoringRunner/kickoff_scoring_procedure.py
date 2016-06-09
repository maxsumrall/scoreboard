# Listens to rabbitMQ for new submissions to score. Writes results out for the scoreboard to pickup.
import json
import os
import subprocess
import sys

import pika

path_to_grader = ""
path_to_results = ""
path_to_biblio_queries = ""
path_to_biblio_graph = ""


def log_result(request):
    filename = request["filename"].split(".")[0]
    log = open(path_to_results + filename + ".txt", "w")
    log.write(json.dumps(request))
    log.close()


def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)
    decoded_json = json.loads(body.decode())
    try:
        path_length = "3"
        budget = "10000"
        result = grade(decoded_json, path_length, budget)
        result = json.loads(result)
        decoded_json["result"] = result["path_results"]
        decoded_json["score"] = result["score"]
        log_result(decoded_json)
        print(" [x] Done : " + json.dumps(result))
    except Exception as err:
        decoded_json["result"] = str(err)
        log_result(decoded_json)
        print(" [x] ERROR ON : " + json.dumps(decoded_json))
    ch.basic_ack(delivery_tag=method.delivery_tag)


def grade(message, path_length, budget):
    global path_to_grader
    bundle_path = message["uri"]
    bundle_name = message["filename"]
    file_type = bundle_name.split(".")[1]
    unpacked_location = bundle_path.split(".")[0]
    subprocess.check_output(["mkdir", "-p", unpacked_location])
    if file_type == "zip":
        print(subprocess.check_output(["unzip", "-o", bundle_path, "-d", unpacked_location]))
    elif file_type == "tar":
        subprocess.check_output(["tar", "-xvf", bundle_path, "-C", unpacked_location])
    else:
        return "Invalid file type"

    files = os.listdir(unpacked_location)
    if "setup.sh" not in files:
        return "Missing setup.sh"
    if "run.sh" not in files:
        return "Missing run.sh"

    unpacked_bundle = bundle_path.split(".")[0]

    biblio_queries = path_to_biblio_queries
    biblio_graph_file = path_to_biblio_graph
    process = subprocess.Popen(
        ["python3", path_to_grader, biblio_queries, unpacked_bundle, biblio_graph_file, path_length, budget],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    process.wait(timeout=120)  # wait 60 seconds for everything
    grader_results = ""
    line = process.stdout.readline().decode()
    while line != "":
        grader_results += line
        line = process.stdout.readline().decode()
    grader_results = grader_results.replace("\'", "\"").replace("\n", "")
    print(grader_results)
    grader_results = grader_results
    return grader_results


def main():
    global path_to_grader, path_to_results, path_to_biblio_graph, path_to_biblio_queries
    config_file_path = sys.argv[1]

    config_file = open(config_file_path, "r")
    server_uri = config_file.readline().strip()
    queue_user = config_file.readline().strip()
    queue_pw = config_file.readline().strip()
    path_to_grader = config_file.readline().strip()
    path_to_uploads = config_file.readline().strip()
    path_to_results = config_file.readline().strip()
    path_to_biblio_graph = config_file.readline().strip()
    path_to_biblio_queries = config_file.readline().strip()

    credentials = pika.PlainCredentials(queue_user, queue_pw)
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        server_uri, 5672, '/', credentials))
    channel = connection.channel()
    channel.queue_declare(queue='jobs')

    channel.basic_consume(callback, queue='jobs')
    channel.start_consuming()


main()
