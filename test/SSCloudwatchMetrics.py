from __future__ import absolute_import

from datetime import datetime

from freezegun import freeze_time
import mock

from ss_cloudwatch_metrics import (
    SSCloudwatchMetrics,
)


def standard_mock(f):
    def wrapper(*args, **kwargs):
        mock_client = mock.MagicMock()
        new_args = args[:] + (mock_client,)

        with mock.patch('boto3.client', return_value=mock_client):
            return f(*new_args, **kwargs)

    return wrapper


@freeze_time('1984-08-06')
class TestSSCloudwatchMetrics(object):
    def create_metrics(self):
        config = {
            'AWS_METRIC_NAMESPACE': 'FizzBuzzAsAService',
            'AWS_LOGGING_REGION': 'us-west-2',
        }

        return SSCloudwatchMetrics(config)

    @mock.patch('boto3.client')
    def test_client_config(self, mock_client_constructor):
        self.create_metrics()
        mock_client_constructor.assert_called_with('cloudwatch', region_name='us-west-2')

    @standard_mock
    def test_store_metric(self, mock_client):
        metrics = self.create_metrics()
        metrics.store_metric('fizz', 6)

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
    def test_store_metric_with_dims(self, mock_client):
        metrics = self.create_metrics()
        metrics.store_metric('fizz', 6, is_prime=False, why='divisible by two')

        mock_client.put_metric_data.assert_called_with(
            Namespace='FizzBuzzAsAService',
            MetricData=[
                {
                    'MetricName': 'fizz',
                    'Value': 6,
                    'Unit': 'None',
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {
                            'Name': 'is_prime',
                            'Value': False,
                        },
                        {
                            'Name': 'why',
                            'Value': 'divisible by two',
                        },
                    ]
                }
            ]
        )
