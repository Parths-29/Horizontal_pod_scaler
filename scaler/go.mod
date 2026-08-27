module github.com/Parths-29/Horizontal_pod_scaler/scaler

go 1.22

require (
	// KEDA external scaler gRPC interface
	// We generate Go stubs from the official KEDA .proto file
	google.golang.org/grpc v1.64.0

	// Protocol Buffers runtime for Go
	google.golang.org/protobuf v1.34.2
)
