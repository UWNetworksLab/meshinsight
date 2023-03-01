package main

import (
	"fmt"
	"log"
	"net/http"

	grpc "github.com/Romero027/grpc-go"
	"golang.org/x/net/context"

	echo "github.com/UWNetworksLab/meshinsight/meshinsight/profiler/benchmark/echo_server_grpc_adn/pb"
)

// func UnaryClientInterceptor(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.ADNInvoker, opts ...grpc.CallOption) (err error) {
// 	// start := time.Now()
// 	// time.Sleep(1 * time.Second)
// 	// defer func() {
// 	// 	in, _ := json.Marshal(req)
// 	// 	out, _ := json.Marshal(reply)
// 	// 	inStr, outStr := string(in), string(out)
// 	// 	duration := int64(time.Since(start).Microseconds())

// 	// 	log.Printf(cc.Authority())
// 	// 	log.Println("grpc", method, "in", inStr, "out", outStr, "err", err, "duration/us", duration)

// 	// }()
// 	log.Println("Hello from UnaryClientInterceptor")
// 	return invoker(ctx, method, req, reply, cc, opts...)
// }

// func UnaryClientInterceptor2(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.ADNInvoker, opts ...grpc.CallOption) (err error) {
// 	// start := time.Now()
// 	// time.Sleep(1 * time.Second)
// 	// defer func() {
// 	// 	in, _ := json.Marshal(req)
// 	// 	out, _ := json.Marshal(reply)
// 	// 	inStr, outStr := string(in), string(out)
// 	// 	duration := int64(time.Since(start).Microseconds())

// 	// 	log.Printf(cc.Authority())
// 	// 	log.Println("grpc", method, "in", inStr, "out", outStr, "err", err, "duration/us", duration)

// 	// }()
// 	log.Println("Hello from UnaryClientInterceptor2")
// 	return invoker(ctx, method, req, reply, cc, opts...)
// }

func handler(writer http.ResponseWriter, request *http.Request) {
	fmt.Printf("%s\n", request.URL.String())

	var conn *grpc.ClientConn
	// conn, err := grpc.Dial(":9000", grpc.WithInsecure(), grpc.WithADNProcessor(grpc.ChainADNClientProcessors(UnaryClientInterceptor, UnaryClientInterceptor2)))
	conn, err := grpc.Dial(":9000", grpc.WithInsecure())
	if err != nil {
		log.Fatalf("could not connect: %s", err)
	}
	defer conn.Close()

	c := echo.NewEchoServiceClient(conn)

	message := echo.Msg{
		Body: request.URL.String(),
	}

	response, err := c.Echo(context.Background(), &message)
	if err == nil {
		log.Printf("Response from server: %s", response.Body)
		fmt.Fprintf(writer, "Echo request finished! Length of the request is %d\n", len(response.Body))
	} else {
		log.Printf("Erro when calling echo: %s", err)
		fmt.Fprintf(writer, "Echo server returns an error: %s\n", err)
	}
}

func main() {

	http.HandleFunc("/", handler)

	fmt.Printf("Starting server at port 8080\n")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}
