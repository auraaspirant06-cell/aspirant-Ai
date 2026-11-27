package main

import (
	"sync"
	"time"
)

// SlidingLimiter protects downstream FastAPI services from burst traffic.
type SlidingLimiter struct {
	mu      sync.Mutex
	maxReq  int
	window  time.Duration
	buckets map[string][]time.Time
}

func NewSlidingLimiter(maxReq int, window time.Duration) *SlidingLimiter {
	return &SlidingLimiter{
		maxReq:  maxReq,
		window:  window,
		buckets: make(map[string][]time.Time),
	}
}

func (l *SlidingLimiter) Allow(key string) (bool, int) {
	l.mu.Lock()
	defer l.mu.Unlock()

	now := time.Now()
	cutoff := now.Add(-l.window)
	existing := l.buckets[key]

	kept := existing[:0]
	for _, ts := range existing {
		if ts.After(cutoff) {
			kept = append(kept, ts)
		}
	}

	if len(kept) >= l.maxReq {
		l.buckets[key] = kept
		return false, 0
	}

	kept = append(kept, now)
	l.buckets[key] = kept
	return true, l.maxReq - len(kept)
}
