from __future__ import absolute_import

from datetime import datetime

import boto3


def batch(iterable, n=1):
    count = len(iterable)
    for ndx in range(0, count, n):
        yield iterable[ndx:min(ndx + n, count)]


class MetricStorage(object):
    def extend(metrics):
        raise NotImplementedError()

    def pop_all():
        raise NotImplementedError()

    def count(metrics):
        raise NotImplementedError()


class InMemoryMetricStorage(MetricStorage):
    def __init__(self):
        self._store = []

    def extend(self, metrics):
        self._store.extend(metrics)

    def pop_all(self,):
        metrics = self._store
        self._store = []
        return metrics

    def count(self):
        return len(self._store)


FLUSH_POLICIES = {
    'ALWAYS',
    'NEVER',
}


class SSCloudwatchMetrics(object):
    """Class for managing methods that send data to be stored in AWS"""

    def __init__(self, config, storage=None, flush_policy='ALWAYS'):
        if flush_policy not in FLUSH_POLICIES:
            raise ValueError('Invalid flush_policy: %r' % flush_policy)

        self.namespace = config['AWS_METRIC_NAMESPACE']
        self.client = boto3.client('cloudwatch', region_name=config['AWS_LOGGING_REGION'])
        self.flush_policy = flush_policy

        if storage:
            self._storage = storage
        else:
            self._storage = InMemoryMetricStorage()

    def _should_flush(self):
        if self.flush_policy == 'ALWAYS':
            return True

        return False

    def store_metric(self, metric_name, value, **kwargs):
        data = {
            'name': metric_name,
            'value': value,
        }

        if kwargs:
            data['dims'] = kwargs

        return self.store_metrics([data])

    def store_metrics(self, metrics):
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

        self._storage.extend(metrics_data)

        if self._should_flush():
            self.flush()

    def flush(self):
        for metric_batch in batch(self._storage.pop_all(), 20):
            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_batch
            )
