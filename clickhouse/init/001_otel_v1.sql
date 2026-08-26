-- Versioned OpenTelemetry analytics schema (T118).
-- PostgreSQL audit events remain authoritative. These tables are operational,
-- deletable analytics projections containing allowlisted metadata only.

CREATE DATABASE IF NOT EXISTS workflow_otel;

-- Collector-compatible ingress is intentionally non-persistent. The
-- materialized view below writes only allowlisted metadata to spans_v1, so a
-- compromised or older SDK cannot persist span-event/link attribute bodies.
CREATE TABLE IF NOT EXISTS workflow_otel.spans_otlp_ingest_v1
(
    Timestamp DateTime64(9),
    TraceId String,
    SpanId String,
    ParentSpanId String,
    TraceState String,
    SpanName String,
    SpanKind String,
    ServiceName String,
    ResourceAttributes Map(String, String),
    ScopeName String,
    ScopeVersion String,
    SpanAttributes Map(String, String),
    Duration UInt64,
    StatusCode String,
    StatusMessage String,
    Events Nested
    (
        Timestamp DateTime64(9),
        Name String,
        Attributes Map(String, String)
    ),
    Links Nested
    (
        TraceId String,
        SpanId String,
        TraceState String,
        Attributes Map(String, String)
    )
)
ENGINE = Null;

CREATE TABLE IF NOT EXISTS workflow_otel.spans_v1
(
    Timestamp DateTime64(9) CODEC(Delta, ZSTD(1)),
    TraceId String CODEC(ZSTD(1)),
    SpanId String CODEC(ZSTD(1)),
    ParentSpanId String CODEC(ZSTD(1)),
    TraceState String CODEC(ZSTD(1)),
    SpanName LowCardinality(String) CODEC(ZSTD(1)),
    SpanKind LowCardinality(String) CODEC(ZSTD(1)),
    ServiceName LowCardinality(String) CODEC(ZSTD(1)),
    ResourceAttributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    ScopeName String CODEC(ZSTD(1)),
    ScopeVersion String CODEC(ZSTD(1)),
    SpanAttributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    Duration UInt64 CODEC(ZSTD(1)),
    StatusCode LowCardinality(String) CODEC(ZSTD(1)),
    StatusMessage String CODEC(ZSTD(1)),
    Events Nested
    (
        Timestamp DateTime64(9),
        Name LowCardinality(String)
    ) CODEC(ZSTD(1)),
    Links Nested
    (
        TraceId String,
        SpanId String,
        TraceState String
    ) CODEC(ZSTD(1)),
    run_id String MATERIALIZED SpanAttributes['workflow.run.id'],
    risk_tier LowCardinality(String) MATERIALIZED SpanAttributes['workflow.risk_tier'],
    data_classification LowCardinality(String)
        MATERIALIZED SpanAttributes['workflow.data_classification'],
    audit_event_id String MATERIALIZED SpanAttributes['audit.event.id'],
    -- Phase 5 (15.1): a snake_case alias of TraceId so a cross-chain query keyed on
    -- `trace_id` reads the same column the OTLP exporter writes as `TraceId`. ALIAS is
    -- stored-free (computed at read time) and does not touch the ingest/MV contract.
    trace_id String ALIAS TraceId,
    INDEX idx_trace_id TraceId TYPE bloom_filter(0.001) GRANULARITY 1,
    INDEX idx_run_id run_id TYPE bloom_filter(0.001) GRANULARITY 1,
    INDEX idx_audit_event_id audit_event_id TYPE bloom_filter(0.001) GRANULARITY 1
)
ENGINE = MergeTree
PARTITION BY toDate(Timestamp)
ORDER BY (run_id, TraceId, Timestamp, SpanId)
TTL toDateTime(Timestamp) + toIntervalDay(
    multiIf(
        risk_tier = 'high', 365,
        data_classification = 'restricted', 30,
        StatusCode = 'Error', 180,
        90
    )
) DELETE
SETTINGS index_granularity = 8192, ttl_only_drop_parts = 0;

