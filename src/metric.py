# -*- coding: utf-8 -*-
import datetime
import calendar


class Metrics():
    def __init__(self):
        self.metrics = []

    def add(self, host_id="", name="", timestamp=None, value=0.0):
        fixed_timestamp = self.fix_timestamp(timestamp)

        for metric in self.metrics:
            if metric["host_id"] == host_id and metric["name"] == name and metric["fixed_timestamp"] == fixed_timestamp:
                metric["value"] = metric["value"] + value
                return

        metric = {
            "host_id": host_id,
            "timestamp": calendar.timegm(timestamp.timetuple()),
            # "timestamp": timestamp,
            "fixed_timestamp": fixed_timestamp,
            "name": name,
            "value": value,
        }
        self.metrics.append(metric)

    def fix_timestamp(self, timestamp):
        return timestamp - datetime.timedelta(seconds=timestamp.second)


def create_graph_definition_param(queries={}):
    graph_definition = []
    for group in queries:
        metrics = []
        for query in group["query"]:
            metrics.append(
                {"name": query["name"], "isStacked": False}
            )
        params = {
            "name": group["name"],
            "unit": group["unit"],
            "metrics": metrics,
        }
        graph_definition.append(params)
    return graph_definition
