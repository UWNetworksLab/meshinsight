package filters

import (
	"log"

	"golang.org/x/net/context"

	grpc "github.com/Romero027/grpc-go"
)

func hello(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.ADNInvoker, opts ...grpc.CallOption) (err error) {
	log.Println("Hello from UnaryClientInterceptor")
	return invoker(ctx, method, req, reply, cc, opts...)
}
