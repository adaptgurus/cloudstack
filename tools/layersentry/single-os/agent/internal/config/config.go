package config

import (
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "errors"
 "fmt"
 "net"
 "path/filepath"
 "strings"

 "github.com/adaptgurus/cloudstack/tools/layersentry/single-os/agent/internal/model"
)

func DecodeStrict(data []byte) (model.ServiceRequest, error) {
 var req model.ServiceRequest
 dec := json.NewDecoder(strings.NewReader(string(data)))
 dec.DisallowUnknownFields()
 if err := dec.Decode(&req); err != nil { return req, fmt.Errorf("decode request: %w", err) }
 if dec.More() { return req, errors.New("multiple JSON values are not allowed") }
 if err := Validate(req); err != nil { return req, err }
 return req, nil
}

func Validate(req model.ServiceRequest) error {
 if req.SchemaVersion != 1 { return fmt.Errorf("unsupported schema_version %d", req.SchemaVersion) }
 for name, v := range map[string]string{"request_id":req.RequestID,"service_id":req.ServiceID,"operation_id":req.OperationID,"idempotency_key":req.IdempotencyKey,"provider":req.Provider,"release_line":req.ReleaseLine,"topology":req.Topology} {
  if strings.TrimSpace(v)=="" { return fmt.Errorf("%s is required", name) }
  if len(v)>256 { return fmt.Errorf("%s too long", name) }
 }
 if req.Category != model.CategoryDatabase && req.Category != model.CategoryApplication { return errors.New("category must be database or application") }
 if req.Topology != "standalone" && req.Topology != "cluster" { return errors.New("topology must be standalone or cluster") }
 if req.Topology == "cluster" && strings.TrimSpace(req.Cluster.Role)=="" { return errors.New("cluster role is required") }
 if req.Network.Port < 1 || req.Network.Port > 65535 { return errors.New("network.port outside 1..65535") }
 if req.Network.ListenAddress != "" && net.ParseIP(req.Network.ListenAddress)==nil { return errors.New("invalid listen_address") }
 for _, cidr := range req.Network.AllowedCIDRs { if _,_,err:=net.ParseCIDR(cidr); err!=nil { return fmt.Errorf("invalid allowed CIDR %q", cidr) } }
 seenDevices := map[string]bool{}; seenMounts:=map[string]bool{}
 for _, s := range req.Storage {
  if !strings.HasPrefix(s.Device,"/dev/disk/by-") { return fmt.Errorf("device must use stable /dev/disk/by-* identity: %q", s.Device) }
  if seenDevices[s.Device] { return fmt.Errorf("duplicate device %q",s.Device) }; seenDevices[s.Device]=true
  clean:=filepath.Clean(s.MountPoint)
  if !filepath.IsAbs(clean) || clean=="/" || strings.HasPrefix(clean,"/boot") || strings.HasPrefix(clean,"/proc") || strings.HasPrefix(clean,"/sys") || strings.HasPrefix(clean,"/dev") { return fmt.Errorf("unsafe mount point %q",s.MountPoint) }
  if clean!=s.MountPoint { return fmt.Errorf("mount point must be canonical: %q",s.MountPoint) }
  if seenMounts[clean] { return fmt.Errorf("duplicate mount point %q",clean) }; seenMounts[clean]=true
  if s.Format && !s.ConfirmFormat { return fmt.Errorf("format requires confirm_format for %q",s.Device) }
  switch s.Filesystem { case "xfs","ext4","": default: return fmt.Errorf("unsupported filesystem %q",s.Filesystem) }
 }
 for k,v := range req.SecretRefs { if strings.TrimSpace(k)=="" || !strings.HasPrefix(v,"secret://") { return fmt.Errorf("secret_refs must contain secret:// references") } }
 return nil
}

func CanonicalDigest(req model.ServiceRequest) (string,error) {
 b,err:=json.Marshal(req); if err!=nil{return "",err}; s:=sha256.Sum256(b); return hex.EncodeToString(s[:]),nil
}
