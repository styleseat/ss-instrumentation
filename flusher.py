import redis
from os import environ

from src.ss_instrumentation import (
    SSInstrumentation,
    RedisMetricStorage,
)


def flush(event, context):
    storage = RedisMetricStorage(
        redis.Redis(
            host=environ['REDIS_HOST'],
            port=int(environ.get('REDIS_PORT', '6379')),
            db=int(environ.get('REDIS_DB', '0'))
        )
    )

    config = {
        'AWS_METRIC_NAMESPACE': environ['AWS_METRIC_NAMESPACE'],
        'AWS_LOGGING_REGION': environ['AWS_LOGGING_REGION'],
    }

    instr = SSInstrumentation(config, storage)

    print('About to flush meters')
    instr.flush_meters()
    print('Flushed, sending response')

    return {
        "statusCode": 200,
        "body": '{"STATUS": "OK"}',
    }


if __name__ == '__main__':
    flush(None, None)