CREATE MATERIALIZED VIEW IF NOT EXISTS workflow_otel.spans_otlp_ingest_v1_mv
TO workflow_otel.spans_v1
AS SELECT
    Timestamp,
    TraceId,
    SpanId,
    ParentSpanId,
    TraceState,
    SpanName,
    SpanKind,
    ServiceName,
    mapFilter(
        (key, value) -> key IN (
            'service.name', 'service.version', 'deployment.environment.name',
            'workflow.system', 'agent.agntcy.id', 'agent.descriptor.hash'
        ),
        ResourceAttributes
    ) AS ResourceAttributes,
    ScopeName,
    ScopeVersion,
    mapFilter(
        (key, value) -> key IN (
            'workflow.run.id', 'workflow.step.id', 'workflow.correlation.id',
            'workflow.causation.id', 'workflow.spec.hash', 'workflow.policy.version',
            'workflow.attempt', 'workflow.risk_tier', 'workflow.data_classification',
            'workflow.verdict', 'workflow.phase', 'workflow.rejection.count',
            'workflow.recovery.count', 'workflow.escalation.type', 'workflow.cost.usd',
            'workflow.duration.ms', 'agent.role', 'agent.runtime', 'agent.agntcy.id',
            'agent.descriptor.hash', 'gen_ai.provider.name', 'gen_ai.request.model',
            'gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens', 'tool.name',
            'tool.result', 'audit.event.id', 'audit.integrity.digest', 'error.type',
            'error.classification', 'error.summary', 'qmd.query.hash', 'qmd.collection',
            'qmd.source.uri', 'qmd.content.hash', 'qmd.index.version',
            'qmd.result.count', 'qmd.max_score', 'pmo.assessment.version',
            'pmo.priority', 'agntcy.identity.evidence.hash', 'agntcy.health.result',
            'telemetry.capture.policy', 'telemetry.schema.version',
            'telemetry.sampling.policy', 'telemetry.retention.class'
        ),
        SpanAttributes
    ) AS SpanAttributes,
    Duration,
    StatusCode,
    '' AS StatusMessage,
    Events.Timestamp AS `Events.Timestamp`,
    arrayMap(value -> 'redacted', Events.Name) AS `Events.Name`,
    Links.TraceId AS `Links.TraceId`,
    Links.SpanId AS `Links.SpanId`,
    Links.TraceState AS `Links.TraceState`
FROM workflow_otel.spans_otlp_ingest_v1;

