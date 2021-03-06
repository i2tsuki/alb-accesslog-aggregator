#!/usr/bin/env python3
import datetime
from logging import getLogger, StreamHandler, INFO, ERROR

import boto3
from mackerel.clienthde import Client

from cli import Cli
import metric
import query

handler = StreamHandler()
handler.setLevel(ERROR)

logger = getLogger("alb-accesslog-aggregator")
logger.setLevel(ERROR)
logger.addHandler(handler)
logger.propagate = False

# Disable boto verbose log
getLogger("boto3").setLevel(ERROR)
getLogger("botocore").setLevel(ERROR)

IGNORE_DELAY_BEFORE = 420  # Ignore bucket objects before 7 Min.
INTERVAL_SECONDS = 60  # 1 Min. (mackerel.io can support metric point)


def execute_query_alb_log(s3_client=None, bucket=None, key=None, query=None):
    if bucket is None or key is None or query is None:
        return None

    records = []

    resp = s3_client.select_object_content(
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
                "QuoteCharacter": '"',
            },
        },
        OutputSerialization={
            "CSV": {
                "RecordDelimiter": "\n",
                "FieldDelimiter": "\t",
                "QuoteCharacter": '"',
            }
        },
    )
    for event in resp["Payload"]:
        if "Records" in event:
            records.append(event["Records"]["Payload"].decode("utf-8"))

    return records


def get_instance_private_ip(ec2_client=None, instance_id=""):
    resp = ec2_client.describe_instances(InstanceIds=[instance_id])
    return resp["Reservations"][-1]["Instances"][-1]["PrivateIpAddress"]


