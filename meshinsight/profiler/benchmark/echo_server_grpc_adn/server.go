package main

import (
	"fmt"
	"log"
	"net"

	codes "github.com/Romero027/grpc-go/codes"
	status "github.com/Romero027/grpc-go/status"
	"golang.org/x/net/context"

	grpc "github.com/Romero027/grpc-go"
	echo "github.com/UWNetworksLab/meshinsight/meshinsight/profiler/benchmark/echo_server_grpc_adn/pb"
)

type server struct {
	echo.UnimplementedEchoServiceServer
}

func UnaryServerInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp interface{}, err error) {
	// remote, _ := peer.FromContext(ctx)
	// remoteAddr := remote.Addr.String()

	// in, _ := json.Marshal(req)
	// log.Println(req)
	if m, ok := req.(*echo.Msg); ok {
		// log.Println("in", m.GetBody())
		if m.GetBody() == "/test" {
			return nil, status.Error(codes.InvalidArgument, "request blocked by ACL filter.")
		}
	}

	// start := time.Now()
	// defer func() {
	// 	out, _ := json.Marshal(resp)
	// 	outStr := string(out)
	// 	duration := int64(time.Since(start) / time.Millisecond)
	// 	log.Println("ip", remoteAddr, "access_end", info.FullMethod, "in", inStr, "out", outStr, "err", err, "duration/ms", duration)
	// }()
	// log.Println("Hello from UnaryServerInterceptor1")

	resp, err = handler(ctx, req)

	return
}

// func UnaryServerInterceptor2(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp interface{}, err error) {
// 	// remote, _ := peer.FromContext(ctx)
// 	// remoteAddr := remote.Addr.String()

// 	// in, _ := json.Marshal(req)
// 	// inStr := string(in)
// 	// log.Println("ip", remoteAddr, "access_start", info.FullMethod, "in", inStr)

// 	// start := time.Now()
// 	// defer func() {
// 	// 	out, _ := json.Marshal(resp)
// 	// 	outStr := string(out)
// 	// 	duration := int64(time.Since(start) / time.Millisecond)
// 	// 	log.Println("ip", remoteAddr, "access_end", info.FullMethod, "in", inStr, "out", outStr, "err", err, "duration/ms", duration)
// 	// }()
// 	log.Println("Hello from UnaryServerInterceptor2")
// 	resp, err = handler(ctx, req)

// 	return
// }

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
	s := grpc.NewServer(grpc.UnaryInterceptor(grpc.ChainUnaryServer(UnaryServerInterceptor)))
	fmt.Printf("Starting server at port 9000\n")

	echo.RegisterEchoServiceServer(s, &server{})
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