-- Phase 5 (15.1): a `default`-database view over spans_v1 so an operator (or the
-- gate's literal acceptance query) can `select distinct trace_id from spans_v1 …`
-- WITHOUT the workflow_otel. schema prefix. The view surfaces the snake_case
-- `trace_id`/`run_id` columns explicitly (a plain `SELECT *` would omit ALIAS/
-- MATERIALIZED columns), so the one-trace cross-store query reads identically here.
CREATE VIEW IF NOT EXISTS default.spans_v1 AS
    SELECT *, TraceId AS trace_id, run_id
    FROM workflow_otel.spans_v1;

CREATE TABLE IF NOT EXISTS workflow_otel.spans_v1_trace_id_ts
(
    TraceId String CODEC(ZSTD(1)),
    run_id String CODEC(ZSTD(1)),
    Start DateTime CODEC(Delta, ZSTD(1)),
    End DateTime CODEC(Delta, ZSTD(1)),
    SpanCount UInt64
)
ENGINE = SummingMergeTree
PARTITION BY toDate(Start)
ORDER BY (run_id, TraceId, Start)
TTL Start + INTERVAL 365 DAY DELETE;

CREATE MATERIALIZED VIEW IF NOT EXISTS workflow_otel.spans_v1_trace_id_ts_mv
TO workflow_otel.spans_v1_trace_id_ts
AS SELECT
    TraceId,
    SpanAttributes['workflow.run.id'] AS run_id,
    min(toDateTime(Timestamp)) AS Start,
    max(toDateTime(Timestamp)) AS End,
    count() AS SpanCount
FROM workflow_otel.spans_v1
WHERE TraceId != ''
GROUP BY TraceId, run_id;

CREATE TABLE IF NOT EXISTS workflow_otel.logs_v1
(
    Timestamp DateTime64(9) CODEC(Delta(8), ZSTD(1)),
    TimestampTime DateTime DEFAULT toDateTime(Timestamp),
    TraceId String CODEC(ZSTD(1)),
    SpanId String CODEC(ZSTD(1)),
    TraceFlags UInt8,
    SeverityText LowCardinality(String) CODEC(ZSTD(1)),
    SeverityNumber UInt8,
    ServiceName LowCardinality(String) CODEC(ZSTD(1)),
    -- Collector policy empties all unstructured bodies. This compatibility
    -- column remains for the standard exporter insert contract.
    Body String CODEC(ZSTD(1)),
    ResourceSchemaUrl LowCardinality(String) CODEC(ZSTD(1)),
    ResourceAttributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    ScopeSchemaUrl LowCardinality(String) CODEC(ZSTD(1)),
    ScopeName String CODEC(ZSTD(1)),
    ScopeVersion LowCardinality(String) CODEC(ZSTD(1)),
    ScopeAttributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    LogAttributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    run_id String MATERIALIZED LogAttributes['workflow.run.id'],
    risk_tier LowCardinality(String) MATERIALIZED LogAttributes['workflow.risk_tier'],
    data_classification LowCardinality(String)
        MATERIALIZED LogAttributes['workflow.data_classification'],
    INDEX idx_trace_id TraceId TYPE bloom_filter(0.001) GRANULARITY 1,
    INDEX idx_run_id run_id TYPE bloom_filter(0.001) GRANULARITY 1
)
ENGINE = MergeTree
PARTITION BY toDate(TimestampTime)
ORDER BY (run_id, ServiceName, TimestampTime, Timestamp)
TTL TimestampTime + toIntervalDay(
    multiIf(
        risk_tier = 'high', 180,
        data_classification = 'restricted', 14,
        SeverityNumber >= 17, 90,
        30
    )
) DELETE
SETTINGS index_granularity = 8192, ttl_only_drop_parts = 0;

CREATE TABLE IF NOT EXISTS workflow_otel.metrics_gauge_v1
(
    ResourceAttributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    ResourceSchemaUrl String CODEC(ZSTD(1)),
    ScopeName String CODEC(ZSTD(1)),
    ScopeVersion String CODEC(ZSTD(1)),
    ScopeAttributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    ScopeDroppedAttrCount UInt32 CODEC(ZSTD(1)),
    ScopeSchemaUrl String CODEC(ZSTD(1)),
    ServiceName LowCardinality(String) CODEC(ZSTD(1)),
    MetricName String CODEC(ZSTD(1)),
    MetricDescription String CODEC(ZSTD(1)),
    MetricUnit String CODEC(ZSTD(1)),
    Attributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    StartTimeUnix DateTime64(9) CODEC(Delta, ZSTD(1)),
    TimeUnix DateTime64(9) CODEC(Delta, ZSTD(1)),
    Value Float64 CODEC(ZSTD(1)),
    Flags UInt32 CODEC(ZSTD(1)),
    Exemplars Nested
    (
        FilteredAttributes Map(LowCardinality(String), String),
        TimeUnix DateTime64(9),
        Value Float64,
        SpanId String,
        TraceId String
    ) CODEC(ZSTD(1)),
    run_id String MATERIALIZED Attributes['workflow.run.id']
)
ENGINE = MergeTree
PARTITION BY toDate(TimeUnix)
ORDER BY (ServiceName, MetricName, Attributes, toUnixTimestamp64Nano(TimeUnix))
TTL toDateTime(TimeUnix) + INTERVAL 90 DAY DELETE;

CREATE TABLE IF NOT EXISTS workflow_otel.metrics_sum_v1
AS workflow_otel.metrics_gauge_v1;
ALTER TABLE workflow_otel.metrics_sum_v1
    ADD COLUMN IF NOT EXISTS AggregationTemporality Int32 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS IsMonotonic Boolean CODEC(Delta, ZSTD(1));

CREATE TABLE IF NOT EXISTS workflow_otel.metrics_histogram_v1
AS workflow_otel.metrics_gauge_v1;
ALTER TABLE workflow_otel.metrics_histogram_v1
    ADD COLUMN IF NOT EXISTS Count UInt64 CODEC(Delta, ZSTD(1)),
    ADD COLUMN IF NOT EXISTS Sum Float64 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS BucketCounts Array(UInt64) CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS ExplicitBounds Array(Float64) CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS Min Float64 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS Max Float64 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS AggregationTemporality Int32 CODEC(ZSTD(1));

CREATE TABLE IF NOT EXISTS workflow_otel.metrics_exponential_histogram_v1
AS workflow_otel.metrics_gauge_v1;
ALTER TABLE workflow_otel.metrics_exponential_histogram_v1
    ADD COLUMN IF NOT EXISTS Count UInt64 CODEC(Delta, ZSTD(1)),
    ADD COLUMN IF NOT EXISTS Sum Float64 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS Scale Int32 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS ZeroCount UInt64 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS PositiveOffset Int32 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS PositiveBucketCounts Array(UInt64) CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS NegativeOffset Int32 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS NegativeBucketCounts Array(UInt64) CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS Min Float64 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS Max Float64 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS AggregationTemporality Int32 CODEC(ZSTD(1));

CREATE TABLE IF NOT EXISTS workflow_otel.metrics_summary_v1
AS workflow_otel.metrics_gauge_v1;
ALTER TABLE workflow_otel.metrics_summary_v1
    ADD COLUMN IF NOT EXISTS Count UInt64 CODEC(Delta, ZSTD(1)),
    ADD COLUMN IF NOT EXISTS Sum Float64 CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS `ValueAtQuantiles.Quantile` Array(Float64) CODEC(ZSTD(1)),
    ADD COLUMN IF NOT EXISTS `ValueAtQuantiles.Value` Array(Float64) CODEC(ZSTD(1));

CREATE TABLE IF NOT EXISTS workflow_otel.telemetry_deletion_log_v1
(
    request_id UUID,
    run_id String,
    requested_by String,
    reason_code LowCardinality(String),
    requested_at DateTime64(3),
    completed_at Nullable(DateTime64(3)),
    affected_signals Array(LowCardinality(String))
)
ENGINE = MergeTree
ORDER BY (requested_at, request_id)
TTL toDateTime(requested_at) + INTERVAL 7 YEAR DELETE;

CREATE TABLE IF NOT EXISTS workflow_otel.retention_policy_v1
(
    signal LowCardinality(String),
    environment LowCardinality(String),
    risk_tier LowCardinality(String),
    data_classification LowCardinality(String),
    retention_days UInt16,
    policy_version LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY (signal, environment, risk_tier, data_classification);

INSERT INTO workflow_otel.retention_policy_v1 VALUES
    ('trace', 'development', 'low', 'internal', 90, 'retention-v1'),
    ('trace', 'development', 'high', 'internal', 365, 'retention-v1'),
    ('trace', 'development', 'low', 'restricted', 30, 'retention-v1'),
    ('log', 'development', 'low', 'internal', 30, 'retention-v1'),
    ('log', 'development', 'high', 'internal', 180, 'retention-v1'),
    ('log', 'development', 'low', 'restricted', 14, 'retention-v1'),
    ('metric', 'development', 'low', 'internal', 90, 'retention-v1');

