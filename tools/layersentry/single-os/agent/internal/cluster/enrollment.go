package cluster

import (
    "bytes"
    "context"
    "crypto/rand"
    "crypto/sha256"
    "crypto/subtle"
    "crypto/tls"
    "encoding/base64"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "net"
    "net/http"
    "os"
    "path/filepath"
    "regexp"
    "strconv"
    "strings"
    "sync"
    "time"

    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/filesystem"
    "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

const (
    defaultTTL             = 15 * time.Minute
    maxTTL                 = time.Hour
    defaultManagementPort  = 9443
    defaultMaxClockSkew     = 2 * time.Minute
    maxEnrollmentBodyBytes = 64 << 10
)

var uuidRE = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$`)
var tokenRE = regexp.MustCompile(`^lsjoin1\.([0-9a-fA-F-]{36})\.([A-Za-z0-9_-]{43})$`)
var fingerprintRE = regexp.MustCompile(`^[0-9a-f]{64}$`)

type Manager struct {
    root string
    mu   sync.Mutex
}

type TokenRecord struct {
    ID          string     `json:"id"`
    ServiceID   string     `json:"service_id"`
    Provider    string     `json:"provider"`
    ReleaseLine string     `json:"release_line"`
    AllowedRole string     `json:"allowed_role"`
    TokenSHA256 string     `json:"token_sha256"`
    CreatedAt   time.Time  `json:"created_at"`
    ExpiresAt   time.Time  `json:"expires_at"`
    UsedAt      *time.Time `json:"used_at,omitempty"`
}

type IssuedToken struct {
    Token     string    `json:"token"`
    ExpiresAt time.Time `json:"expires_at"`
}

type EnrollmentIntent struct {
    ServiceID   string `json:"service_id"`
    Provider    string `json:"provider"`
    ReleaseLine string `json:"release_line"`
    Role        string `json:"role"`
    NodeAddress string `json:"node_address"`
}

type PeerInfo struct {
    ServiceID   string    `json:"service_id"`
    Provider    string    `json:"provider"`
    ReleaseLine string    `json:"release_line"`
    Role        string    `json:"role"`
    Address     string    `json:"address"`
    ServicePort int       `json:"service_port"`
    ServerTime  time.Time `json:"server_time"`
}

type SecretGetter interface {
    Get(string) ([]byte, error)
}

type Client struct {
    Secrets SecretGetter
    Timeout time.Duration
    Now     func() time.Time
}

func Open(root string) (*Manager, error) {
    if !filepath.IsAbs(root) {
        return nil, errors.New("cluster enrollment root must be absolute")
    }
    if err := privateDir(root); err != nil {
        return nil, err
    }
    return &Manager{root: root}, nil
}

func (m *Manager) Issue(serviceID, provider, releaseLine, allowedRole string, ttl time.Duration, now time.Time) (IssuedToken, error) {
    if m == nil {
        return IssuedToken{}, errors.New("cluster enrollment manager unavailable")
    }
    if !uuidRE.MatchString(serviceID) || provider == "" || releaseLine == "" || allowedRole == "" {
        return IssuedToken{}, errors.New("cluster enrollment token scope is invalid")
    }
    if ttl == 0 {
        ttl = defaultTTL
    }
    if ttl < time.Minute || ttl > maxTTL {
        return IssuedToken{}, errors.New("cluster enrollment token TTL must be between 1 and 60 minutes")
    }
    id, err := newUUID()
    if err != nil {
        return IssuedToken{}, err
    }
    secret := make([]byte, 32)
    if _, err = io.ReadFull(rand.Reader, secret); err != nil {
        return IssuedToken{}, err
    }
    defer zero(secret)
    token := "lsjoin1." + id + "." + base64.RawURLEncoding.EncodeToString(secret)
    sum := sha256.Sum256([]byte(token))
    if now.IsZero() {
        now = time.Now().UTC()
    } else {
        now = now.UTC()
    }
    record := TokenRecord{
        ID:          id,
        ServiceID:   serviceID,
        Provider:    provider,
        ReleaseLine: releaseLine,
        AllowedRole: allowedRole,
        TokenSHA256: hex.EncodeToString(sum[:]),
        CreatedAt:   now,
        ExpiresAt:   now.Add(ttl),
    }
    raw, err := json.MarshalIndent(record, "", "  ")
    if err != nil {
        return IssuedToken{}, err
    }
    path := filepath.Join(m.root, id+".json")
    if err = filesystem.AtomicWrite(path, append(raw, '\n'), 0600, m.root); err != nil {
        return IssuedToken{}, err
    }
    return IssuedToken{Token: token, ExpiresAt: record.ExpiresAt}, nil
}

func (m *Manager) Consume(token []byte, intent EnrollmentIntent, now time.Time) error {
    if m == nil {
        return errors.New("cluster enrollment manager unavailable")
    }
    id, err := tokenID(token)
    if err != nil {
        return err
    }
    if !uuidRE.MatchString(intent.ServiceID) || intent.Provider == "" || intent.ReleaseLine == "" || intent.Role == "" {
        return errors.New("cluster enrollment intent invalid")
    }
    if now.IsZero() {
        now = time.Now().UTC()
    } else {
        now = now.UTC()
    }

    m.mu.Lock()
    defer m.mu.Unlock()
    record, err := m.read(id)
    if err != nil {
        return err
    }
    if record.UsedAt != nil {
        return errors.New("cluster enrollment token already used")
    }
    if !now.Before(record.ExpiresAt) {
        return errors.New("cluster enrollment token expired")
    }
    sum := sha256.Sum256(token)
    expected, err := hex.DecodeString(record.TokenSHA256)
    if err != nil || len(expected) != sha256.Size || subtle.ConstantTimeCompare(sum[:], expected) != 1 {
        return errors.New("cluster enrollment token rejected")
    }
    if record.ServiceID != intent.ServiceID || record.Provider != intent.Provider || record.ReleaseLine != intent.ReleaseLine || record.AllowedRole != intent.Role {
        return errors.New("cluster enrollment token scope mismatch")
    }
    used := now
    record.UsedAt = &used
    raw, err := json.MarshalIndent(record, "", "  ")
    if err != nil {
        return err
    }
    return filesystem.AtomicWrite(filepath.Join(m.root, id+".json"), append(raw, '\n'), 0600, m.root)
}

func (m *Manager) Prune(before time.Time) (int, error) {
    if m == nil {
        return 0, nil
    }
    m.mu.Lock()
    defer m.mu.Unlock()
    entries, err := os.ReadDir(m.root)
    if err != nil {
        return 0, err
    }
    removed := 0
    for _, e := range entries {
        if e.IsDir() || filepath.Ext(e.Name()) != ".json" {
            continue
        }
        id := strings.TrimSuffix(e.Name(), ".json")
        if !uuidRE.MatchString(id) {
            return removed, errors.New("malformed enrollment token record filename")
        }
        rec, err := m.read(id)
        if err != nil {
            return removed, err
        }
        terminalAt := rec.ExpiresAt
        if rec.UsedAt != nil && rec.UsedAt.After(terminalAt) {
            terminalAt = *rec.UsedAt
        }
        if terminalAt.Before(before) {
            if err = os.Remove(filepath.Join(m.root, e.Name())); err != nil {
                return removed, err
            }
            removed++
        }
    }
    return removed, nil
}

func (m *Manager) read(id string) (TokenRecord, error) {
    if !uuidRE.MatchString(id) {
        return TokenRecord{}, errors.New("invalid cluster enrollment token id")
    }
    path := filepath.Join(m.root, id+".json")
    fi, err := os.Lstat(path)
    if err != nil {
        return TokenRecord{}, err
    }
    if fi.Mode()&os.ModeSymlink != 0 || !fi.Mode().IsRegular() || fi.Size() < 2 || fi.Size() > 32<<10 {
        return TokenRecord{}, errors.New("unsafe cluster enrollment token record")
    }
    raw, err := os.ReadFile(path)
    if err != nil {
        return TokenRecord{}, err
    }
    var rec TokenRecord
    dec := json.NewDecoder(bytes.NewReader(raw))
    dec.DisallowUnknownFields()
    if err = dec.Decode(&rec); err != nil {
        return TokenRecord{}, err
    }
    if rec.ID != id || !uuidRE.MatchString(rec.ServiceID) || rec.TokenSHA256 == "" || rec.ExpiresAt.IsZero() {
        return TokenRecord{}, errors.New("cluster enrollment token record invalid")
    }
    return rec, nil
}

func (c *Client) Enroll(ctx context.Context, req model.ServiceRequest) (PeerInfo, error) {
    if c == nil || c.Secrets == nil {
        return PeerInfo{}, errors.New("cluster enrollment client unavailable")
    }
    peer := req.Cluster.EnrollmentPeer
    if net.ParseIP(peer) == nil {
        return PeerInfo{}, errors.New("cluster enrollment peer must be an IP address")
    }
    fingerprint := strings.ToLower(req.Cluster.PeerTLSFingerprints[peer])
    if !fingerprintRE.MatchString(fingerprint) {
        return PeerInfo{}, errors.New("cluster enrollment peer TLS fingerprint missing or invalid")
    }
    expectedFingerprint, _ := hex.DecodeString(fingerprint)
    port := req.Cluster.ManagementPort
    if port == 0 {
        port = defaultManagementPort
    }
    timeout := c.Timeout
    if timeout <= 0 {
        timeout = 10 * time.Second
    }
    token, err := c.Secrets.Get(req.Cluster.JoinTokenRef)
    if err != nil {
        return PeerInfo{}, err
    }
    defer zero(token)

    body, err := json.Marshal(struct {
        Token  string           `json:"token"`
        Intent EnrollmentIntent `json:"intent"`
    }{
        Token: string(token),
        Intent: EnrollmentIntent{
            ServiceID:   req.ServiceID,
            Provider:    req.Provider,
            ReleaseLine: req.ReleaseLine,
            Role:        req.Cluster.Role,
            NodeAddress: req.Network.ListenAddress,
        },
    })
    if err != nil {
        return PeerInfo{}, err
    }
    defer zero(body)

    tlsConfig := &tls.Config{
        MinVersion:         tls.VersionTLS12,
        InsecureSkipVerify: true, // Replaced by the mandatory SHA-256 leaf-certificate pin below.
        VerifyConnection: func(cs tls.ConnectionState) error {
            if len(cs.PeerCertificates) < 1 {
                return errors.New("cluster peer did not present a TLS certificate")
            }
            sum := sha256.Sum256(cs.PeerCertificates[0].Raw)
            if subtle.ConstantTimeCompare(sum[:], expectedFingerprint) != 1 {
                return errors.New("cluster peer TLS certificate fingerprint mismatch")
            }
            return nil
        },
    }
    transport := &http.Transport{
        Proxy:             nil,
        TLSClientConfig:   tlsConfig,
        DisableKeepAlives: true,
        DialContext:       (&net.Dialer{Timeout: 3 * time.Second, KeepAlive: -1}).DialContext,
    }
    client := &http.Client{
        Timeout:   timeout,
        Transport: transport,
        CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
            return errors.New("cluster enrollment redirects are not allowed")
        },
    }
    url := "https://" + net.JoinHostPort(peer, strconv.Itoa(port)) + "/api/v1/cluster/enroll"
    httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
    if err != nil {
        return PeerInfo{}, err
    }
    httpReq.Header.Set("Content-Type", "application/json")
    resp, err := client.Do(httpReq)
    if err != nil {
        return PeerInfo{}, fmt.Errorf("cluster enrollment peer TLS/reachability check failed: %w", err)
    }
    defer resp.Body.Close()
    if resp.StatusCode != http.StatusOK {
        return PeerInfo{}, errors.New("cluster enrollment peer rejected token or intent")
    }
    var info PeerInfo
    dec := json.NewDecoder(io.LimitReader(resp.Body, maxEnrollmentBodyBytes))
    dec.DisallowUnknownFields()
    if err = dec.Decode(&info); err != nil {
        return PeerInfo{}, errors.New("cluster enrollment peer returned invalid response")
    }
    if info.ServiceID != req.ServiceID || info.Provider != req.Provider || info.ReleaseLine != req.ReleaseLine {
        return PeerInfo{}, errors.New("cluster enrollment peer provider/release compatibility check failed")
    }
    if info.Address != peer || info.ServicePort < 1 || info.ServicePort > 65535 {
        return PeerInfo{}, errors.New("cluster enrollment peer topology response invalid")
    }
    if req.Provider == "postgresql" && req.Cluster.Role == "standby" && info.Role != "primary" {
        return PeerInfo{}, errors.New("PostgreSQL standby enrollment requires a primary peer")
    }
    now := time.Now().UTC()
    if c.Now != nil {
        now = c.Now().UTC()
    }
    skewLimit := defaultMaxClockSkew
    if req.Cluster.MaxClockSkewSeconds > 0 {
        skewLimit = time.Duration(req.Cluster.MaxClockSkewSeconds) * time.Second
    }
    skew := now.Sub(info.ServerTime)
    if skew < 0 {
        skew = -skew
    }
    if skew > skewLimit {
        return PeerInfo{}, errors.New("cluster peer clock skew exceeds policy")
    }
    conn, err := (&net.Dialer{Timeout: 3 * time.Second}).DialContext(ctx, "tcp", net.JoinHostPort(peer, strconv.Itoa(info.ServicePort)))
    if err != nil {
        return PeerInfo{}, errors.New("cluster peer provider data port is unreachable")
    }
    _ = conn.Close()
    return info, nil
}

func CertificateFingerprint(certPath string) (string, error) {
    if !filepath.IsAbs(certPath) {
        return "", errors.New("TLS certificate path must be absolute")
    }
    raw, err := os.ReadFile(certPath)
    if err != nil {
        return "", err
    }
    block, _ := decodePEMCertificate(raw)
    if len(block) == 0 {
        return "", errors.New("TLS certificate PEM invalid")
    }
    sum := sha256.Sum256(block)
    return hex.EncodeToString(sum[:]), nil
}

func decodePEMCertificate(raw []byte) ([]byte, []byte) {
    const begin = "-----BEGIN CERTIFICATE-----"
    const end = "-----END CERTIFICATE-----"
    text := string(raw)
    start := strings.Index(text, begin)
    if start < 0 {
        return nil, nil
    }
    text = text[start+len(begin):]
    finish := strings.Index(text, end)
    if finish < 0 {
        return nil, nil
    }
    encoded := strings.Map(func(r rune) rune {
        switch r {
        case ' ', '\t', '\r', '\n':
            return -1
        default:
            return r
        }
    }, text[:finish])
    der, err := base64.StdEncoding.DecodeString(encoded)
    if err != nil {
        return nil, nil
    }
    return der, raw
}

func tokenID(token []byte) (string, error) {
    if len(token) > 256 {
        return "", errors.New("cluster enrollment token rejected")
    }
    match := tokenRE.FindSubmatch(token)
    if len(match) != 3 {
        return "", errors.New("cluster enrollment token rejected")
    }
    id := string(match[1])
    if !uuidRE.MatchString(id) {
        return "", errors.New("cluster enrollment token rejected")
    }
    return id, nil
}

func privateDir(path string) error {
    if err := os.MkdirAll(path, 0700); err != nil {
        return err
    }
    fi, err := os.Lstat(path)
    if err != nil {
        return err
    }
    if !fi.IsDir() || fi.Mode()&os.ModeSymlink != 0 || fi.Mode().Perm()&0022 != 0 {
        return errors.New("cluster enrollment directory must be private and non-symlink")
    }
    return nil
}

func newUUID() (string, error) {
    b := make([]byte, 16)
    if _, err := io.ReadFull(rand.Reader, b); err != nil {
        return "", err
    }
    b[6] = (b[6] & 0x0f) | 0x40
    b[8] = (b[8] & 0x3f) | 0x80
    h := hex.EncodeToString(b)
    return h[0:8] + "-" + h[8:12] + "-" + h[12:16] + "-" + h[16:20] + "-" + h[20:32], nil
}

func zero(b []byte) {
    for i := range b {
        b[i] = 0
    }
}
