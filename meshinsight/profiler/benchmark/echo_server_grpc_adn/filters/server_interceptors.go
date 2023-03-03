package filters

import (
	codes "github.com/Romero027/grpc-go/codes"
	status "github.com/Romero027/grpc-go/status"
	"golang.org/x/net/context"

	grpc "github.com/Romero027/grpc-go"
	echo "github.com/UWNetworksLab/meshinsight/meshinsight/profiler/benchmark/echo_server_grpc_adn/pb"
)

func contentBasedACL(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp interface{}, err error) {

	if m, ok := req.(*echo.Msg); ok {
		// log.Println("in", m.GetBody())
		if m.GetBody() == "/test" {
			return nil, status.Error(codes.InvalidArgument, "request blocked by ACL filter.")
		}
	}

	resp, err = handler(ctx, req)

	return
}
