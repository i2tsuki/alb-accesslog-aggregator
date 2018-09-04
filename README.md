# Alb Accesslog Aggregator
Alb Accesslog Aggregator aggregates access logs that ALB outputs to the S3 bucket. 
Calculate metrics from the aggregated log and post to monitoring Platform.
Currently, only the supported monitoring platform is [Mackerel](https://mackerel.io).
We plan to support other platforms in the future (`Ganglia` for now).

If there are other SaaS you want to post, please push your pull request.

## Installation
Alb Accesslog Aggregator is built on the assumption that it runs on Lambda Function on AWS.  There is toolset for deploying with CloudFormation.  See the following:

- Customize CloudFormation stack parameters

```sh
${EDITOR} ./cloudformation/parameters/params.json
```

- Create CloudFormation stack

```sh
make create
```

- Update CloudFormation stack by changeset

```sh
make create-changeset
```

- Create package and deploy to AWS Lambda

```sh
make deploy
```

## Requirements

- awscli (For CloudFormation deployment)
- python3 (For packaging lambda deployment)

## Troubleshooting
If you can not view the metric on the monitoring platform you posted, the function would be not working properly. By activating the next item with `./cloudformation/parameters/params.json` you can set the application logger level to `INFO`.

```yaml
...
  {
    "ParameterKey": "Verbose",
    "ParameterValue": "1",
    "UsePreviousValue": false
  }
...
```

The any debug log output to CloudWatch Logs and you will be able to figure out the cause of the problem.
