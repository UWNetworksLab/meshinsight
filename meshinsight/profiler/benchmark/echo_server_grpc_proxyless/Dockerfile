From golang:1.18.3

WORKDIR /echoserver

COPY . ./


RUN go mod download
RUN go get github.com/Romero027/echo-server-grpc/pb
RUN go build -o /frontend frontend.go
#RUN go build -o /server server.go

EXPOSE 8080
#EXPOSE 9000

CMD [ "/frontend" ]
#CMD ["/server"]