def main():
    # Parse environment variable
    cli = Cli()
    if cli.verbose:
        handler.setLevel(INFO)
        logger.setLevel(INFO)
        getLogger("boto3").setLevel(INFO)
        getLogger("botocore").setLevel(INFO)

    mkr = Client(mackerel_api_key=cli.mackerel_apikey)

    now = datetime.datetime.utcnow()
    # Cutting off secs. and microsecs.
    now = now - datetime.timedelta(seconds=now.second, microseconds=now.microsecond)
    if now.minute % 5 != 1:
        logger.error("Aggregator must be executed x1 or x6 minutes")
        exit(1)
    sts = boto3.client("sts")
    aws_account_id = sts.get_caller_identity()["Account"]

    region = cli.region
    load_balancer_name = cli.load_balancer_name
    prefix = cli.prefix
    duration = cli.duration

    s3 = boto3.client("s3", region)
    ec2 = boto3.client("ec2", region)
    elbv2 = boto3.client("elbv2", region)

    # Get load balancer arn
    load_balancer_arn = elbv2.describe_load_balancers(Names=[load_balancer_name])[
        "LoadBalancers"
    ][-1]["LoadBalancerArn"]

    # Get S3 Log bucket objects
    bucket = ""
    bucket_prefix = ""
    attributes = elbv2.describe_load_balancer_attributes(
        LoadBalancerArn=load_balancer_arn
    )["Attributes"]
    for attr in attributes:
        if attr["Key"] == "access_logs.s3.enabled":
            if not attr["Value"]:
                logger.error("ALB attribute `access_logs.s3.enabled` is not enabled\n")
                exit(1)
        if attr["Key"] == "access_logs.s3.bucket":
            bucket = attr["Value"]
        if attr["Key"] == "access_logs.s3.prefix":
            date = (now - datetime.timedelta(seconds=60)).strftime("%Y/%m/%d")
            bucket_prefix = "{prefix}/AWSLogs/{aws_account_id}/elasticloadbalancing/{region}/{date}/".format(
                prefix=attr["Value"],
                aws_account_id=aws_account_id,
                region=region,
                date=date,
            )

    contents = []
    objs = s3.list_objects_v2(Bucket=bucket, Prefix=bucket_prefix, MaxKeys=1000)
    for content in objs["Contents"]:
        contents.append(content)
    while True:
        if "NextContinuationToken" in objs:
            token = objs["NextContinuationToken"]
            objs = s3.list_objects_v2(
                Bucket=bucket,
                Prefix=bucket_prefix,
                ContinuationToken=token,
                MaxKeys=1000,
            )
            for content in objs["Contents"]:
                contents.append(content)
        else:
            break

    # Build targets list for constructing group by target query
    targets = []
    # ToDo(Very low priority): support marker args
    target_groups = elbv2.describe_target_groups(LoadBalancerArn=load_balancer_arn)[
        "TargetGroups"
    ]

    for target_group in target_groups:
        # For instance based target group
        if target_group["TargetType"] == "instance":
            health_descriptions = elbv2.describe_target_health(
                TargetGroupArn=target_group["TargetGroupArn"]
            )
            for health in health_descriptions["TargetHealthDescriptions"]:
                target = "{host}:{port}".format(
                    host=get_instance_private_ip(
                        ec2_client=ec2, instance_id=health["Target"]["Id"]
                    ),
                    port=str(health["Target"]["Port"]),
                )
                targets.append(target)
        # For ip based target group
        elif target_groups["TargetType"] == "ip":
            for target_group in target_groups:
                health_descriptions = elbv2.describe_target_health(
                    TargetGroupArn=target_group["TargetGroupArn"]
                )
                for health in health_descriptions["TargetHealthDescriptions"]:
                    target = "{host}:{port}".format(
                        host=health["Target"]["Id"], port=str(health["Target"]["Port"])
                    )
                    targets.append(target)

    metrics = metric.Metrics()

    builder = query.Builder(
        mackerel_apikey=cli.mackerel_apikey,
        mackerel_service=cli.mackerel_service,
        mackerel_role=cli.mackerel_role,
    )

    # Create mackerel graph definition
    builder.build(prefix=prefix, alb=load_balancer_name, targets=targets, between="")
    params = metric.create_graph_definition_param(queries=builder.queries)
    for param in params:
        mkr.create_graph_definition(
            name=param["name"],
            display_name=param["name"],
            unit=param["unit"],
            metrics=param["metrics"],
        )

    # Aggregate s3 access log
    for content in contents:
        # When `LastModified` is older than `RECORD_DELAY_SECONDS` seconds ago, loop continues
        if content["LastModified"].replace(tzinfo=None) < now - (
            datetime.timedelta(seconds=IGNORE_DELAY_BEFORE)
        ):
            continue

        for epoch in range(1, 6):
            to_timestamp = now - datetime.timedelta(seconds=duration * (epoch - 1) + 60)
            from_timestamp = now - datetime.timedelta(seconds=duration * epoch + 60)
            between = "s._2 BETWEEN '{from_timestamp}' AND '{to_timestamp}'".format(
                from_timestamp=from_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                to_timestamp=to_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            err = builder.build(
                prefix=prefix, alb=load_balancer_name, targets=targets, between=between
            )
            if err is not None:
                logger.error("Aggregator failed to build queries: " + err)

            for query_group in builder.queries:
                host_id = ""
                if "host_id" in query_group:
                    host_id = query_group["host_id"]
                for q in query_group["query"]:

                    records = execute_query_alb_log(
                        s3_client=s3,
                        bucket=bucket,
                        key=content["Key"],
                        query=q["query"],
                    )
                    for record in records:
                        v = record.strip()
                        if v != "":
                            metrics.add(
                                host_id=host_id,
                                name=q["name"],
                                timestamp=to_timestamp,
                                value=float(v),
                            )
                        else:
                            metrics.add(
                                host_id=host_id,
                                name=q["name"],
                                timestamp=to_timestamp,
                                value=float(0.0),
                            )
    data = []
    for m in metrics.metrics:
        v = {
            "hostId": m["host_id"],
            "name": m["name"],
            "time": m["timestamp"] - 1,
            "value": m["value"],
        }
        data.append(v)
        logger.info(
            "\t".join([str(m["timestamp"]), m["host_id"], m["name"], str(m["value"])])
        )
    mkr.post_metrics(metrics=data)


def lambda_handler(event, context):
    main()


if __name__ == "__main__":
    main()

# Memo
# load_balancer.latency.max
# Expression="SELECT MAX(CAST(s._6 AS FLOAT) + CAST(s._7 AS FLOAT) + CAST(s._8 AS FLOAT)) FROM S3Object s",
# load_balancer.received_bytes
# Expression="SELECT SUM(CAST(s._11 AS INT)) FROM S3Object s",
# load_balancer.sent_bytes
# Expression="SELECT SUM(CAST(s._12 AS INT)) FROM S3Object s",
# load_balancer.error_matched_rule
# Expression="SELECT COUNT(*) FROM S3Object s WHERE s._20 = -",
