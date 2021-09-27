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
instance.incr_meter('foo', is_bar='no')
```

constitute two separate meters, rates are counted independently and are reported to couldwatch separately, and they will appear in the cloudwatch UI as separate metrics. As a result you'll want to keep the set of unique dimension/value pairs for a given metric name to a relatively small, closed set. For example, in a meter tracking the rate of login attempts to a service, success or failure of a login attempt may be a reasonable dimension to include (resulting in success and failure rates being reported independently, although calculating a sum over multiple metrics is possible in the cloudwatch UI), but the IP address of a client attempting login would lead to an unmanageable proliferation of metrics.

## Best Practices when Adding a Meter

These are some recommendations for setting up meters to instrument a codebase. They won't always be applicable, the thing to keep in mind is that a meter should give insight into what's happening in the application, the data we get back from meters should be alarm-able, either when at exceptionally low or high volumes. Measuring something where any value indicates normal operation doesn't tell us anything about what's happening.


### Where/When to Instrument

The object of this project is to monitor system health/detect exceptional behavior rather than provide business insight. If you can't identify when a certain volume of an event represents a situation that needs to be acted on by engineering, consider different tracking options.

When metering an activity, try to keep the reporting as close to the thing being metered as possible. When you are metering an event, make sure that the meter is incremented every time that event happens (check for alternative code paths that could make the same event happen without the meter being incremented) and that erroring out of a code path leading to the event does not cause that event to be reported (or report the event as having failed in that case).

### Naming

Purely for organizational purposes, metric names should be organized hierarchically with `.` separating parts of the hierarchy.

The first component of a metric name should report where the event is happening. For example, if a metric is being reported from an API endpoint, it should start with `web`, if it's happening in a task it should start with `task`. For metrics in utility functions/model methods that could be called either in the request/response cycle or from a task, use the generic `backend` and consider adding a dimension if where the metric reporting is being called from seems significant (e.g. auto vs. instant payout).

The last component of a metric name should indicate what is happening, e.g. `login_attempted` when a user attempts to log in.

Intermediary components may be included to conceptually group together related events, e.g. `web.appointment.created` and `web.appointment.rescheduled`. Intermediary components are not required if there aren't conceptually related events.

All parts of a metric name should be in snake case (lowercase, underscores to separate words). The last component of a metric should be phrased in the last tense, e.g. prefer `checkout_completed` to `checkout_complete`.

### Dimensions

Each unique set of dimensions/values create a separately tracked metric. Information like pro or client IDs, payment information, or information that goes into business logic like appointment counts, which we usually include in tracking, should not be included as dimensions as this would result in e.g. a metric per pro/client.

If the event tracked by a metric only has one logical result, no dimensions need to be specified. In cases where the same logical action can produce one of a few possible results, each result should increment a meter with the same name, and a `result` dimension should be included to indicate the outcome. For example, the `web.login_attempted` meter's `result` dimension will be one of `ip-rate-limited`, `global-rate-limited`, `mfa-block`, `bad-credentials`, or `success`.

### I've instrumented a piece of code, now what?

Either add an alarm, or add the metric to a dashboard, or both. You can add an alarm [here](https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#alarmsV2:create). If you know what reasonable numbers are for the meter (looking at tracking can help here) then set a static threshold, if you have no idea then you can use the anomaly detection condition and specify a number of standard deviations that represent normal operation. It's OK to guess at what a reasonable threshold is, if you're adding a new metric erring on the side of caution and alarming more actively is fine as this can be adjusted later. When adding an alarm include a description, what situation would cause it, and remediation steps if known. Add a link in the description if it doesn't fit in 1024 characters.

When adding an alarm drop a line in the #eng-on-call-rotation channel to help the on-call engineer knows that the alarm is new and may need to be tuned.

## Flushing Meters

Meters record the rate of an event over a period of time. To report the rate of a meter to cloudwatch, meters must be "flushed" (frequencies over the period calculated and sent to cloudwatch). This is done by calling the `flush_meters()` method of `SSInstrumenation`. While rates over irregular periods will be calculated accurately, this method should be called regularly so that spikes or dips in rates are not smoothed out over a long reporting period. It is the responsibility of consumers of this library to arrange for `flush_meters()` to be called at a regular interval, once to twice a minute is recommended for standard resolution metrics.

## Deployment

This repo contains both a service and a library. The service flushes fluentd periodically, and has a serverless-based deployment. Deployment is performed by creating a pull request from the `release` branch to the `stage` or `prod` branch, and then releasing the `deploy_hold` on CircleCI.

To release the library, submit a pull request from `dev` -> `release` which contains a semantic version bump in `setup.py`. Once merged, the `tag_release` job will automatically run on CircleCI and create a git tag corresponding to the released version.

## Linting & formatting

We use [lintball](https://github.com/elijahr/lintball) for linting to fix any auto-fixable issues via a git pre-commit hook. This runs `docformatter`, `autopep8`, `isort`, and `black`, in order.

To set up lintball locally:

```
brew install bash                             # bash v5 or greater required
npm install -g lintball                       # Install lintball
lintball install-tools py                     # Install Python formatters
git config --local core.hooksPath .githooks   # Enable hooks in .githooks dir
```

This will format your committed files properly at the time of commit and is considered best practice.
