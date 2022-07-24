# Annotated Call Graph (ACG)

Application developers can use MeshInsight to estimate service mesh overhead in any deployment scenario of interest by providing an annotated call graph (ACG). See section 4.2 of our [paper](https://arxiv.org/pdf/2207.00592.pdf) for ACG definition. Each call is formatted as (Upstream microservice, Downstream microservice, Message Size, Message Rate, Protocol).

See `book_info.txt` for an example critical path for the [bookinfo](https://istio.io/latest/docs/examples/bookinfo/) application.

We plan to integrate Meshinsight with tracing and critical path analysis tools like [FIRM](https://www.usenix.org/conference/osdi20/presentation/qiu) or [CRISP](https://www.usenix.org/conference/osdi20/presentation/qiu) in the future.

