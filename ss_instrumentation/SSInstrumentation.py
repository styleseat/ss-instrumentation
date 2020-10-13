from __future__ import absolute_import

import json
from datetime import datetime
from collections import defaultdict

import boto3


def batch(iterable, n=1):
    count = len(iterable)
    for ndx in range(0, count, n):
        yield iterable[ndx:min(ndx + n, count)]


class MetricAndDims(object):
    """
    Hashable and serializable storage for a metric name and associated
    dimension name/value pairs.
    """
    def __init__(self, name, **kwargs):
        self.name = name
        self.dims = kwargs

    def serialize(self):
        return json.dumps([
            self.name,
            sorted([(k, v) for k, v in self.dims.items()])
        ])

    @classmethod
    def deserialize(cls, s):
        name, dims = json.loads(s)
        return cls(name, **dict(dims))

    def __eq__(self, other):
        if not isinstance(other, MetricAndDims):
            return False

        return self.serialize() == other.serialize()

    def __hash__(self):
        return hash(self.serialize())


class MetricStorage(object):
    def incr(metric):
        raise NotImplementedError()

    def get_values_for_period():
        raise NotImplementedError()


class InMemoryMetricStorage(MetricStorage):
    def __init__(self):
        self._start_time = datetime.utcnow()
        self._counts = defaultdict(int)

    def incr(self, metric):
        self._counts[metric] += 1

    def get_values_for_period(self):
        duration = (datetime.utcnow() - self._start_time).total_seconds()
        values = {}

        for metric, count in self._counts.items():
            values[metric] = count / duration

        self._start_time = datetime.utcnow()
        self._counts = defaultdict(int)

        return values


class SSInstrumentation(object):
    """Class for managing methods that send data to be stored in AWS"""

    def __init__(self, config, storage=None):
        self.namespace = config['AWS_METRIC_NAMESPACE']
        self.client = boto3.client('cloudwatch', region_name=config['AWS_LOGGING_REGION'])

        if storage:
            self._storage = storage
        else:
            self._storage = InMemoryMetricStorage()

    def incr_meter(self, metric_name, **dims):
        metric = MetricAndDims(metric_name, **dims)
        self._storage.incr(metric)

    def put_metric(self, metric_name, value, **kwargs):
        data = {
            'name': metric_name,
            'value': value,
        }

        if kwargs:
            data['dims'] = kwargs

        return self.put_metrics([data])

    def put_metrics(self, metrics):
        """Store multiple metrics in CloudWatch"""
        metrics_data = []
        for metric in metrics:
            metric_data = {
                'MetricName': metric['name'],
                'Value': metric.get('value', 1),
                'Unit': metric.get('unit', 'None'),
                'Timestamp': datetime.utcnow()
            }

            if 'dims' in metric:
                metric_data['Dimensions'] = [
                    {'Name': name, 'Value': value} for name, value in metric['dims'].items()
                ]

            metrics_data.append(metric_data)

        self.client.put_metric_data(
            Namespace=self.namespace,
            MetricData=metrics_data
        )

    def flush_meters(self):
        values = self._storage.get_values_for_period()

        if not values:
            return

        for metric_batch in batch(list(values.items()), 20):
            metrics_to_put = []

            for metric, rate in metric_batch:
                metrics_to_put.append({
                    'name': metric.name,
                    'dims': metric.dims,
                    'value': rate,
                    'unit': 'Count/Second',
                })

            self.put_metrics(metrics_to_put)
