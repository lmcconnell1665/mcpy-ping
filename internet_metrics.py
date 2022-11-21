import logging
import speedtest
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Runs the internet speed tests
def run_test(tracer):
    
    servers = []
    threads = None

    # Other Tracing spans will be children to this one
    with tracer.span(name="main") as span:
        # getting the servers does a ping
        s = speedtest.Speedtest(secure=True)
        logger.info("getting servers")
        tic = time.perf_counter()
        with tracer.span(name="get_servers") as span:
            s.get_servers(servers)
        tac = time.perf_counter()
        with tracer.span(name="get_best_servers") as span:
            s.get_best_server()
        toc = time.perf_counter()

        with tracer.span(name="measure_download") as span:
            logger.info("running download test")
            s.download(threads=threads)

        with tracer.span(name="measure_upload") as span:
            logger.info("running upload test")
            s.upload(threads=threads)

        # calculate and return the setup time which is not reported by speedtest
        # convert seconds based times to msec
        setup_time_dict = {
            "get_servers": (tac - tic) * 1000.0,
            "get_best_servers": (toc - tac) * 1000.0,
        }
        return s.results, setup_time_dict

def Merge(dict1, dict2):
    res = {**dict1, **dict2}
    return res
