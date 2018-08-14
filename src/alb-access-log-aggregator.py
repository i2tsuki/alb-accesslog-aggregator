#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import datetime
import sys

import boto3

RECORD_DELAY_SECONDS = 600 # 10 Min.
INTERVAL_SECONDS = 60 # 1 Min. (mackerel.io can support metric point)


def _temp_fileopen(fn):
    tempfp = open(file=fn, mode='r', encoding='utf-8')
    return tempfp


def parse_args():
    description = ""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--region", type=str,
                        metavar="REGION",
                        action="store", dest="region",
                        help="S3 bucket region")
    parser.add_argument("--load-balancer-name", type=str,
                        metavar="LOAD BALANCER NAME",
                        action="store", dest="load_balancer_name",
                        help="load balancer name")
    parser.add_argument("--prefix", type=str,
                        metavar="METRIC PREFIX",
                        action="store", dest="prefix",
                        help="mackerel metric prefix")
    parser.add_argument("--duration", type=int,
                        metavar="DURATION",
                        action="store", dest="duration",
                        default=60,
                        help="aggregation duration (seconds)")
    parser.add_argument("--tempfile",
                        metavar="TEMPORARY FILE",
                        type=_temp_fileopen, nargs=1,
                        help="temporary data store file")
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        dest='verbose')
    args = parser.parse_args()
    return args


def filter_obj_last_modified(obj=None, cut_timestamp=None):
    if obj["LastModified"].replace(tzinfo=None) < cut_timestamp:
        return True


def query_builder(prefix="alb", targets=None, between=""):
    if prefix != "" and prefix is not None:
        prefix = prefix + "."

    if targets is None:
        # ToDo raise error exception
        return None

    queries = [
        {
            "name": "{prefix}target_status_code.all.2xx".format(prefix=prefix),
            "query": "SELECT COUNT(*) FROM S3Object s WHERE s._10 LIKE '2%' AND {between}".format(between=between),
        },
        # "SELECT COUNT(*) FROM S3Object s WHERE (s._6 = -1 OR s._7 = -1 OR s._8 = -1) AND {between}".format(between=between),
    ]

    for target in targets:
        query = {
            "name": "{prefix}target_status_code.{target}.2xx".format(prefix=prefix, target=target),
            "query": "SELECT COUNT(*) FROM S3Object s WHERE s._5 LIKE '{target}' AND s._10 LIKE '2%' AND {between}".format(target=target, between=between),
        }
        queries.append(query)

    return queries


def execute_query_alb_log(client=None, bucket=None, key=None, query=None):
    if bucket is None or key is None or query is None:
        print("all args none")
        return None

    records = []

    resp = client.select_object_content(
        Bucket=bucket,
        Key=key,
        ExpressionType="SQL",
        Expression=query,
        InputSerialization={
            "CompressionType": "GZip",
            "CSV": {
                "FileHeaderInfo": "NONE",
                "RecordDelimiter": "\n",
                "FieldDelimiter": " ",
                "QuoteCharacter": "\"",
            },
        },
        OutputSerialization={
            "CSV": {
                "RecordDelimiter": "\n",
                "FieldDelimiter": "\t",
                "QuoteCharacter": "\"",
            },
        },
    )
    for event in resp["Payload"]:
        if "Records" in event:
            records.append(event["Records"]["Payload"].decode("utf-8"))

    return records


