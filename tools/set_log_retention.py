#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
from logging import getLogger, StreamHandler, ERROR

import boto3


handler = StreamHandler()
handler.setLevel(ERROR)

logger = getLogger("alb-accesslog-aggregator")
logger.setLevel(ERROR)
logger.addHandler(handler)
logger.propagate = False

# Disable boto verbose log
getLogger("boto3").setLevel(ERROR)
getLogger("botocore").setLevel(ERROR)

__doc__ = "set_log_retention.py set retention policy in AWS CloudWatch Logs log group"

if __name__ == "__main__":
    description = __doc__
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--retention",
                        metavar="RETENTION",
                        action="store",
                        dest="retention", type=int,
                        default=1, help="CloudWatch log retention in days")
    args = parser.parse_args()

    client = boto3.client("lambda")
    logs = boto3.client('logs')
    retention = args.retention

    functions = []
    resp = client.list_functions(
        MaxItems=1000,
    )
    for function in resp["Functions"]:
        functions.append(function)
    while True:
        if "NextMarker" in resp:
            marker = resp["NextMarker"]
            resp = client.list_functions(
                Marker=marker,
                MaxItems=1000,
            )
            for function in resp["Functions"]:
                functions.append(function)
        else:
            break

    for i, function in enumerate(functions):
        resp = client.list_tags(Resource=function["FunctionArn"])
        for tag in resp["Tags"]:
            if tag == "Application":
                if resp["Tags"][tag] == "alb-accesslog-aggregator":
                    name = functions[i]["FunctionName"]
                    resp = logs.put_retention_policy(
                        logGroupName="/aws/lambda/{name}".format(name=name),
                        retentionInDays=retention,
                    )
                    if resp["ResponseMetadata"]["HTTPStatusCode"] != 200:
                        logger.Error("Logs put_retention_policy export API error")
                        sys.exit(1)
