#!/usr/bin/python
import logging

from opencensus.stats import aggregation as aggregation_module
from opencensus.stats import measure as measure_module
from opencensus.stats import stats as stats_module
from opencensus.stats import view as view_module
from opencensus.tags import tag_key as tag_key
from opencensus.tags import tag_map as tag_map
from opencensus.tags import tag_value as tag_value
from opencensus.ext.azure import metrics_exporter

from opencensus.trace.tracer import Tracer
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import AlwaysOnSampler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# keys in the key map must also be in the view dimensions/columns to be exposed as customDimensions
tag_key_isp = tag_key.TagKey("client_isp")
tag_key_server_host = tag_key.TagKey("server_host")


def _create_metric_measure(metric_name, metric_description, metric_unit):
    # The description of our metric
    measure = measure_module.MeasureFloat(metric_name, metric_description, metric_unit)
    return measure


def _create_metric_view(view_manager, name, description, measure):
    # view must be registered prior to record
    ping_view = view_module.View(
        name=name,
        description=description,
        columns=[tag_key_isp, tag_key_server_host],
        measure=measure,
        aggregation=aggregation_module.LastValueAggregation(),
    )
    view_manager.register_view(ping_view)


# after this, everything sent to this view will end up in azure as a metric
def _register_azure_exporter_with_view_manager(view_manager, azure_connection_string):
    # enable the Azure metrics exporter which talks to Azure
    # standard metrics are CPU, memory, storage, etc.
    exporter = metrics_exporter.new_metrics_exporter(
        enable_standard_metrics=False, connection_string=azure_connection_string
    )
    view_manager.register_exporter(exporter)


def _record_metric_float(mmap, value, measure):
    # data from the speed test
    mmap.measure_float_put(measure, value)
    # the measure becomes the key to the measurement map
    logger.info(
        "metrics: %s value: %s number of measurements: %s ",
        measure.name,
        value,
        len(mmap.measurement_map),
    )


# Record a single metric. Apply same tags to all metrics.
def _tag_and_record(mmap, metrics_info):
    # apply same tags to every metric in batch
    tag_value_isp = tag_value.TagValue(metrics_info["client"]["isp"])
    tag_value_server_host = tag_value.TagValue(metrics_info["server"]["host"])
    tagmap = tag_map.TagMap()
    tagmap.insert(tag_key_isp, tag_value_isp)
    tagmap.insert(tag_key_server_host, tag_value_server_host)
    logger.debug("tagmap: %s", tagmap.map)
    mmap.record(tagmap)


def register_azure_exporter_with_tracer(azure_connection_string):
    tracer = Tracer(
        exporter=AzureExporter(connection_string=azure_connection_string),
        sampler=AlwaysOnSampler(),
    )
    return tracer


def push_azure_speedtest_metrics(json_data, azure_connection_string):
    # standard opencensus and azure exporter setup
    stats = stats_module.stats
    view_manager = stats.view_manager
    stats_recorder = stats.stats_recorder
    mmap = stats_recorder.new_measurement_map()

    # perf data gathered while running tests
    get_servers_measure = _create_metric_measure(
        "get_servers_time", "Amount of time it took to get_servers()", "ms"
    )
    get_best_servers_measure = _create_metric_measure(
        "get_best_servers_time", "Amount of time it took to get_best_servers()", "ms"
    )
    # we measure 3 different things so lets describe them
    ping_measure = _create_metric_measure(
        "ping_time", "The latency in milliseconds per ping check", "ms"
    )
    upload_measure = _create_metric_measure(
        "upload_speed", "Upload speed in megabits per second", "Mbps"
    )
    download_measure = _create_metric_measure(
        "download_speed", "Download speed in megabits per second", "Mbps"
    )

    # we always monitor ping and optionally capture upload or download
    # add setup metrics
    _create_metric_view(
        view_manager=view_manager,
        name="LM Servers Time",
        description="get servers",
        measure=get_servers_measure,
    )
    _create_metric_view(
        view_manager=view_manager,
        name="LM Best Servers Time",
        description="get best servers",
        measure=get_best_servers_measure,
    )
    # the name is what you see in the Azure App Insights drop lists
    # https://github.com/census-instrumentation/opencensus-python/issues/1015
    _create_metric_view(
        view_manager=view_manager,
        name="LM Ping Time",
        description="last ping",
        measure=ping_measure,
    )
    _create_metric_view(
        view_manager=view_manager,
        name="LM Upload Rate",
        description="last upload",
        measure=upload_measure,
    )
    _create_metric_view(
        view_manager=view_manager,
        name="LM Download Rate",
        description="last download",
        measure=download_measure,
    )

    # lets add the exporter and register our azure key with the exporter
    _register_azure_exporter_with_view_manager(view_manager, azure_connection_string)

    # views(measure, view)  events(measure,metric)
    # setup times
    _record_metric_float(mmap, json_data["get_servers"], get_servers_measure)
    _record_metric_float(mmap, json_data["get_best_servers"], get_best_servers_measure)
    _record_metric_float(mmap, json_data["ping"], ping_measure)
    _record_metric_float(mmap, json_data["upload"], upload_measure)
    _record_metric_float(mmap, json_data["download"], download_measure)


    # create our tags for these metrics - record the metrics - the exporter runs on a schedule
    # this will throw a 400 if the instrumentation key isn't set
    _tag_and_record(mmap, json_data)
    return mmap
