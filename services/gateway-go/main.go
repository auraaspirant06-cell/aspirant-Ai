package main

import (
	"encoding/json"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strconv"
	"time"
)

func envOrDefault(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}

func newGatewayHandler(upstream *url.URL, limiter *SlidingLimiter) http.Handler {
	proxy := httputil.NewSingleHostReverseProxy(upstream)
	mux := http.NewServeMux()

	mux.HandleFunc("/gateway/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"status":   "ok",
			"service":  "aspirant-go-gateway",
			"upstream": upstream.String(),
		})
	})

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		ip, _, err := net.SplitHostPort(r.RemoteAddr)
		if err != nil {
			ip = r.RemoteAddr
		}
		allowed, remaining := limiter.Allow(ip + ":" + r.URL.Path)
		w.Header().Set("X-Gateway-Service", "aspirant-go")
		w.Header().Set("X-RateLimit-Remaining", strconv.Itoa(remaining))
		if !allowed {
			w.WriteHeader(http.StatusTooManyRequests)
			_, _ = w.Write([]byte(`{"detail":"Gateway rate limit exceeded"}`))
			return
		}
		proxy.ServeHTTP(w, r)
	})

	return mux
}

func main() {
	upstreamRaw := envOrDefault("UPSTREAM_API_URL", "http://127.0.0.1:8000")
	upstream, err := url.Parse(upstreamRaw)
	if err != nil {
		log.Fatalf("invalid UPSTREAM_API_URL: %v", err)
	}
	listenAddr := envOrDefault("GATEWAY_ADDR", ":8080")
	limiter := NewSlidingLimiter(180, time.Minute)

	srv := &http.Server{
		Addr:              listenAddr,
		Handler:           newGatewayHandler(upstream, limiter),
		ReadHeaderTimeout: 10 * time.Second,
	}
	log.Printf("Aspirant Go Gateway listening on %s -> %s", listenAddr, upstream.String())
	log.Fatal(srv.ListenAndServe())
}
