#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import datetime

import boto3

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
    parser.add_argument("--bucket", type=str,
                        metavar="BUCKET",
                        action="store", dest="bucket",
                        help="S3 bucket target name")
    parser.add_argument("--prefix", type=str,
                        metavar="PREFIX",
                        action="store", dest="prefix",
                        help="ALB access log location prefix (S3 bucket key prefix)")
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


def main():
    # parse args
    args = parse_args()

    now = datetime.datetime.now()

    region = args.region
    bucket = args.bucket
    prefix = "{prefix}/AWSLogs/{aws_account}/elasticloadbalancing/{region}/{date}/".format(
        prefix=args.prefix,
        aws_account="000000000000",
        region=region,
        date=now.strftime("%Y/%m/%d")
    )
    duration = args.duration
    verbose = args.verbose

    print(region, bucket, prefix, verbose)

    s3 = boto3.client("s3", region)

    # ToDo: support marker args
    objs = s3.list_objects(
        Bucket=bucket,
        Prefix=prefix
    )
    for obj in objs["Contents"]:
        print(obj)

    exit(0)

if __name__ == "__main__":
    main()
