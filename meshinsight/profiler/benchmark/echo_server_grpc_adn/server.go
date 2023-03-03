package main

import (
	"fmt"
	"log"
	"net"

	"golang.org/x/net/context"

	grpc "github.com/Romero027/grpc-go"
	echo "github.com/UWNetworksLab/meshinsight/meshinsight/profiler/benchmark/echo_server_grpc_adn/pb"
)

type server struct {
	echo.UnimplementedEchoServiceServer
}

func (s *server) Echo(ctx context.Context, x *echo.Msg) (*echo.Msg, error) {
	log.Printf("got: [%s]", x.GetBody())
	return x, nil
}

func main() {
	lis, err := net.Listen("tcp", ":9000")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	// s := grpc.NewServer(grpc.UnaryInterceptor(grpc.ChainUnaryServer(UnaryServerInterceptor, UnaryServerInterceptor2)))
	s := grpc.NewServer(grpc.UnaryInterceptor(grpc.ChainUnaryServer(filters.contentBasedACL())))
	fmt.Printf("Starting server at port 9000\n")

	echo.RegisterEchoServiceServer(s, &server{})
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
