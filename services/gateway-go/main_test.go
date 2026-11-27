package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"
)

func TestGatewayHealthAndRateLimit(t *testing.T) {
	upstreamServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"proxied"}`))
	}))
	defer upstreamServer.Close()

	u, _ := url.Parse(upstreamServer.URL)
	limiter := NewSlidingLimiter(2, time.Minute)
	handler := newGatewayHandler(u, limiter)

	reqHealth := httptest.NewRequest(http.MethodGet, "/gateway/health", nil)
	recHealth := httptest.NewRecorder()
	handler.ServeHTTP(recHealth, reqHealth)
	if recHealth.Code != http.StatusOK {
		t.Fatalf("expected 200 on health, got %d", recHealth.Code)
	}

	for i := 0; i < 2; i++ {
		req := httptest.NewRequest(http.MethodGet, "/api/v1/health", nil)
		req.RemoteAddr = "127.0.0.1:50000"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("expected 200 on request %d, got %d", i+1, rec.Code)
		}
	}

	reqBlocked := httptest.NewRequest(http.MethodGet, "/api/v1/health", nil)
	reqBlocked.RemoteAddr = "127.0.0.1:50000"
	recBlocked := httptest.NewRecorder()
	handler.ServeHTTP(recBlocked, reqBlocked)
	if recBlocked.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429 on 3rd request, got %d", recBlocked.Code)
	}
}
