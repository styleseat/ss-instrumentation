from __future__ import absolute_import

from datetime import datetime, timedelta

from freezegun import freeze_time
import mock

from ss_instrumentation import (
    SSInstrumentation,
)


def standard_mock(f):
    def wrapper(*args, **kwargs):
        mock_client = mock.MagicMock()
        new_args = args[:] + (mock_client,)

        with mock.patch('boto3.client', return_value=mock_client):
            return f(*new_args, **kwargs)

    return wrapper


@freeze_time('1984-08-06')
class TestSSInstrumenation(object):
    def create_instr(self):
        config = {
            'AWS_METRIC_NAMESPACE': 'FizzBuzzAsAService',
            'AWS_LOGGING_REGION': 'us-west-2',
        }

        return SSInstrumentation(config)

    def _metric_ident(self, metric):
        dims = sorted([(dim['Name'], dim['Value']) for dim in metric.get('Dimensions', [])])
        return (metric['MetricName'], tuple(dims))

    def assert_metric_present(self, actual_metrics, expected_metric):
        actual_metrics = {self._metric_ident(metric): metric for metric in actual_metrics}
        metric_ident = self._metric_ident(expected_metric)

        if metric_ident not in actual_metrics:
            assert 1 == 0, 'Metric with matching name/dims not found'

        actual_metric = actual_metrics[metric_ident]

        assert actual_metric.get('Value') == expected_metric.get('Value')
        assert actual_metric.get('Unit') == expected_metric.get('Unit')
        assert actual_metric.get('Timestamp') == expected_metric.get('Timestamp')

    @mock.patch('boto3.client')
    def test_client_config(self, mock_client_constructor):
        self.create_instr()
        mock_client_constructor.assert_called_with('cloudwatch', region_name='us-west-2')

    @standard_mock
    def test_put_metric(self, mock_client):
        instr = self.create_instr()
        instr.put_metric('fizz', 6)

        mock_client.put_metric_data.assert_called_with(
            Namespace='FizzBuzzAsAService',
            MetricData=[
                {
                    'MetricName': 'fizz',
                    'Value': 6,
                    'Unit': 'None',
                    'Timestamp': datetime.utcnow(),
                }
            ]
        )

    @standard_mock
    def test_put_metric_with_dims(self, mock_client):
        instr = self.create_instr()
        instr.put_metric('fizz', 6, is_prime='no', why='divisible by two')

        self.assert_metric_present(
            mock_client.put_metric_data.call_args.kwargs['MetricData'],
            {
                'MetricName': 'fizz',
                'Value': 6,
                'Unit': 'None',
                'Timestamp': datetime.utcnow(),
                'Dimensions': [
                    {
                        'Name': 'is_prime',
                        'Value': 'no',
                    },
                    {
                        'Name': 'why',
                        'Value': 'divisible by two',
                    },
                ]
            }
        )

    @standard_mock
    def test_simple_meter(self, mock_client):
        with freeze_time(datetime.utcnow()) as frozen_datetime:
            instr = self.create_instr()

            instr.incr_meter('bps')
            instr.incr_meter('bps')

            frozen_datetime.tick(timedelta(seconds=1))

            instr.incr_meter('bps')
            instr.incr_meter('bps')

            frozen_datetime.tick(timedelta(seconds=1))

            instr.flush_meters()

            mock_client.put_metric_data.assert_called_with(
                Namespace='FizzBuzzAsAService',
                MetricData=[
                    {
                        'MetricName': 'bps',
                        'Value': 2,
                        'Unit': 'Count/Second',
                        'Timestamp': datetime.utcnow(),
                        'Dimensions': []
                    }
                ]
            )

    @standard_mock
    def test_meter_w_dims(self, mock_client):
        with freeze_time(datetime.utcnow()) as frozen_datetime:
            instr = self.create_instr()

            instr.incr_meter('bps', is_prime='yes')
            instr.incr_meter('bps', is_prime='no')

            frozen_datetime.tick(timedelta(seconds=1))

            instr.incr_meter('bps', is_prime='no')

            frozen_datetime.tick(timedelta(seconds=1))

            instr.flush_meters()

            self.assert_metric_present(
                mock_client.put_metric_data.call_args.kwargs['MetricData'],
                {
                    'MetricName': 'bps',
                    'Value': 0.5,
                    'Unit': 'Count/Second',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {
                            'Name': 'is_prime',
                            'Value': 'yes',
                        },
                    ],
                }
            )

            self.assert_metric_present(
                mock_client.put_metric_data.call_args.kwargs['MetricData'],
                {
                    'MetricName': 'bps',
                    'Value': 1,
                    'Unit': 'Count/Second',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {
                            'Name': 'is_prime',
                            'Value': 'no',
                        },
                    ],
                },
            )
