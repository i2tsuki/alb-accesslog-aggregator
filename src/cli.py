import os


class Cli:
    def __init__(self):
        self.mackerel_apikey = os.environ["MACKEREL_APIKEY"]

        # S3 bucket region
        self.region = os.environ["REGION"]
        # AWS application loadbalancer name
        self.load_balancer_name = os.environ["LOAD_BALANCER_NAME"]
        # Mackerel metric prefix
        if "PREFIX" in os.environ:
            self.prefix = os.environ["PREFIX"]
        else:
            self.prefix = "alb-accesslog-aggregator"
        # Duration is between to aggregate ALB logs
        if "DURATION" in os.environ:
            self.duration = int(os.environ["DURATION"])
        else:
            self.duration = 60

        # Service that have ALB host and its targets host
        self.mackerel_service = os.environ["MACKEREL_SERVICE"]
        # Role is target hosts registered the ALB
        self.mackerel_role = os.environ["MACKEREL_ROLE"].replace(" ", "").split(sep=",")

        # Logging verbosity
        self.verbose = False
        if "VERBOSE" in os.environ:
            if os.environ["VERBOSE"] != "0":
                self.verbose = True
