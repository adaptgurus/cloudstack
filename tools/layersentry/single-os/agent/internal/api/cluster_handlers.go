package api

import (
    "net"
    "net/http"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/cluster"
)

const clusterManagementPort = 9443

type EnrollmentManager interface {
    Issue(serviceID, provider, releaseLine, allowedRole, allowedNodeAddress string, ttl time.Duration, now time.Time) (cluster.IssuedToken, error)
    Consume(token []byte, intent cluster.EnrollmentIntent, now time.Time) error
}

func (s *Server) clusterEnrollmentTokens(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost {
        method(w)
        return
    }
    if s.Enrollment == nil || s.TLSCertFile == "" {
        serverErr(w, nil)
        return
    }
    var q struct {
        ServiceID   string `json:"service_id"`
        AllowedRole string `json:"allowed_role"`
        PeerAddress string `json:"peer_address"`
        TTLSeconds  int    `json:"ttl_seconds,omitempty"`
    }
    if err := decode(r, &q); err != nil {
        bad(w, err)
        return
    }
    if q.TTLSeconds != 0 && (q.TTLSeconds < 60 || q.TTLSeconds > 3600) {
        bad(w, errInvalidEnrollmentRequest)
        return
    }
    peerIP := net.ParseIP(q.PeerAddress)
    if peerIP == nil || peerIP.String() != q.PeerAddress {
        bad(w, errInvalidEnrollmentRequest)
        return
    }
    st, err := s.Journal.GetService(q.ServiceID)
    if err != nil || st.Status != "installed" || st.Topology != "cluster" || !declaredPeer(st.Cluster.Peers, q.PeerAddress) {
        bad(w, errInvalidEnrollmentRequest)
        return
    }
    switch st.Provider {
    case "postgresql":
        if st.Cluster.Role != "primary" || q.AllowedRole != "standby" {
            bad(w, errInvalidEnrollmentRequest)
            return
        }
    default:
        bad(w, errUnsupportedClusterEnrollment)
        return
    }
    ttl := time.Duration(q.TTLSeconds) * time.Second
    issued, err := s.Enrollment.Issue(st.ID, st.Provider, st.ReleaseLine, q.AllowedRole, q.PeerAddress, ttl, time.Now().UTC())
    if err != nil {
        bad(w, errInvalidEnrollmentRequest)
        return
    }
    fingerprint, err := cluster.CertificateFingerprint(s.TLSCertFile)
    if err != nil {
        serverErr(w, err)
        return
    }
    write(w, http.StatusCreated, map[string]any{
        "token":             issued.Token,
        "expires_at":        issued.ExpiresAt,
        "peer_address":      issued.PeerAddress,
        "tls_sha256":        fingerprint,
        "management_port":   clusterManagementPort,
        "service_id":        st.ID,
        "provider":          st.Provider,
        "release_line":      st.ReleaseLine,
        "allowed_role":      q.AllowedRole,
    })
}

func (s *Server) clusterEnroll(w http.ResponseWriter, r *http.Request) {
    if r.Method != http.MethodPost {
        method(w)
        return
    }
    if s.Enrollment == nil {
        clusterReject(w)
        return
    }
    var q struct {
        Token  string                   `json:"token"`
        Intent cluster.EnrollmentIntent `json:"intent"`
    }
    if err := decode(r, &q); err != nil {
        clusterReject(w)
        return
    }
    token := []byte(q.Token)
    q.Token = ""
    defer wipe(token)
    if len(token) < 80 || len(token) > 256 {
        clusterReject(w)
        return
    }
    remoteHost, _, err := net.SplitHostPort(r.RemoteAddr)
    if err != nil {
        clusterReject(w)
        return
    }
    remoteIP := net.ParseIP(remoteHost)
    intentIP := net.ParseIP(q.Intent.NodeAddress)
    if remoteIP == nil || intentIP == nil || !remoteIP.Equal(intentIP) {
        clusterReject(w)
        return
    }
    st, err := s.Journal.GetService(q.Intent.ServiceID)
    if err != nil || st.Status != "installed" || st.Topology != "cluster" || st.Provider != q.Intent.Provider || st.ReleaseLine != q.Intent.ReleaseLine || !declaredPeer(st.Cluster.Peers, q.Intent.NodeAddress) {
        clusterReject(w)
        return
    }
    switch st.Provider {
    case "postgresql":
        if st.Cluster.Role != "primary" || q.Intent.Role != "standby" {
            clusterReject(w)
            return
        }
    default:
        clusterReject(w)
        return
    }
    if err = s.Enrollment.Consume(token, q.Intent, time.Now().UTC()); err != nil {
        clusterReject(w)
        return
    }
    write(w, http.StatusOK, cluster.PeerInfo{
        ServiceID:   st.ID,
        Provider:    st.Provider,
        ReleaseLine: st.ReleaseLine,
        Role:        st.Cluster.Role,
        Address:     st.Network.ListenAddress,
        ServicePort: st.Network.Port,
        ServerTime:  time.Now().UTC(),
    })
}

func declaredPeer(peers []string, candidate string) bool {
    for _, peer := range peers {
        if peer == candidate {
            return true
        }
    }
    return false
}

func clusterReject(w http.ResponseWriter) {
    http.Error(w, "cluster enrollment rejected", http.StatusForbidden)
}

func wipe(b []byte) {
    for i := range b {
        b[i] = 0
    }
}

var (
    errInvalidEnrollmentRequest      = enrollmentError("invalid cluster enrollment request")
    errUnsupportedClusterEnrollment = enrollmentError("provider does not support cluster enrollment")
)

type enrollmentError string

func (e enrollmentError) Error() string { return string(e) }
