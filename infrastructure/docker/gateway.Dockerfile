FROM golang:1.23-alpine AS builder
WORKDIR /src
COPY services/gateway-go/ ./
RUN go build -o /out/aspirant-gateway .

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=builder /out/aspirant-gateway /usr/local/bin/aspirant-gateway
EXPOSE 8080
CMD ["/usr/local/bin/aspirant-gateway"]
