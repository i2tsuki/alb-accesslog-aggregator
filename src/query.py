from mackerel.clienthde import Client


class Builder:
    def __init__(self, mackerel_apikey, mackerel_service, mackerel_role):
        self.target_hosts = {}
        self.queries = []

        mkr = Client(mackerel_api_key=mackerel_apikey)
        self.target_hosts = mkr.get_hosts(service=mackerel_service, role=mackerel_role)
        self.alb_hosts = mkr.get_hosts(service=mackerel_service, role="alb")

    def build(self, prefix="alb", alb="", targets=None, between=""):
        self.queries = []

        if prefix != "" and prefix is not None:
            prefix = prefix + "."
        if alb == "":
            return "`alb` args is null string"
        alb_host_id = self._alb_to_host_id(name=alb)
        if alb_host_id == "":
            return "`alb_host_id` is not registerd in mackerel"
        if targets is None:
            return "`targets` args is None"

        # Build basic query
        self.queries = [
            {
                "name": "custom.{prefix}target_status_code.all".format(prefix=prefix),
                "unit": "integer",
                "host_id": alb_host_id,
                "query": [
                    {
                        "name": "custom.{prefix}target_status_code.all.2xx".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE s._10 LIKE '2%' AND {between}".format(
                            between=between
                        ),
                    },
                    {
                        "name": "custom.{prefix}target_status_code.all.3xx".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE s._10 LIKE '3%' AND {between}".format(
                            between=between
                        ),
                    },
                    {
                        "name": "custom.{prefix}target_status_code.all.4xx".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE s._10 LIKE '4%' AND {between}".format(
                            between=between
                        ),
                    },
                    {
                        "name": "custom.{prefix}target_status_code.all.5xx".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE s._10 LIKE '5%' AND {between}".format(
                            between=between
                        ),
                    },
                ],
            },
            {
                "name": "custom.{prefix}no_dispatch.all".format(prefix=prefix),
                "unit": "integer",
                "host_id": alb_host_id,
                "query": [
                    {
                        "name": "custom.{prefix}no_dispatch.all.count".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE (s._6 = -1 OR s._7 = -1 OR s._8 = -1) AND {between}".format(
                            between=between
                        ),
                    }
                ],
            },
            {
                "name": "custom.{prefix}no_target_response.all".format(prefix=prefix),
                "unit": "integer",
                "host_id": alb_host_id,
                "query": [
                    {
                        "name": "custom.{prefix}no_target_response.all.count".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE s._10 = '-' AND {between}".format(
                            between=between
                        ),
                    }
                ],
            },
        ]

        # Build query by target
        for target in targets:
            host_id = self._target_to_host_id(target=target)
            if host_id == "":
                return "`host_id` is not registerd in mackerel"

            # count status code
            query = {
                "name": "custom.{prefix}target_status_code".format(prefix=prefix),
                "unit": "integer",
                "host_id": host_id,
                "query": [
                    {
                        "name": "custom.{prefix}target_status_code.2xx".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE s._5 LIKE '{target}' AND s._10 LIKE '2%' AND {between}".format(
                            target=target, between=between
                        ),
                    },
                    {
                        "name": "custom.{prefix}target_status_code.3xx".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE s._5 LIKE '{target}' AND s._10 LIKE '3%' AND {between}".format(
                            target=target, between=between
                        ),
                    },
                    {
                        "name": "custom.{prefix}target_status_code.4xx".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE s._5 LIKE '{target}' AND s._10 LIKE '4%' AND {between}".format(
                            target=target, between=between
                        ),
                    },
                    {
                        "name": "custom.{prefix}target_status_code.5xx".format(
                            prefix=prefix
                        ),
                        "query": "SELECT COUNT(*) FROM S3Object s WHERE s._5 LIKE '{target}' AND s._10 LIKE '5%' AND {between}".format(
                            target=target, between=between
                        ),
                    },
                ],
            }
            self.queries.append(query)
            # average latency
            query = {
                "name": "custom.{prefix}latency.".format(prefix=prefix),
                "unit": "float",
                "host_id": host_id,
                "query": [
                    {
                        "name": "custom.{prefix}latency.average".format(prefix=prefix),
                        "query": "SELECT AVG(CAST(s._6 AS FLOAT) + CAST(s._7 AS FLOAT) + CAST(s._8 AS FLOAT)) FROM S3Object s WHERE s._5 LIKE '{target}' AND {between}".format(
                            target=target, between=between
                        ),
                    }
                ],
            }
            self.queries.append(query)
        return None

    def _alb_to_host_id(self, name):
        for host in self.alb_hosts:
            if host.name == name:
                return host.id
        return ""

    def _target_to_host_id(self, target):
        ipaddr = target.split(sep=":")[0]
        for host in self.target_hosts:
            if ipaddr == host.interfaces[0]["ipAddress"]:
                return host.id
        return ""
