# CRISP: Critical Path Analysis of Microservice Traces

This repo contains code to compute and present critical path summary from [Jaeger](https://github.com/jaegertracing/jaeger) microservice traces.
To use first collect the microservice traces of a specific endpoint in a directory (say `traces`).
Let the traces be for `OP` operation and `SVC` service (these are Jaeger termonologies, which can be found via Jaeger webpage UI).
`python3 process.py --operationName OP --serviceName SVC -t <path to trace> -o . --parallelism 8` will produce the critical path summary using 8 concurrent processes. 
The summary will be output in the current directory as an HTML file with a heatmap, flamegraph, and summary text in `criticalPaths.html`.
It will also produce three flamegraphs `flame-graph-*.svg` for three different percentile values.

The script accepts the following options:

```bash
python3 process.py --help
usage: process.py [-h] -a OPERATIONNAME -s SERVICENAME [-t TRACEDIR] [--file FILE] -o OUTPUTDIR
                  [--parallelism PARALLELISM] [--topN TOPN] [--numTrace NUMTRACE] [--numOperation NUMOPERATION]

optional arguments:
  -h, --help            show this help message and exit
  -a OPERATIONNAME, --operationName OPERATIONNAME
                        operation name
  -s SERVICENAME, --serviceName SERVICENAME
                        name of the service
  -t TRACEDIR, --traceDir TRACEDIR
                        path of the trace directory (mutually exclusive with --file)
  --file FILE           input path of the trace file (mutually exclusivbe with --traceDir)
  -o OUTPUTDIR, --outputDir OUTPUTDIR
                        directory where output will be produced
  --parallelism PARALLELISM
                        number of concurrent python processes.
  --topN TOPN           number of services to show in the summary
  --numTrace NUMTRACE   number of traces to show in the heatmap
  --numOperation NUMOPERATION
                        number of operations to show in the heatmap
```

## Example 1 
To demonstrate the usage of CRISP, I've exported a trace from a simple two service [application](https://github.com/albertteoh/jaeger-go-example). See `example1/criticalPaths.html` for output summary and flame graphs for critical paths.

#### Application architecture
```
+------------+     +---------------+   
| service a  +---->+   service b   | 
+------------+     +-----+---------+   

```

#### Command
```bash
python3 process.py --operationName ping-receive --serviceName service-a -t ./example1 -o ./example1 --parallelism 1 --rootTrace
```

## Example 2
I've also exported a trace from a [video application](https://github.com/marcel-dempers/docker-development-youtube-series/tree/master/tracing). See `example2/criticalPaths.html` for output summary and flame graphs for critical paths.

#### Application architecture
```
+------------+     +---------------+    +--------------+
| videos-web +---->+ playlists-api +--->+ playlists-db |
|            |     |               |    |    [redis]   |
+------------+     +-----+---------+    +--------------+
                         |
                         v
                   +-----+------+       +-----------+
                   | videos-api +------>+ videos-db |
                   |            |       |  [redis]  |
                   +------------+       +-----------+

```
#### Command
```bash
python3 process.py --operationName "playlists-api: GET /" --serviceName playlists-api -t ./example2 -o ./example2 --parallelism 8 --rootTrace
```


## Note
This repo is a copy (with several modifications) of the [**CRISP**](https://github.com/uber-research/CRISP) tool created by Uber. 