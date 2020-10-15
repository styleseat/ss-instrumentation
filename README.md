# ss-instrumentation

ss-instrumentation is a light wrapper around the boto3 cloudwatch client intended for reporting custom metrics to cloudwatch. The one additional concept that ss-instrumentation adds to cloudwatch's model is a "meter" which can be incremented as some event occurs, sample the rate of the event, and report it periodically to cloudwatch. This is more performant/cost effective than reporting each occurrence of an event as up to 20 different event types and any frequency of an event within a period can be bundled into a single call to cloudwatch.

## Configuration

An example configuration for the `SSInstrumentation` class is:

```
config = {
    'AWS_METRIC_NAMESPACE': 'FizzBuzzAsAService',
    'AWS_LOGGING_REGION': 'us-west-2',
}

instr = SSInstrumentation(config)
```

This will use `InMemoryMetricStorage` by default. To use `RedisMetricStorage` instead you might do:

```
storage = RedisMetricStorage(redis.Redis(host='localhost', port=6379, db=0))
config = {
    'AWS_METRIC_NAMESPACE': 'FizzBuzzAsAService',
    'AWS_LOGGING_REGION': 'us-west-2',
}

instr = SSInstrumentation(config, storage)
```

See the following section for more on metric storage.

## Metric Storage

Because meters report a rate over some time period, they need a storage mechanism for tracking event frequency and period boundaries. You can use either of `InMemoryMetricStorage` or `RedisMetricStorage` for this. `InMemoryMetricStorage` is suitable for environments where every process that interacts with a meter can share one `SSInstrumentation` instance. `RedisMetricsStorage` is suitable when there are potentially multiple isolated processes or machines that report to a meter that have access to a common redis instance.

## Reporting to Meters

Given an instance of `SSInstrumentation`, reporting an event is as simple as:

```
instance.incr_meter('event_name')
```

You can report to a meter with [dimensions](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_concepts.html#Dimension) like so:

```
instance.incr_meter('event_name', dim1='foo', dim2='bar')
```

It's important to note that dimension names and values are part of a meter/metric's identity. For example, the following two events:

```
instance.incr_meter('foo', is_bar='yes')
instance.incr_meter('foo', is_bar='no)
```

constitute two separate meters, rates are counted independently and are reported to couldwatch separately, and they will appear in the cloudwatch UI as separate metrics. As a result you'll want to keep the set of unique dimension/value pairs for a given metric name to a relatively small, closed set. For example, in a meter tracking the rate of login attempts to a service, success or failure of a login attempt may be a reasonable dimension to include (resulting in success and failure rates being reported independently, although calculating a sum over multiple metrics is possible in the cloudwatch UI), but the IP address of a client attempting login would lead to an unmanageable proliferation of metrics.

## Flushing Meters

Meters record the rate of an event over a period of time. To report the rate of a meter to cloudwatch, meters must be "flushed" (frequencies over the period calculated and sent to cloudwatch). This is done by calling the `flush_meters()` method of `SSInstrumenation`. While rates over irregular periods will be calculated accurately, this method should be called regularly so that spikes or dips in rates are not smoothed out over a long reporting period. It is the responsibility of consumers of this library to arrange for `flush_meters()` to be called at a regular interval, once to twice a minute is recommended for standard resolution metrics.
