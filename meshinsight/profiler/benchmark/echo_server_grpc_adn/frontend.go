package main

import (
	"fmt"
	"log"
	"net/http"

	"golang.org/x/net/context"
	"google.golang.org/grpc"

	echo "github.com/UWNetworksLab/meshinsight/meshinsight/profiler/benchmark/echo_server_grpc_adn/pb"
)

func handler(writer http.ResponseWriter, request *http.Request) {
	fmt.Printf("%s\n", request.URL.String())

	var conn *grpc.ClientConn
	conn, err := grpc.Dial(":9000", grpc.WithInsecure())
	if err != nil {
		log.Fatalf("could not connect: %s", err)
	}
	defer conn.Close()

	c := echo.NewEchoServiceClient(conn)

	message := echo.Msg{
		Body: request.URL.String(),
		// Body: "Hello",
	}

	response, err := c.Echo(context.Background(), &message)
	if err != nil {
		log.Fatalf("Erro when calling echo: %s", err)
	}
	log.Printf("Response from server: %s", response.Body)
	fmt.Fprintf(writer, "Echo request finished! Length of the request is %d\n", len(response.Body))
}

func main() {
	http.HandleFunc("/", handler)

	fmt.Printf("Starting server at port 8080\n")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}