def main():
    # parse args
    args = parse_args()

    now = datetime.datetime.utcnow()
    sts = boto3.client("sts")
    aws_account_id = sts.get_caller_identity()["Account"]

    region = args.region
    load_balancer_name = args.load_balancer_name
    prefix = args.prefix
    duration = args.duration
    # verbose = args.verbose

    s3 = boto3.client("s3", region)
    ec2 = boto3.client("ec2", region)
    elbv2 = boto3.client("elbv2", region)

    # Get load balancer arn
    load_balancer_arn = elbv2.describe_load_balancers(
        Names=[load_balancer_name],
    )["LoadBalancers"][-1]["LoadBalancerArn"]

    # Get S3 Log bucket objects
    bucket = ""
    bucket_prefix = ""
    attributes = elbv2.describe_load_balancer_attributes(LoadBalancerArn=load_balancer_arn)["Attributes"]
    for attr in attributes:
        if attr["Key"] == "access_logs.s3.enabled":
            if not attr["Value"]:
                sys.stderr.write("ALB attribute `access_logs.s3.enabled` is not enabled\n")
                exit(1)
        if attr["Key"] == "access_logs.s3.bucket":
            bucket = attr["Value"]
        if attr["Key"] == "access_logs.s3.prefix":
            bucket_prefix = "{prefix}/AWSLogs/{aws_account_id}/elasticloadbalancing/{region}/{date}/".format(
                prefix=attr["Value"],
                aws_account_id=aws_account_id,
                region=region,
                date=now.strftime("%Y/%m/%d")
            )
    # ToDo: support marker args
    objs = s3.list_objects(
        Bucket=bucket,
        Prefix=bucket_prefix,
    )

    # Build targets list for constructing group by target query
    targets = []
    # ToDo: support marker args
    target_groups = elbv2.describe_target_groups(LoadBalancerArn=load_balancer_arn)["TargetGroups"]

    def get_instance_private_ip(client=None, instance_id=""):
        resp = client.describe_instances(InstanceIds=[instance_id])
        return resp["Reservations"][-1]["Instances"][-1]["PrivateIpAddress"]

    for target_group in target_groups:
        # for instance based target group
        if target_group["TargetType"] == "instance":
            health_descriptions = elbv2.describe_target_health(TargetGroupArn=target_group["TargetGroupArn"])
            for health in health_descriptions["TargetHealthDescriptions"]:
                target = "{host}:{port}".format(
                    host=get_instance_private_ip(
                        client=ec2,
                        instance_id=health["Target"]["Id"],
                    ),
                    port=str(health["Target"]["Port"]),
                )
                targets.append(target)
        # for ip based target group
        elif target_groups["TargetType"] == "ip":
            for target_group in target_groups:
                health_descriptions = elbv2.describe_target_health(TargetGroupArn=target_group["TargetGroupArn"])
                for health in health_descriptions["TargetHealthDescriptions"]:
                    target = "{host}:{port}".format(
                        host=health["Target"]["Id"],
                        port=str(health["Target"]["Port"])
                    )
                    targets.append(target)

    for obj in objs["Contents"]:
        if filter_obj_last_modified(obj=obj,
                                    cut_timestamp=now - datetime.timedelta(seconds=RECORD_DELAY_SECONDS)):
            continue

        for epoch in range(1, 6):
            from_timestamp = obj["LastModified"] - datetime.timedelta(seconds=duration*epoch)
            to_timestamp = obj["LastModified"] - datetime.timedelta(seconds=duration*(epoch-1))
            between = "s._2 BETWEEN '{from_timestamp}' AND '{to_timestamp}'".format(
                from_timestamp=from_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                to_timestamp=to_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            queries = query_builder(
                prefix=prefix,
                targets=targets,
                between=between,
            )

            for q in queries:
                records = execute_query_alb_log(
                    client=s3,
                    bucket=bucket,
                    key=obj["Key"],
                    query=q["query"],
                )
                for record in records:
                    v = record.strip()
                    print("\t".join([
                        to_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        q["name"],
                        v])
                    )


# format:
# type timestamp elb client:port target:port request_processing_time target_processing_time response_processing_time elb_status_code target_status_code received_bytes sent_bytes request user_agent ssl_cipher ssl_protocol target_group_arn trace_id domain_name chosen_cert_arn matched_rule_priority request_creation_time actions_executed


if __name__ == "__main__":
    main()

# Memo
# load_balancer.no_dispatch
# Expression="SELECT COUNT(*) FROM S3Object s WHERE s._6 = -1 OR s._7 = -1 OR s._8 = -1"
# load_balancer.latency.average
# Expression="SELECT AVG(CAST(s._6 AS FLOAT) + CAST(s._7 AS FLOAT) + CAST(s._8 AS FLOAT)) FROM S3Object s",
# load_balancer.latency.max
# Expression="SELECT MAX(CAST(s._6 AS FLOAT) + CAST(s._7 AS FLOAT) + CAST(s._8 AS FLOAT)) FROM S3Object s",
# load_balancer.status.2xx
# Expression="SELECT COUNT(*) FROM S3Object s WHERE s._9 LIKE '2%'",
# load_balancer.status.3xx
# Expression="SELECT COUNT(*) FROM S3Object s WHERE s._9 LIKE '3%'",
# load_balancer.status.4xx
# Expression="SELECT COUNT(*) FROM S3Object s WHERE s._9 LIKE '4%'",
# load_balancer.status.404
# Expression="SELECT COUNT(*) FROM S3Object s WHERE s._9 LIKE '404'",
# load_balancer.no_target_response
# Expression="SELECT COUNT(*) FROM S3Object s WHERE s._10 = -"
# load_balancer.received_bytes
# Expression="SELECT SUM(CAST(s._11 AS INT)) FROM S3Object s",
# load_balancer.sent_bytes
# Expression="SELECT SUM(CAST(s._12 AS INT)) FROM S3Object s",
# load_balancer.error_matched_rule
# Expression="SELECT COUNT(*) FROM S3Object s WHERE s._20 = -",
