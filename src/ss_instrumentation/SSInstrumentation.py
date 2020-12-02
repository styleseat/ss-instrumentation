from __future__ import absolute_import

import json
import time
from abc import ABCMeta, abstractmethod
from datetime import datetime
from collections import defaultdict

import boto3
from botocore.client import Config


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

    def __str__(self):
        return self.serialize()

    def __eq__(self, other):
        if not isinstance(other, MetricAndDims):
            return False

        return self.serialize() == other.serialize()

    def __hash__(self):
        return hash(self.serialize())


class MetricStorage(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def incr(self, metric):
        raise NotImplementedError()

    @abstractmethod
    def pop_values_for_period(self):
        raise NotImplementedError()


class InMemoryMetricStorage(MetricStorage):
    def __init__(self):
        self._start_time = datetime.utcnow()
        self._counts = defaultdict(int)

    def incr(self, metric):
        self._counts[metric] += 1

    def pop_values_for_period(self):
        duration = (datetime.utcnow() - self._start_time).total_seconds()
        values = {}

        for metric, count in self._counts.items():
            values[metric] = count / duration

        self._start_time = datetime.utcnow()
        self._counts = defaultdict(int)

        return values


class RedisMetricStorage(MetricStorage):
    def __init__(self, redis_client):
        self._client = redis_client

        if not self._client.exists('ssinstr:meter:periodstart'):
            self._client.set('ssinstr:meter:periodstart', time.time())

    def incr(self, metric):
        self._client.hincrby('ssinstr:meter:counts', metric.serialize(), 1)

    def pop_values_for_period(self):
        duration = time.time() - float(self._client.get('ssinstr:meter:periodstart'))
        raw_counts = self._client.hgetall('ssinstr:meter:counts')
        values = {}

        for metric_str, count in raw_counts.items():
            metric = MetricAndDims.deserialize(metric_str)
            values[metric] = float(count) / duration

        self._client.set('ssinstr:meter:periodstart', time.time())
        self._client.delete('ssinstr:meter:counts')

        return values


class SSInstrumentation(object):
    """Class for managing methods that send data to be stored in AWS"""

    def __init__(self, config, storage=None):
        self.namespace = config['AWS_METRIC_NAMESPACE']
        self.client = boto3.client('cloudwatch', config=Config(
            connect_timeout=config.get('BOTO_CONNECT_TIMEOUT', 1),
            read_timeout=config.get('BOTO_READ_TIMEOUT', 1),
            retries={'max_attempts': 0},
            region_name=config['AWS_LOGGING_REGION']
        ))

        if storage:
            self._storage = storage
        else:
            self._storage = InMemoryMetricStorage()

    def incr_meter(self, metric_name, **dims):
        # metric = MetricAndDims(metric_name, **dims)
        # self._storage.incr(metric)
        self.put_metric(metric_name, 1, **dims)

    def put_metric(self, metric_name, value, **kwargs):
        data = {
            'name': metric_name,
            'value': value,
        }

        if kwargs:
            data['dims'] = kwargs

        return self.put_metrics([data])

    def put_metrics(self, metrics):
        """
        Store multiple metrics in CloudWatch. May fail in various ways, returns
        True on success but in most contexts you won't want to retry or even
        bother to check the return value.
        """
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

        try:
            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=metrics_data
            )
            return True
        except Exception:
            return False

    def flush_meters(self):
        values = self._storage.pop_values_for_period()

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
