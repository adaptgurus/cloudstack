package api

import (
	"net"
	"net/http"
	"strconv"
	"sync"
	"time"
)

const (
	authWindow = 5 * time.Minute
	authBlock = 15 * time.Minute
	authMaxFailures = 5
	authMaxSources = 2048
)

type authBucket struct {
	Failures []time.Time
	BlockedUntil time.Time
	LastSeen time.Time
}

var authAttempts = struct{
	sync.Mutex
	m map[string]authBucket
}{m: make(map[string]authBucket)}

func authSource(remoteAddr string) string {
	host, _, err := net.SplitHostPort(remoteAddr)
	if err != nil { host = remoteAddr }
	ip := net.ParseIP(host)
	if ip == nil { return "unknown" }
	return ip.String()
}

func authKey(kind, remoteAddr string) string { return kind + ":" + authSource(remoteAddr) }

func allowAuthAttempt(kind, remoteAddr string) (bool, time.Duration) {
	now := time.Now().UTC(); key := authKey(kind, remoteAddr)
	authAttempts.Lock(); defer authAttempts.Unlock()
	b := authAttempts.m[key]; b.LastSeen = now; b.Failures = recentFailures(b.Failures, now)
	if now.Before(b.BlockedUntil) { authAttempts.m[key] = b; return false, b.BlockedUntil.Sub(now) }
	if !b.BlockedUntil.IsZero() { b.BlockedUntil = time.Time{} }
	authAttempts.m[key] = b; trimAuthSourcesLocked(); return true, 0
}

func recordAuthFailure(kind, remoteAddr string) {
	now := time.Now().UTC(); key := authKey(kind, remoteAddr)
	authAttempts.Lock(); defer authAttempts.Unlock()
	b := authAttempts.m[key]; b.LastSeen = now; b.Failures = recentFailures(b.Failures, now); b.Failures = append(b.Failures, now)
	if len(b.Failures) >= authMaxFailures { b.BlockedUntil = now.Add(authBlock); b.Failures = nil }
	authAttempts.m[key] = b; trimAuthSourcesLocked()
}

func recordAuthSuccess(kind, remoteAddr string) {
	authAttempts.Lock(); delete(authAttempts.m, authKey(kind, remoteAddr)); authAttempts.Unlock()
}

func recentFailures(in []time.Time, now time.Time) []time.Time {
	cut := now.Add(-authWindow); out := in[:0]
	for _, t := range in { if t.After(cut) { out = append(out, t) } }
	return out
}

func trimAuthSourcesLocked() {
	for len(authAttempts.m) > authMaxSources {
		var oldestKey string; var oldest time.Time
		for k, b := range authAttempts.m { if oldestKey == "" || b.LastSeen.Before(oldest) { oldestKey, oldest = k, b.LastSeen } }
		if oldestKey == "" { return }
		delete(authAttempts.m, oldestKey)
	}
}

func authRateLimited(w http.ResponseWriter, retry time.Duration) {
	seconds := int(retry.Round(time.Second) / time.Second); if seconds < 1 { seconds = 1 }
	w.Header().Set("Retry-After", strconv.Itoa(seconds))
	http.Error(w, "authentication temporarily rate limited", http.StatusTooManyRequests)
}
